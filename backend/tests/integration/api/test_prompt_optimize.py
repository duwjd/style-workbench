"""Integration tests for POST /api/prompts/{id}/optimize and
GET /api/prompts/{id}/optimizations (F02 spec §6, §10.2).

Pattern: TestClient + app.dependency_overrides (no real DB, no real LLM).

Scenarios:
  1  POST /api/prompts/{id}/optimize with evaluation_id → 200 + new_version_id
  2  POST /api/prompts/{id}/optimize with direct retry_guidance → 200
  3  POST /api/prompts/{id}/optimize with both None → 422
  4  POST /api/prompts/{id}/optimize with invalid evaluation_id → 404
  5  POST /api/prompts/{id}/optimize with F02 invalid output (mock) → 200 + succeeded=false
  6  GET /api/prompts/{id}/optimizations → pagination
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from style_workbench.api.deps import (
    get_evaluation_repo,
    get_prompt_optimization_repo,
    get_prompt_optimizer,
    get_prompt_service,
)
from style_workbench.core.errors import PromptNotFoundError
from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    NodeType,
    Prompt,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from style_workbench.infra.repositories.evaluation_repo import EvaluationRecord
from style_workbench.main import app

_NOW = datetime(2026, 5, 12, 0, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Fixtures — domain objects
# ---------------------------------------------------------------------------

_DECLARED_VARS = [DeclaredVariable(name="name", role="subject", required=True)]

_VERSION_1 = PromptVersion(
    id="pmv-v1",
    prompt_id="prm-001",
    version=1,
    body="Studio headshot of {name}.",
    declared_variables=_DECLARED_VARS,
    parent_version_id=None,
    created_at=_NOW,
)

_VERSION_2 = PromptVersion(
    id="pmv-v2",
    prompt_id="prm-001",
    version=2,
    body="Studio headshot of {name}, front key light.",
    declared_variables=_DECLARED_VARS,
    parent_version_id="pmv-v1",
    created_at=_NOW,
)

_PROMPT = Prompt(
    id="prm-001",
    name="Portrait Prompt",
    node_type=NodeType.IMAGE,
    status=PromptStatus.DRAFT,
    current_version_id="pmv-v1",
    current_version=_VERSION_1,
    created_at=_NOW,
    updated_at=_NOW,
)

_EVAL_RECORD = EvaluationRecord(
    id="eval-001",
    node_execution_id="ne-001",
    node_id="node-001",
    node_type="image",
    evaluator_model="claude-opus-4-6",
    overall_result="failed",
    dimensions=[{"name": "lighting_match", "score": 0.3, "rationale": "dark"}],
    retry_guidance={"instruction": "주광원을 변경하라.", "confidence": 0.8},
    failed_dimensions=["lighting_match"],
    created_at=_NOW,
)

_OPT_SUCCESS = PromptOptimization(
    id="po-001",
    prompt_id="prm-001",
    parent_version_id="pmv-v1",
    new_version_id="pmv-v2",
    retry_guidance={"instruction": "주광원을 변경하라.", "confidence": 0.8},
    failed_dimensions=["lighting_match"],
    eval_evidence=None,
    change_summary="주광원을 정면으로 변경했습니다.",
    cost_won=Decimal("280.00"),
    latency_ms=3500,
    succeeded=True,
    failure_reason=None,
    created_at=_NOW,
)

_OPT_FAILED = PromptOptimization(
    id="po-002",
    prompt_id="prm-001",
    parent_version_id="pmv-v1",
    new_version_id=None,
    retry_guidance={"instruction": "fix"},
    failed_dimensions=["lighting_match"],
    eval_evidence=None,
    change_summary=None,
    cost_won=Decimal("280.00"),
    latency_ms=3200,
    succeeded=False,
    failure_reason="PromptOptimizerInvalidOutputError: missing placeholder {name}",
    created_at=_NOW,
)


def _make_prompt_service_mock(
    prompt: Prompt = _PROMPT,
    usages: list[PromptUsage] | None = None,
    raise_not_found: bool = False,
) -> Any:
    mock = AsyncMock()
    if raise_not_found:
        mock.get.side_effect = PromptNotFoundError("not found")
    else:
        mock.get.return_value = prompt
    mock.list_usages.return_value = (usages or [], 0)
    return mock


def _make_eval_repo_mock(
    record: EvaluationRecord | None = _EVAL_RECORD,
) -> Any:
    mock = AsyncMock()
    mock.get_record_by_id.return_value = record
    return mock


def _make_opt_repo_mock(
    items: list[PromptOptimization] | None = None,
    total: int = 0,
) -> Any:
    mock = AsyncMock()
    effective_items = items if items is not None else []
    mock.list_for_prompt.return_value = (effective_items, total or len(effective_items))
    return mock


def _make_modifier_mock(
    result: tuple[str, str | None] = ("edited body", "pmv-v2"),
    last_cost_won: Decimal = Decimal("280"),
) -> Any:
    mock = AsyncMock(spec=LlmPromptModifier)
    mock.modify.return_value = result
    mock.last_cost_won = last_cost_won
    return mock


# ---------------------------------------------------------------------------
# Scenario 1: POST /optimize with evaluation_id — success
# ---------------------------------------------------------------------------


def test_optimize_with_evaluation_id_success() -> None:
    """Scenario 1: evaluation_id 모드 → 200 + new_version_id + succeeded=true."""
    prompt_service = _make_prompt_service_mock()
    eval_repo = _make_eval_repo_mock()
    opt_repo = _make_opt_repo_mock(items=[_OPT_SUCCESS], total=1)
    modifier = _make_modifier_mock()

    app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    app.dependency_overrides[get_evaluation_repo] = lambda: eval_repo
    app.dependency_overrides[get_prompt_optimization_repo] = lambda: opt_repo
    app.dependency_overrides[get_prompt_optimizer] = lambda: modifier

    client = TestClient(app)
    response = client.post(
        "/api/prompts/prm-001/optimize",
        json={"evaluation_id": "eval-001"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["optimization_id"] == "po-001"
    assert data["new_version_id"] == "pmv-v2"
    assert data["succeeded"] is True
    assert data["failure_reason"] is None
    assert "cost_won" in data


# ---------------------------------------------------------------------------
# Scenario 2: POST /optimize with direct retry_guidance — success
# ---------------------------------------------------------------------------


def test_optimize_direct_input_success() -> None:
    """Scenario 2: 직접 retry_guidance 입력 모드 → 200 + succeeded=true."""
    prompt_service = _make_prompt_service_mock()
    eval_repo = _make_eval_repo_mock()
    opt_repo = _make_opt_repo_mock(items=[_OPT_SUCCESS], total=1)
    modifier = _make_modifier_mock()

    app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    app.dependency_overrides[get_evaluation_repo] = lambda: eval_repo
    app.dependency_overrides[get_prompt_optimization_repo] = lambda: opt_repo
    app.dependency_overrides[get_prompt_optimizer] = lambda: modifier

    client = TestClient(app)
    response = client.post(
        "/api/prompts/prm-001/optimize",
        json={
            "retry_guidance": {"instruction": "주광원을 변경하라.", "confidence": 0.8},
            "failed_dimensions": ["lighting_match"],
            "parent_version_id": "pmv-v1",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["succeeded"] is True


# ---------------------------------------------------------------------------
# Scenario 3: POST /optimize with both None → 422
# ---------------------------------------------------------------------------


def test_optimize_both_none_returns_422() -> None:
    """Scenario 3: evaluation_id 도 retry_guidance 도 없으면 422."""
    client = TestClient(app)
    response = client.post("/api/prompts/prm-001/optimize", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Scenario 4: POST /optimize with invalid evaluation_id → 404
# ---------------------------------------------------------------------------


def test_optimize_invalid_evaluation_id_returns_404() -> None:
    """Scenario 4: 존재하지 않는 evaluation_id → 404."""
    prompt_service = _make_prompt_service_mock()
    eval_repo = _make_eval_repo_mock(record=None)
    opt_repo = _make_opt_repo_mock()
    modifier = _make_modifier_mock()

    app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    app.dependency_overrides[get_evaluation_repo] = lambda: eval_repo
    app.dependency_overrides[get_prompt_optimization_repo] = lambda: opt_repo
    app.dependency_overrides[get_prompt_optimizer] = lambda: modifier

    client = TestClient(app)
    response = client.post(
        "/api/prompts/prm-001/optimize",
        json={"evaluation_id": "eval-nonexistent"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 5: F02 invalid output (Claude mock returns {name} 누락 body)
#             → 200 + succeeded=false
# ---------------------------------------------------------------------------


def test_optimize_invalid_output_returns_200_with_succeeded_false() -> None:
    """Scenario 5: LLM invalid output → 200 + succeeded=false."""
    prompt_service = _make_prompt_service_mock()
    eval_repo = _make_eval_repo_mock()
    # modifier.modify() 가 ("", None) 반환 — Noop fallback
    modifier = _make_modifier_mock(result=("", None))
    # optimization_repo.list_for_prompt() 가 succeeded=false row 반환
    opt_repo = _make_opt_repo_mock(items=[_OPT_FAILED], total=1)

    app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    app.dependency_overrides[get_evaluation_repo] = lambda: eval_repo
    app.dependency_overrides[get_prompt_optimization_repo] = lambda: opt_repo
    app.dependency_overrides[get_prompt_optimizer] = lambda: modifier

    client = TestClient(app)
    response = client.post(
        "/api/prompts/prm-001/optimize",
        json={"evaluation_id": "eval-001"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["succeeded"] is False
    assert data["new_version_id"] is None
    assert data["failure_reason"] is not None


# ---------------------------------------------------------------------------
# Scenario 6: GET /api/prompts/{id}/optimizations → pagination
# ---------------------------------------------------------------------------


def test_list_optimizations_pagination() -> None:
    """Scenario 6: GET /optimizations → items + total + pagination meta."""
    prompt_service = _make_prompt_service_mock()
    opt_repo = _make_opt_repo_mock(items=[_OPT_SUCCESS, _OPT_FAILED], total=2)

    app.dependency_overrides[get_prompt_service] = lambda: prompt_service
    app.dependency_overrides[get_prompt_optimization_repo] = lambda: opt_repo

    client = TestClient(app)
    response = client.get("/api/prompts/prm-001/optimizations?limit=10&offset=0")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["limit"] == 10
    assert data["offset"] == 0
    # 첫 번째 item (succeeded=true)
    assert data["items"][0]["succeeded"] is True
    assert data["items"][1]["succeeded"] is False
