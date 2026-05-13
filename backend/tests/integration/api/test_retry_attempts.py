"""Integration tests — GET /api/runs/{run_id}/retry-attempts (F01 §단계 3 §3).

Scenarios:
  1. Run with FAIL → retry → PASS: attempts=2, succeeded=True.
  2. Run ID not found → 404.
  3. Run exists but 0 attempts (eval_service=None path): empty list, succeeded=None.

All external dependencies (RunService, retry_repo, eval_service) are mocked
via FastAPI dependency_overrides so no real DB or adapter is required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_retry_attempt_repo, get_run_service
from style_workbench.core.errors import RunNotFoundError
from style_workbench.domain.auto_loop.entity import RetryAttempt, RetryAttemptWithEval
from style_workbench.infra.repositories.run_repo import RunRecord
from style_workbench.main import app
from style_workbench.services.run_service import RunService

_NOW = datetime(2026, 5, 8, 3, 14, 22, tzinfo=UTC)
_LATER = datetime(2026, 5, 8, 3, 15, 1, tzinfo=UTC)
_EVEN_LATER = datetime(2026, 5, 8, 3, 15, 30, tzinfo=UTC)
_DONE = datetime(2026, 5, 8, 3, 16, 8, tzinfo=UTC)


def _make_run_record(run_id: str = "run-test-1") -> RunRecord:
    return RunRecord(
        id=run_id,
        style_version_id="ver-1",
        style_id="style-1",
        status="succeeded",
        total_cost=Decimal("25000"),
        created_at=_NOW,
        started_at=_NOW,
        finished_at=_DONE,
        node_executions=[],
    )


def _make_attempt(
    *,
    attempt_id: str,
    run_id: str,
    node_id: str,
    attempt_number: int,
    evaluation_id: str | None,
    started_at: datetime,
    finished_at: datetime | None,
    retry_guidance: dict[str, object] | None = None,
    cost_won: Decimal = Decimal("12500.00"),
) -> RetryAttempt:
    return RetryAttempt(
        id=attempt_id,
        run_id=run_id,
        node_execution_id=f"ne-{attempt_number}",
        node_id=node_id,
        attempt_number=attempt_number,
        prompt_version_id_used="pmv-01" if attempt_number == 0 else "pmv-01",
        retry_guidance=retry_guidance,
        evaluation_id=evaluation_id,
        cost_won=cost_won,
        started_at=started_at,
        finished_at=finished_at,
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Scenario 1: FAIL → retry → PASS → attempts=2, succeeded=True
# ---------------------------------------------------------------------------


def test_list_retry_attempts_fail_then_pass(client: TestClient) -> None:
    """Run with attempt 0 FAIL, attempt 1 PASS → 2 rows, succeeded=True."""
    run_id = "run-rta-1"

    attempt_0 = _make_attempt(
        attempt_id="rta-0001",
        run_id=run_id,
        node_id="img1",
        attempt_number=0,
        evaluation_id="eval-0001",
        started_at=_NOW,
        finished_at=_LATER,
        retry_guidance=None,
    )
    attempt_1 = _make_attempt(
        attempt_id="rta-0002",
        run_id=run_id,
        node_id="img1",
        attempt_number=1,
        evaluation_id="eval-0002",
        started_at=_EVEN_LATER,
        finished_at=_DONE,
        retry_guidance={"instruction": "주광원을 좌측으로 변경", "confidence": 0.82},
    )

    with_evals = [
        RetryAttemptWithEval(
            attempt=attempt_0,
            passed=False,
            failed_dimensions=["composition", "lighting"],
        ),
        RetryAttemptWithEval(
            attempt=attempt_1,
            passed=True,
            failed_dimensions=[],
        ),
    ]

    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(return_value=_make_run_record(run_id))

    mock_repo = AsyncMock()
    mock_repo.list_with_evaluations = AsyncMock(return_value=with_evals)

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    app.dependency_overrides[get_retry_attempt_repo] = lambda: mock_repo
    try:
        resp = client.get(f"/api/runs/{run_id}/retry-attempts")
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_retry_attempt_repo, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["run_id"] == run_id
    assert body["total_attempts"] == 2
    assert body["succeeded"] is True

    attempts = body["attempts"]
    assert len(attempts) == 2

    a0 = attempts[0]
    assert a0["id"] == "rta-0001"
    assert a0["node_id"] == "img1"
    assert a0["attempt_number"] == 0
    assert a0["retry_guidance"] is None
    assert a0["passed"] is False
    assert a0["failed_dimensions"] == ["composition", "lighting"]
    assert a0["evaluation_id"] == "eval-0001"

    a1 = attempts[1]
    assert a1["id"] == "rta-0002"
    assert a1["attempt_number"] == 1
    assert a1["retry_guidance"] is not None
    assert a1["retry_guidance"]["instruction"] == "주광원을 좌측으로 변경"
    assert a1["passed"] is True
    assert a1["failed_dimensions"] == []


# ---------------------------------------------------------------------------
# Scenario 2: Run not found → 404
# ---------------------------------------------------------------------------


def test_list_retry_attempts_run_not_found(client: TestClient) -> None:
    """Non-existent run_id → RunNotFoundError → 404."""
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(side_effect=RunNotFoundError("Run 'ghost-run' not found"))
    mock_repo = AsyncMock()

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    app.dependency_overrides[get_retry_attempt_repo] = lambda: mock_repo
    try:
        resp = client.get("/api/runs/ghost-run/retry-attempts")
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_retry_attempt_repo, None)

    assert resp.status_code == 404
    body = resp.json()
    assert "RunNotFoundError" in body.get("error", "")


# ---------------------------------------------------------------------------
# Scenario 3: Run exists, 0 attempts → empty list, succeeded=None
# ---------------------------------------------------------------------------


def test_list_retry_attempts_empty(client: TestClient) -> None:
    """Run exists but has no retry_attempt rows → empty list, succeeded=None.

    This can happen when eval_service=None path was used (no auto-loop).
    """
    run_id = "run-empty"

    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(return_value=_make_run_record(run_id))

    mock_repo = AsyncMock()
    mock_repo.list_with_evaluations = AsyncMock(return_value=[])

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    app.dependency_overrides[get_retry_attempt_repo] = lambda: mock_repo
    try:
        resp = client.get(f"/api/runs/{run_id}/retry-attempts")
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_retry_attempt_repo, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["run_id"] == run_id
    assert body["attempts"] == []
    assert body["total_attempts"] == 0
    assert body["succeeded"] is None
