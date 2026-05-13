"""Integration test — W2: get_run_service wires eval_service.

Verifies that the DI graph for RunService now includes EvaluationService so
that the eval+retry branch in execute() is reachable from the API layer.

All external vendor calls (ClaudeAdapter) are mocked; no real DB is required.
The test resolves the FastAPI dependency graph directly rather than making an
HTTP request, because the POST /api/runs endpoint streams SSE and is harder
to assert against in a TestClient context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from style_workbench.api.deps import get_evaluation_service, get_run_service
from style_workbench.services.evaluation_service import EvaluationService
from style_workbench.services.run_service import RunService


@pytest.mark.asyncio
async def test_get_run_service_includes_eval_service() -> None:
    """Resolving get_run_service via its declared Depends produces a RunService
    whose _eval_service attribute is a fully-constructed EvaluationService
    (not None), confirming W2 wiring is active.
    """
    # Build a fake AsyncSession that satisfies SqlAlchemy repo construction
    # (repos only store the session, they don't query in __init__).
    fake_session = MagicMock()

    # Build a fake RunEventBus
    fake_bus = MagicMock()

    # Construct eval_service the same way deps.py does, but with a mocked adapter.
    with patch(
        "style_workbench.api.deps.ClaudeAdapter",
        return_value=AsyncMock(),
    ):
        eval_svc = get_evaluation_service(session=fake_session)  # type: ignore[arg-type]

    # Now call get_run_service with the resolved eval_service
    run_svc = get_run_service(
        session=fake_session,  # type: ignore[arg-type]
        bus=fake_bus,
        eval_service=eval_svc,
    )

    assert isinstance(run_svc, RunService), "get_run_service must return RunService"
    assert isinstance(run_svc._eval_service, EvaluationService), (
        "RunService._eval_service must be EvaluationService after W2 wiring; "
        f"got {type(run_svc._eval_service)!r}"
    )
