from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_run_service
from style_workbench.core.errors import ConflictError, RunNotFoundError
from style_workbench.infra.repositories.run_repo import RunRecord
from style_workbench.main import app
from style_workbench.services.run_service import RunService

_NOW = datetime(2026, 1, 1, 0, 0, 0)


def _make_run_record(status: str = "aborted") -> RunRecord:
    return RunRecord(
        id="run-1",
        style_version_id="ver-1",
        style_id="style-1",
        status=status,
        total_cost=None,
        created_at=_NOW,
        started_at=_NOW,
        finished_at=_NOW if status != "running" else None,
        node_executions=[],
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/abort  — 200 happy path
# ---------------------------------------------------------------------------


def test_abort_run_returns_200(client: TestClient) -> None:
    aborted_record = _make_run_record("aborted")
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.abort = AsyncMock(return_value=aborted_record)

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        resp = client.post("/api/runs/run-1/abort")
    finally:
        app.dependency_overrides.pop(get_run_service, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "aborted"
    assert body["id"] == "run-1"


def test_abort_run_passes_reason(client: TestClient) -> None:
    aborted_record = _make_run_record("aborted")
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.abort = AsyncMock(return_value=aborted_record)

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/runs/run-1/abort",
            json={"reason": "user cancelled"},
        )
    finally:
        app.dependency_overrides.pop(get_run_service, None)

    assert resp.status_code == 200
    call_kwargs = mock_svc.abort.call_args
    assert call_kwargs.kwargs.get("reason") == "user cancelled" or (
        len(call_kwargs.args) > 1 and call_kwargs.args[1] == "user cancelled"
    )


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/abort  — 404 not found
# ---------------------------------------------------------------------------


def test_abort_run_404_when_not_found(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.abort = AsyncMock(side_effect=RunNotFoundError("Run 'ghost' not found"))

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        resp = client.post("/api/runs/ghost/abort")
    finally:
        app.dependency_overrides.pop(get_run_service, None)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/runs/{run_id}/abort  — 409 conflict (already terminal)
# ---------------------------------------------------------------------------


def test_abort_run_409_already_succeeded(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.abort = AsyncMock(
        side_effect=ConflictError("Run 'run-1' is already in terminal state 'succeeded'")
    )

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        resp = client.post("/api/runs/run-1/abort")
    finally:
        app.dependency_overrides.pop(get_run_service, None)

    assert resp.status_code == 409


def test_abort_run_409_already_aborted(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.abort = AsyncMock(
        side_effect=ConflictError("Run 'run-1' is already in terminal state 'aborted'")
    )

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        resp = client.post("/api/runs/run-1/abort")
    finally:
        app.dependency_overrides.pop(get_run_service, None)

    assert resp.status_code == 409
