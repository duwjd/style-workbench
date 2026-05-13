from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from style_workbench.api.deps import get_event_bus, get_run_service
from style_workbench.core.errors import RunNotFoundError
from style_workbench.engine.run_events import RunEvent, RunEventBus
from style_workbench.infra.repositories.run_repo import RunRecord
from style_workbench.main import app
from style_workbench.services.run_service import RunService

_NOW = datetime(2026, 1, 1, 0, 0, 0)


def _make_run_record(status: str = "running") -> RunRecord:
    return RunRecord(
        id="run-sse-1",
        style_version_id="ver-1",
        style_id="style-1",
        status=status,
        total_cost=None,
        created_at=_NOW,
        started_at=_NOW,
        finished_at=_NOW if status != "running" else None,
        node_executions=[],
    )


# ---------------------------------------------------------------------------
# 404 — run_id가 없을 때
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_run_events_404_when_not_found() -> None:
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(side_effect=RunNotFoundError("Run 'ghost' not found"))

    app.dependency_overrides[get_run_service] = lambda: mock_svc
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/runs/ghost/events")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_run_service, None)


# ---------------------------------------------------------------------------
# 이미 terminal 상태인 run — snapshot만 반환하고 스트림 종료
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_run_events_already_succeeded_returns_snapshot() -> None:
    succeeded_record = _make_run_record("succeeded")
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(return_value=succeeded_record)

    bus = RunEventBus()
    app.dependency_overrides[get_run_service] = lambda: mock_svc
    app.dependency_overrides[get_event_bus] = lambda: bus
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/runs/run-sse-1/events")

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        # snapshot 이벤트가 포함되어야 한다
        assert "event: snapshot" in body
        # 상태가 succeeded이므로 스트림 즉시 종료
        snapshot_line = next(
            (ln for ln in body.splitlines() if ln.startswith("data:") and "succeeded" in ln),
            None,
        )
        assert snapshot_line is not None
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_event_bus, None)


# ---------------------------------------------------------------------------
# running 상태 run — 이벤트 수신 후 terminal 이벤트에서 종료
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_run_events_receives_node_and_terminal_events() -> None:
    running_record = _make_run_record("running")
    mock_svc = AsyncMock(spec=RunService)
    mock_svc.get_run = AsyncMock(return_value=running_record)

    bus = RunEventBus()
    app.dependency_overrides[get_run_service] = lambda: mock_svc
    app.dependency_overrides[get_event_bus] = lambda: bus

    # 별도 태스크로 이벤트를 짧은 지연 후 발행
    async def _publisher() -> None:
        await asyncio.sleep(0.05)
        await bus.publish(
            RunEvent(
                run_id="run-sse-1",
                event_type="node_started",
                payload={"node_id": "n1", "node_type": "text_generation"},
            )
        )
        await asyncio.sleep(0.05)
        await bus.publish(RunEvent(run_id="run-sse-1", event_type="run_completed", payload={}))
        bus.close_run("run-sse-1")

    try:
        pub_task = asyncio.create_task(_publisher())
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await asyncio.wait_for(
                client.get("/api/runs/run-sse-1/events"),
                timeout=5.0,
            )
        await pub_task

        assert resp.status_code == 200
        body = resp.text
        assert "event: snapshot" in body
        assert "node_started" in body
        assert "run_completed" in body

        # node_started payload 검증
        node_data_line = next(
            (ln for ln in body.splitlines() if "node_started" in ln and ln.startswith("data:")),
            None,
        )
        assert node_data_line is not None
        node_payload = json.loads(node_data_line.removeprefix("data:").strip())
        assert node_payload["payload"]["node_id"] == "n1"
    finally:
        app.dependency_overrides.pop(get_run_service, None)
        app.dependency_overrides.pop(get_event_bus, None)
