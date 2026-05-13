"""F02 Prompt Optimizer — LlmPromptModifier.

``LlmPromptModifier`` 는 ``PromptModifier`` Protocol 의 실 구현체다.
F01 ``AutoLoopOrchestrator`` 가 retry FAIL 시 이 클래스를 호출하며,
Claude Opus 를 통해 prompt body 를 자동 수정하고 새 PromptVersion 을 생성한다.

설계 불변식 (정적 검증 필수):
  - anthropic / openai / replicate 을 직접 import 하지 않는다 (FR-10 / AC-6).
    Claude 호출은 adapters/claude.py:ClaudeAdapter 경유만.
  - evaluator 모듈을 import 하지 않는다 (FR-11 / AC-5).
    engine.evaluator 또는 evaluator system prompt 참조 0건.
  - Style.status 를 'approved' 로 자동 전이하지 않는다 (AC-7).
  - PromptModifier Protocol 시그니처 변경 금지 (F01 회귀 보호).
"""

from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any

import structlog

from style_workbench.adapters.base import ModelInput, ModelOutput
from style_workbench.adapters.claude import ClaudeAdapter
from style_workbench.core.errors import PromptOptimizerInvalidOutputError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.optimization import PromptOptimization, PromptOptimizationRepo
from style_workbench.domain.prompt.template import extract_placeholders
from style_workbench.prompts.prompt_optimizer import (
    MAX_TOKENS,
    OPTIMIZER_MODEL,
    PROMPT_OPTIMIZER_SYSTEM_PROMPT,
    TEMPERATURE,
    build_optimizer_user_message,
)
from style_workbench.services.prompt_service import PromptService

logger = structlog.get_logger(__name__)

# 1 USD ≈ 1,400 KRW (adapters/CLAUDE.md 비용 단가 기준)
_DEFAULT_USD_TO_WON: float = 1_400.0


class LlmPromptModifier:
    """F02 Prompt Optimizer — Claude 기반 prompt body 자동 수정.

    ``PromptModifier`` Protocol 을 구현한다. ``AutoLoopOrchestrator`` 에
    ``NoopPromptModifier`` 대신 주입하면 retry FAIL 시 Claude Opus 로
    prompt 를 수정해 새 PromptVersion 을 생성한다.

    F01 회귀 보호:
      - ``prompt_version_id is None`` (인라인 prompt) → 즉시 Noop 반환.
      - Claude API 오류 / JSON 파싱 실패 / placeholder 누락 →
        ``prompt_optimizations`` row (succeeded=false) 저장 후 Noop 반환.
      - Protocol 시그니처 변경 금지.

    비용 기록:
      - 마지막 수정 호출의 비용은 ``last_cost_won`` 속성으로 노출 (F09 budget 통합 예정).
    """

    def __init__(
        self,
        claude: ClaudeAdapter,
        prompt_service: PromptService,
        optimization_repo: PromptOptimizationRepo,
        prompt_version_repo: Any,  # PromptVersionRepo Protocol — 원본 버전 조회
        prompt_repo: Any,  # PromptRepo Protocol — node_type 추출용
        model_id: str = OPTIMIZER_MODEL,
        temperature: float = TEMPERATURE,
        max_tokens: int = MAX_TOKENS,
        usd_to_won: float = _DEFAULT_USD_TO_WON,
    ) -> None:
        self._claude = claude
        self._prompt_service = prompt_service
        self._optimization_repo = optimization_repo
        self._prompt_version_repo = prompt_version_repo
        self._prompt_repo = prompt_repo
        self._model_id = model_id
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._usd_to_won = usd_to_won

        # 마지막 modify() 호출의 비용 (won) — AutoLoopOrchestrator 가 활용 가능
        self.last_cost_won: Decimal = Decimal("0")

    # ------------------------------------------------------------------
    # PromptModifier Protocol
    # ------------------------------------------------------------------

    async def modify(
        self,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
    ) -> tuple[str, str | None]:
        """Return (new_prompt_text, new_prompt_version_id).

        spec FR-1 Protocol 호환.

        Returns:
            ("", None)  — Noop (인라인 prompt, Claude 오류, invalid output)
            (new_body, new_version_id) — 성공 시 새 PromptVersion
        """
        # ── 케이스 1: 인라인 prompt (prompt_version_id 없음) ──────────────────
        if prompt_version_id is None:
            logger.debug("prompt_optimizer_noop_inline_prompt")
            return ("", None)

        # ── 원본 PromptVersion 조회 ───────────────────────────────────────────
        original_version = await self._prompt_version_repo.get(prompt_version_id)
        if original_version is None:
            logger.warning(
                "prompt_optimizer_version_not_found",
                prompt_version_id=prompt_version_id,
            )
            return ("", None)

        # ── Prompt 조회 (node_type 추출) ───────────────────────────────────────
        prompt = await self._prompt_repo.get(original_version.prompt_id)
        if prompt is None:
            logger.warning(
                "prompt_optimizer_prompt_not_found",
                prompt_id=original_version.prompt_id,
            )
            return ("", None)

        node_type = str(prompt.node_type)

        # declared_variables → build_optimizer_user_message 형식으로 변환
        declared_variables_dicts = [
            {"name": v.name, "role": v.role, "required": v.required}
            for v in original_version.declared_variables
        ]

        # retry_guidance 에 instruction 키가 없으면 임시 보강
        if not retry_guidance or "instruction" not in retry_guidance:
            effective_guidance: dict[str, Any] = {
                "instruction": "이전 evaluation 의 지침에 따라 prompt 를 개선하라.",
                **retry_guidance,
            }
        else:
            effective_guidance = retry_guidance

        # ── Claude 호출 ────────────────────────────────────────────────────────
        start_ms = time.monotonic()
        claude_output: ModelOutput | None = None
        cost_won = Decimal("0")

        try:
            user_msg = build_optimizer_user_message(
                original_body=original_version.body,
                declared_variables=declared_variables_dicts,
                retry_guidance=effective_guidance,
                failed_dimensions=failed_dimensions,
                node_type=node_type,
            )

            claude_input = ModelInput(
                model_id=self._model_id,
                prompt=user_msg,
                system=PROMPT_OPTIMIZER_SYSTEM_PROMPT,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )

            claude_output = await self._claude.generate(claude_input)
            latency_ms = int((time.monotonic() - start_ms) * 1000)
            cost_won = Decimal(str(round(claude_output.cost_usd * self._usd_to_won, 2)))

        except Exception as api_err:
            latency_ms = int((time.monotonic() - start_ms) * 1000)
            failure_reason = f"ClaudeAPI: {type(api_err).__name__}: {api_err!s}"
            logger.warning(
                "prompt_optimizer_api_error",
                prompt_version_id=prompt_version_id,
                error_type=type(api_err).__name__,
            )
            await self._save_failed_row(
                prompt_id=original_version.prompt_id,
                parent_version_id=prompt_version_id,
                retry_guidance=retry_guidance,
                failed_dimensions=failed_dimensions,
                failure_reason=failure_reason,
                cost_won=cost_won,
                latency_ms=latency_ms,
            )
            self.last_cost_won = cost_won
            return ("", None)

        # ── JSON 파싱 ──────────────────────────────────────────────────────────
        try:
            parsed = json.loads(claude_output.text)
            new_body: str = parsed["new_body"]
            change_summary: str | None = parsed.get("change_summary")
        except (json.JSONDecodeError, KeyError, TypeError) as parse_err:
            failure_reason = f"InvalidJSON: {parse_err!s}"
            logger.warning(
                "prompt_optimizer_json_parse_error",
                prompt_version_id=prompt_version_id,
                error=str(parse_err),
            )
            await self._save_failed_row(
                prompt_id=original_version.prompt_id,
                parent_version_id=prompt_version_id,
                retry_guidance=retry_guidance,
                failed_dimensions=failed_dimensions,
                failure_reason=failure_reason,
                cost_won=cost_won,
                latency_ms=latency_ms,
            )
            self.last_cost_won = cost_won
            return ("", None)

        # ── FR-4: placeholder 보호 검증 ────────────────────────────────────────
        try:
            _validate_required_placeholders(
                new_body=new_body,
                declared_variables=declared_variables_dicts,
            )
        except PromptOptimizerInvalidOutputError as ph_err:
            failure_reason = f"PromptOptimizerInvalidOutputError: {ph_err!s}"
            logger.warning(
                "prompt_optimizer_placeholder_missing",
                prompt_version_id=prompt_version_id,
                error=str(ph_err),
            )
            await self._save_failed_row(
                prompt_id=original_version.prompt_id,
                parent_version_id=prompt_version_id,
                retry_guidance=retry_guidance,
                failed_dimensions=failed_dimensions,
                failure_reason=failure_reason,
                cost_won=cost_won,
                latency_ms=latency_ms,
            )
            self.last_cost_won = cost_won
            return ("", None)

        # ── FR-5: 새 PromptVersion 생성 ────────────────────────────────────────
        new_version = await self._prompt_service.create_version(
            prompt_id=original_version.prompt_id,
            body=new_body,
            declared_variables=original_version.declared_variables,
            change_note=f"auto:F02 — {change_summary}",
            model_default=original_version.model_default,
            created_by="auto:F02",
        )

        # ── FR-6: optimization row 저장 (succeeded=true) ───────────────────────
        opt_id = new_ulid()
        opt = PromptOptimization(
            id=opt_id,
            prompt_id=original_version.prompt_id,
            parent_version_id=prompt_version_id,
            new_version_id=new_version.id,
            retry_guidance=retry_guidance,
            failed_dimensions=failed_dimensions,
            eval_evidence=None,
            change_summary=change_summary,
            cost_won=cost_won,
            latency_ms=latency_ms,
            succeeded=True,
            failure_reason=None,
        )
        await self._optimization_repo.create(opt)

        self.last_cost_won = cost_won
        logger.info(
            "prompt_optimizer_success",
            optimization_id=opt_id,
            prompt_id=original_version.prompt_id,
            parent_version_id=prompt_version_id,
            new_version_id=new_version.id,
            cost_won=float(cost_won),
            latency_ms=latency_ms,
        )
        return (new_body, new_version.id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _save_failed_row(
        self,
        prompt_id: str,
        parent_version_id: str,
        retry_guidance: dict[str, Any],
        failed_dimensions: list[str],
        failure_reason: str,
        cost_won: Decimal,
        latency_ms: int,
    ) -> None:
        """succeeded=false row 저장 — F02 호출 실패 시 항상 기록 (AC-4)."""
        opt = PromptOptimization(
            id=new_ulid(),
            prompt_id=prompt_id,
            parent_version_id=parent_version_id,
            new_version_id=None,
            retry_guidance=retry_guidance,
            failed_dimensions=failed_dimensions,
            eval_evidence=None,
            change_summary=None,
            cost_won=cost_won,
            latency_ms=latency_ms,
            succeeded=False,
            failure_reason=failure_reason,
        )
        try:
            await self._optimization_repo.create(opt)
        except Exception as save_err:
            # 저장 자체가 실패해도 Noop 반환은 유지 — 로그만 남긴다
            logger.error(
                "prompt_optimizer_failed_row_save_error",
                prompt_id=prompt_id,
                error=str(save_err),
            )


# ---------------------------------------------------------------------------
# FR-4: Required placeholder 검증
# ---------------------------------------------------------------------------


def _validate_required_placeholders(
    new_body: str,
    declared_variables: list[dict[str, Any]],
) -> None:
    """new_body 에 required=true 인 모든 placeholder 가 존재하는지 검증.

    누락이 있으면 ``PromptOptimizerInvalidOutputError`` raise.
    domain/prompt/template.py 의 ``extract_placeholders`` 를 사용해
    ``{name}`` 패턴만 인식 (CLAUDE.md §2.5).
    """
    found_in_new_body = extract_placeholders(new_body)
    required_names = {v["name"] for v in declared_variables if v.get("required", True)}
    missing = required_names - found_in_new_body
    if missing:
        missing_str = ", ".join(f"{{{name}}}" for name in sorted(missing))
        raise PromptOptimizerInvalidOutputError(f"missing placeholder {missing_str}")
