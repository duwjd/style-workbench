"""Unit tests for LlmPromptModifier (F02 Prompt Optimizer).

spec §10.1 / §10.5 — engine/test_prompt_optimizer.py

테스트 대상:
  - test_modify_valid_output_creates_new_version
  - test_modify_invalid_output_placeholder_missing
  - test_modify_claude_api_error_fallback
  - test_modify_inline_prompt_noop
  - test_modify_invalid_json_response
  - test_evaluator_optimizer_separation  (정적 검증 회귀)
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.domain.prompt.entity import DeclaredVariable, ModelDefault, PromptVersion
from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.engine.prompt_optimizer import LlmPromptModifier, _validate_required_placeholders
from style_workbench.core.errors import PromptOptimizerInvalidOutputError


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_prompt_version(
    *,
    body: str = "Studio headshot of {name}, soft key light.",
    declared_variables: list[DeclaredVariable] | None = None,
    prompt_id: str = "prm_test",
    version_id: str = "pmv_test_v1",
) -> PromptVersion:
    if declared_variables is None:
        declared_variables = [DeclaredVariable(name="name", role="subject", required=True)]
    return PromptVersion(
        id=version_id,
        prompt_id=prompt_id,
        version=1,
        body=body,
        declared_variables=declared_variables,
        model_default=None,
        parent_version_id=None,
    )


def _make_prompt(prompt_id: str = "prm_test", node_type: str = "image") -> MagicMock:
    p = MagicMock()
    p.id = prompt_id
    p.node_type = node_type
    return p


def _make_claude_output(text: str, cost_usd: float = 0.0002) -> ModelOutput:
    return ModelOutput(
        text=text,
        input_tokens=100,
        output_tokens=50,
        cost_usd=cost_usd,
    )


def _valid_llm_response(new_body: str, change_summary: str = "수정 완료") -> str:
    return json.dumps(
        {
            "new_body": new_body,
            "change_summary": change_summary,
            "preserved_placeholders": ["name"],
        },
        ensure_ascii=False,
    )


def _make_new_version(
    version_id: str = "pmv_test_v2",
    prompt_id: str = "prm_test",
    body: str = "Edited body with {name}",
) -> PromptVersion:
    return PromptVersion(
        id=version_id,
        prompt_id=prompt_id,
        version=2,
        body=body,
        declared_variables=[DeclaredVariable(name="name", role="subject", required=True)],
        model_default=None,
        parent_version_id="pmv_test_v1",
    )


def _make_optimization(opt_id: str = "po_test") -> PromptOptimization:
    return PromptOptimization(
        id=opt_id,
        prompt_id="prm_test",
        parent_version_id="pmv_test_v1",
        new_version_id="pmv_test_v2",
        retry_guidance={"instruction": "fix it"},
        failed_dimensions=["lighting_match"],
        eval_evidence=None,
        change_summary="수정 완료",
        cost_won=Decimal("280"),
        latency_ms=3000,
        succeeded=True,
        failure_reason=None,
    )


def _make_modifier(
    *,
    claude_output: ModelOutput | None = None,
    claude_error: Exception | None = None,
    new_version: PromptVersion | None = None,
    opt: PromptOptimization | None = None,
    prompt_version: PromptVersion | None = None,
    prompt: Any = None,
) -> tuple[LlmPromptModifier, AsyncMock, AsyncMock, AsyncMock]:
    """Build a LlmPromptModifier with all collaborators mocked."""
    mock_claude = AsyncMock()
    if claude_error is not None:
        mock_claude.generate.side_effect = claude_error
    elif claude_output is not None:
        mock_claude.generate.return_value = claude_output

    mock_prompt_service = AsyncMock()
    if new_version is not None:
        mock_prompt_service.create_version.return_value = new_version

    mock_optimization_repo = AsyncMock()
    if opt is not None:
        mock_optimization_repo.create.return_value = opt

    mock_prompt_version_repo = AsyncMock()
    pv = prompt_version or _make_prompt_version()
    mock_prompt_version_repo.get.return_value = pv

    mock_prompt_repo = AsyncMock()
    p = prompt or _make_prompt()
    mock_prompt_repo.get.return_value = p

    modifier = LlmPromptModifier(
        claude=mock_claude,
        prompt_service=mock_prompt_service,
        optimization_repo=mock_optimization_repo,
        prompt_version_repo=mock_prompt_version_repo,
        prompt_repo=mock_prompt_repo,
        model_id="claude-opus-4-7",
        temperature=0.2,
        max_tokens=1500,
        usd_to_won=1400.0,
    )
    return modifier, mock_prompt_service, mock_optimization_repo, mock_claude


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modify_valid_output_creates_new_version() -> None:
    """Claude 유효 응답 → 새 PromptVersion 생성 + succeeded=true row."""
    new_body = "Studio headshot of {name}, front key light."
    new_ver = _make_new_version(body=new_body)
    opt = _make_optimization()

    modifier, mock_service, mock_opt_repo, mock_claude = _make_modifier(
        claude_output=_make_claude_output(_valid_llm_response(new_body)),
        new_version=new_ver,
        opt=opt,
    )

    result_body, result_version_id = await modifier.modify(
        prompt_version_id="pmv_test_v1",
        retry_guidance={"instruction": "주광원 방향을 변경하라."},
        failed_dimensions=["lighting_match"],
    )

    assert result_version_id == "pmv_test_v2"
    assert result_body == new_body
    mock_service.create_version.assert_awaited_once()
    mock_opt_repo.create.assert_awaited_once()

    saved_opt: PromptOptimization = mock_opt_repo.create.call_args[0][0]
    assert saved_opt.succeeded is True
    assert saved_opt.new_version_id == "pmv_test_v2"
    assert saved_opt.failure_reason is None


@pytest.mark.asyncio
async def test_modify_invalid_output_placeholder_missing() -> None:
    """Claude 가 required placeholder 누락한 new_body 반환 → succeeded=false + Noop."""
    # {name} 이 없는 new_body
    bad_body = "Studio headshot of John, front key light."
    invalid_response = json.dumps(
        {
            "new_body": bad_body,
            "change_summary": "placeholder 누락",
            "preserved_placeholders": [],
        }
    )

    modifier, mock_service, mock_opt_repo, _ = _make_modifier(
        claude_output=_make_claude_output(invalid_response),
    )

    result_body, result_version_id = await modifier.modify(
        prompt_version_id="pmv_test_v1",
        retry_guidance={"instruction": "주광원 방향을 변경하라."},
        failed_dimensions=["lighting_match"],
    )

    # Noop 반환
    assert result_version_id is None
    assert result_body == ""

    # succeeded=false row 저장됨
    mock_opt_repo.create.assert_awaited_once()
    saved_opt: PromptOptimization = mock_opt_repo.create.call_args[0][0]
    assert saved_opt.succeeded is False
    assert saved_opt.failure_reason is not None
    assert "PromptOptimizerInvalidOutputError" in saved_opt.failure_reason

    # create_version 은 호출되지 않아야 함
    mock_service.create_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_modify_claude_api_error_fallback() -> None:
    """ClaudeAdapter API 오류 → succeeded=false row + Noop fallback."""
    modifier, mock_service, mock_opt_repo, _ = _make_modifier(
        claude_error=RuntimeError("Network error"),
    )

    result_body, result_version_id = await modifier.modify(
        prompt_version_id="pmv_test_v1",
        retry_guidance={"instruction": "fix"},
        failed_dimensions=["composition"],
    )

    assert result_version_id is None
    assert result_body == ""

    mock_opt_repo.create.assert_awaited_once()
    saved_opt: PromptOptimization = mock_opt_repo.create.call_args[0][0]
    assert saved_opt.succeeded is False
    assert "ClaudeAPI" in (saved_opt.failure_reason or "")

    mock_service.create_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_modify_inline_prompt_noop() -> None:
    """prompt_version_id=None (인라인 prompt) → 즉시 Noop 반환."""
    modifier, mock_service, mock_opt_repo, mock_claude = _make_modifier()

    result_body, result_version_id = await modifier.modify(
        prompt_version_id=None,
        retry_guidance={"instruction": "fix"},
        failed_dimensions=["tone_match"],
    )

    assert result_version_id is None
    assert result_body == ""

    # 어떤 collaborator 도 호출되지 않아야 함
    mock_claude.generate.assert_not_awaited()
    mock_service.create_version.assert_not_awaited()
    mock_opt_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_modify_invalid_json_response() -> None:
    """Claude 가 JSON 아닌 응답 → succeeded=false fallback."""
    modifier, mock_service, mock_opt_repo, _ = _make_modifier(
        claude_output=_make_claude_output("이건 JSON이 아닙니다."),
    )

    result_body, result_version_id = await modifier.modify(
        prompt_version_id="pmv_test_v1",
        retry_guidance={"instruction": "fix"},
        failed_dimensions=["composition"],
    )

    assert result_version_id is None
    assert result_body == ""

    mock_opt_repo.create.assert_awaited_once()
    saved_opt: PromptOptimization = mock_opt_repo.create.call_args[0][0]
    assert saved_opt.succeeded is False
    assert "InvalidJSON" in (saved_opt.failure_reason or "")

    mock_service.create_version.assert_not_awaited()


def test_evaluator_optimizer_separation() -> None:
    """engine/prompt_optimizer.py 가 evaluator 모듈을 import 하지 않음 (AC-5 정적 검증 회귀)."""
    import style_workbench.engine.prompt_optimizer as optimizer_module

    source = inspect.getsource(optimizer_module)

    # evaluator import 0건
    assert "from .evaluator" not in source, "prompt_optimizer imports evaluator (AC-5 violation)"
    assert "EVALUATOR_SYSTEM_PROMPT" not in source, (
        "prompt_optimizer references EVALUATOR_SYSTEM_PROMPT (AC-5 violation)"
    )

    # 외부 SDK import 0건 (AC-6)
    for sdk in ("anthropic", "openai", "replicate"):
        assert f"import {sdk}" not in source, (
            f"prompt_optimizer directly imports {sdk} (AC-6 violation)"
        )


def test_validate_required_placeholders_passes_when_all_present() -> None:
    """모든 required placeholder 가 new_body 에 있으면 통과."""
    _validate_required_placeholders(
        new_body="Hello {name}, your role is {role}.",
        declared_variables=[
            {"name": "name", "role": "subject", "required": True},
            {"name": "role", "role": "occupation", "required": True},
        ],
    )


def test_validate_required_placeholders_raises_on_missing() -> None:
    """required placeholder 누락 시 PromptOptimizerInvalidOutputError."""
    with pytest.raises(PromptOptimizerInvalidOutputError, match=r"\{name\}"):
        _validate_required_placeholders(
            new_body="Hello John, your role is {role}.",
            declared_variables=[
                {"name": "name", "role": "subject", "required": True},
                {"name": "role", "role": "occupation", "required": True},
            ],
        )


def test_validate_required_placeholders_optional_may_be_absent() -> None:
    """optional placeholder 가 없어도 통과."""
    _validate_required_placeholders(
        new_body="Hello {name}.",
        declared_variables=[
            {"name": "name", "role": "subject", "required": True},
            {"name": "location", "role": "place", "required": False},
        ],
    )
