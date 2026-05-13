"""Integration tests for Evaluation API endpoints.

실제 DB 없이 FastAPI TestClient + dependency_overrides 로 HTTP 계층만 검증한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_evaluation_service
from style_workbench.core.errors import EvaluationNotFoundError
from style_workbench.infra.repositories.evaluation_repo import EvaluationRecord
from style_workbench.main import app
from style_workbench.services.evaluation_service import EvaluationService

_NOW = datetime(2026, 1, 1, tzinfo=UTC)

_DIMS: list[dict[str, object]] = [{"name": "tone_match", "score": 0.9, "rationale": "Good tone"}]


def _make_eval_record(
    evaluation_id: str = "eval-1",
    human_verdict: str | None = None,
    human_comment: str | None = None,
) -> EvaluationRecord:
    return EvaluationRecord(
        id=evaluation_id,
        node_execution_id="ne-1",
        node_id="node-1",
        node_type="text_generation",
        evaluator_model="claude-opus-4-6",
        overall_result="passed",
        dimensions=list(_DIMS),
        retry_guidance=None,
        human_verdict=human_verdict,
        human_comment=human_comment,
        created_at=_NOW,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/evaluations/{evaluation_id}/verdict — 200 happy path
# ---------------------------------------------------------------------------


def test_submit_verdict_approved_returns_200(client: TestClient) -> None:
    updated_record = _make_eval_record(human_verdict="approved", human_comment="LGTM")
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.update_human_verdict = AsyncMock(return_value=updated_record)

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/evaluations/eval-1/verdict",
            json={"verdict": "approved", "comment": "LGTM"},
        )
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "eval-1"
    assert body["human_verdict"] == "approved"
    assert body["human_comment"] == "LGTM"


def test_submit_verdict_rejected_no_comment(client: TestClient) -> None:
    updated_record = _make_eval_record(human_verdict="rejected")
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.update_human_verdict = AsyncMock(return_value=updated_record)

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/evaluations/eval-1/verdict",
            json={"verdict": "rejected"},
        )
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["human_verdict"] == "rejected"


def test_submit_verdict_invalid_value_returns_422(client: TestClient) -> None:
    """Pydantic Literal 검증 — "pending" 은 허용 안 됨."""
    mock_svc = AsyncMock(spec=EvaluationService)
    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/evaluations/eval-1/verdict",
            json={"verdict": "pending"},
        )
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/evaluations/{evaluation_id}/verdict — 404
# ---------------------------------------------------------------------------


def test_submit_verdict_not_found_returns_404(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.update_human_verdict = AsyncMock(
        side_effect=EvaluationNotFoundError("Evaluation 'ghost' not found")
    )

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/evaluations/ghost/verdict",
            json={"verdict": "approved"},
        )
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/evaluations
# ---------------------------------------------------------------------------


def test_list_run_evaluations_returns_200(client: TestClient) -> None:
    records = [_make_eval_record("eval-1"), _make_eval_record("eval-2")]
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.list_by_run = AsyncMock(return_value=records)

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.get("/api/runs/run-1/evaluations")
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2
    assert body[0]["id"] == "eval-1"
    assert body[1]["id"] == "eval-2"


def test_list_run_evaluations_empty_returns_empty_list(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.list_by_run = AsyncMock(return_value=[])

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.get("/api/runs/run-no-evals/evaluations")
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_run_evaluations_response_schema(client: TestClient) -> None:
    """응답 필드가 snake_case 이고 필수 키를 포함하는지 검증."""
    record = _make_eval_record()
    mock_svc = AsyncMock(spec=EvaluationService)
    mock_svc.list_by_run = AsyncMock(return_value=[record])

    app.dependency_overrides[get_evaluation_service] = lambda: mock_svc
    try:
        resp = client.get("/api/runs/run-1/evaluations")
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)

    item = resp.json()[0]
    expected_keys = {
        "id",
        "node_execution_id",
        "node_id",
        "node_type",
        "evaluator_model",
        "overall_result",
        "dimensions",
        "retry_guidance",
        "failed_dimensions",
        "human_verdict",
        "human_comment",
        "created_at",
    }
    assert expected_keys.issubset(set(item.keys()))
