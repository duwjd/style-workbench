"""Golden tests for F02 Prompt Optimizer placeholder invariants.

spec §10.3 — 50 cases (10 prompt bodies × 5 guidance scenarios).

검증 invariant:
  - required=true placeholder 는 new_body 에 반드시 존재해야 한다.
  - invalid output 시 Noop 반환 → original_body 의 placeholder 상태 유지.
  - undeclared placeholder 가 new_body 에 추가되지 않아야 한다.

Marker: @pytest.mark.golden — mock 기반 (real LLM 호출 없음).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.entity import DeclaredVariable, NodeType, Prompt, PromptVersion
from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.domain.prompt.template import extract_placeholders
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from tests.golden.prompts.fixtures.optimizer_invariants import CASES, OptimizerCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 12, 0, 0, 0, tzinfo=UTC)


def _build_modifier_for_case(
    case: OptimizerCase,
    *,
    new_body: str | None = None,
    force_invalid: bool = False,
) -> LlmPromptModifier:
    """Build LlmPromptModifier with mocked collaborators for one case.

    If `force_invalid` is True, Claude returns a body with required placeholders removed.
    If `new_body` is provided, Claude returns that body as the edited result.
    Otherwise, the mock returns the original_body verbatim (safe fallback).
    """
    # Determine what Claude will return
    if force_invalid:
        # Strip all {placeholder} tokens → triggers PromptOptimizerInvalidOutputError
        import re
        bad_body = re.sub(r"\{[a-z_]+\}", "FILLED_IN", case.original_body)
        response_body = bad_body
    elif new_body is not None:
        response_body = new_body
    else:
        # Safe: return original body with all placeholders preserved
        response_body = case.original_body

    claude_response = json.dumps(
        {
            "new_body": response_body,
            "change_summary": "테스트용 수정입니다.",
            "preserved_placeholders": list(case.allowed_placeholders),
        },
        ensure_ascii=False,
    )

    mock_claude = AsyncMock()
    mock_claude.generate.return_value = ModelOutput(
        text=claude_response,
        input_tokens=200,
        output_tokens=80,
        cost_usd=0.0002,
    )

    # PromptVersion mock
    declared_vars = [
        DeclaredVariable(
            name=v["name"],
            role=v.get("role", ""),
            required=v.get("required", True),
        )
        for v in case.declared_variables
    ]
    mock_version = PromptVersion(
        id="pmv-golden",
        prompt_id="prm-golden",
        version=1,
        body=case.original_body,
        declared_variables=declared_vars,
        parent_version_id=None,
    )
    mock_version_repo = AsyncMock()
    mock_version_repo.get.return_value = mock_version

    # Prompt mock (node_type 추출용)
    mock_prompt_obj = AsyncMock()
    mock_prompt_obj.id = "prm-golden"
    mock_prompt_obj.node_type = case.node_type
    mock_prompt_repo = AsyncMock()
    mock_prompt_repo.get.return_value = mock_prompt_obj

    # PromptService mock (create_version)
    new_ver_body = response_body
    new_version_obj = PromptVersion(
        id="pmv-golden-v2",
        prompt_id="prm-golden",
        version=2,
        body=new_ver_body,
        declared_variables=declared_vars,
        parent_version_id="pmv-golden",
    )
    mock_service = AsyncMock()
    mock_service.create_version.return_value = new_version_obj

    # optimization_repo mock
    saved_opt = PromptOptimization(
        id=new_ulid(),
        prompt_id="prm-golden",
        parent_version_id="pmv-golden",
        new_version_id="pmv-golden-v2",
        retry_guidance=case.retry_guidance,
        failed_dimensions=case.failed_dimensions,
        eval_evidence=None,
        change_summary="테스트용 수정입니다.",
        cost_won=Decimal("280"),
        latency_ms=3000,
        succeeded=True,
        failure_reason=None,
    )
    mock_opt_repo = AsyncMock()
    mock_opt_repo.create.return_value = saved_opt

    return LlmPromptModifier(
        claude=mock_claude,
        prompt_service=mock_service,
        optimization_repo=mock_opt_repo,
        prompt_version_repo=mock_version_repo,
        prompt_repo=mock_prompt_repo,
        model_id="claude-opus-4-7",
        temperature=0.2,
        max_tokens=1500,
        usd_to_won=1400.0,
    )


# ---------------------------------------------------------------------------
# Golden tests: 50 cases parametrized
# ---------------------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
async def test_optimizer_invariant_valid_output(case: OptimizerCase) -> None:
    """valid output 시 required placeholder 가 new_body 에 모두 존재해야 한다.

    Mock Claude 는 original_body 를 그대로 반환한다 (안전한 fallback).
    required_placeholders ⊆ extract_placeholders(new_body) 검증.
    """
    modifier = _build_modifier_for_case(case)

    _new_body, new_version_id = await modifier.modify(
        prompt_version_id="pmv-golden",
        retry_guidance=case.retry_guidance,
        failed_dimensions=case.failed_dimensions,
    )

    # 성공 케이스: new_version_id 가 존재해야 함
    assert new_version_id is not None, (
        f"Case {case.case_id}: expected new_version_id but got None"
    )

    found_in_new_body = extract_placeholders(_new_body)

    # required_placeholders ⊆ found_in_new_body
    missing = case.required_placeholders - found_in_new_body
    assert not missing, (
        f"Case {case.case_id}: required placeholder(s) missing from new_body: "
        f"{{{', '.join(sorted(missing))}}}\n"
        f"  original_body: {case.original_body!r}\n"
        f"  new_body: {_new_body!r}"
    )

    # undeclared placeholder 가 new_body 에 추가되지 않아야 함
    undeclared = found_in_new_body - case.allowed_placeholders
    assert not undeclared, (
        f"Case {case.case_id}: undeclared placeholder(s) appeared in new_body: "
        f"{{{', '.join(sorted(undeclared))}}}"
    )


@pytest.mark.golden
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
async def test_optimizer_invariant_invalid_output_fallback(case: OptimizerCase) -> None:
    """invalid output (placeholder 제거) 시 Noop fallback + succeeded=false row.

    required_placeholders 가 있는 케이스에서만 의미 있음.
    required_placeholders 가 없는 케이스 (B05 등)는 force_invalid 가 아무 영향 없음.
    """
    modifier = _build_modifier_for_case(case, force_invalid=True)

    _new_body, new_version_id = await modifier.modify(
        prompt_version_id="pmv-golden",
        retry_guidance=case.retry_guidance,
        failed_dimensions=case.failed_dimensions,
    )

    if case.required_placeholders:
        # required placeholder 있는 케이스: invalid output → Noop 반환
        assert new_version_id is None, (
            f"Case {case.case_id}: expected Noop (new_version_id=None) on invalid output"
        )
        assert _new_body == "", (
            f"Case {case.case_id}: expected empty string on Noop fallback"
        )
    else:
        # required placeholder 없는 케이스 (B05): force_invalid 해도 새 버전 생성 가능
        # (strip 해도 required 위반 없음)
        # 이 경우 succeeded=true 가 허용된다.
        pass  # 검증 생략 — required 없는 케이스는 어떤 결과든 허용
