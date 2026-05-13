"""Integration tests for POST /api/prompts/{id}/ab (spec §10.2, 단계 5).

Scenarios:
  1. POST /api/prompts/{id}/ab → 200, response contains ab_id / from_run_id / to_run_id.
  2. Unknown prompt_id → 404.
  3. from_version == to_version → 422 (meaningless A/B, spec §10.2 시나리오 3).
  4. style_version_id not linked to prompt → 422.

Pattern: TestClient + app.dependency_overrides (no real DB).
         PromptService and RunService are mocked via AsyncMock(spec=...).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_prompt_service, get_run_service
from style_workbench.core.errors import (
    PromptAbSameVersionError,
    PromptNotFoundError,
    StyleVersionHasNoPromptNodeError,
)
from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    NodeType,
    Prompt,
    PromptAbComparison,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.main import app
from style_workbench.services.prompt_service import PromptService
from style_workbench.services.run_service import RunService

_NOW = datetime(2026, 5, 12, 0, 0, 0, tzinfo=UTC)

_DECLARED_VARS = [
    DeclaredVariable(name="name", role="person_name", required=True),
    DeclaredVariable(name="role", role="job_title", required=True),
]

_VERSION_1 = PromptVersion(
    id="pmv-001",
    prompt_id="prm-001",
    version=1,
    body="Hello {name}, role: {role}.",
    declared_variables=_DECLARED_VARS,
    created_at=_NOW,
    created_by="user:test",
)

_VERSION_2 = PromptVersion(
    id="pmv-002",
    prompt_id="prm-001",
    version=2,
    body="Greetings {name}, your role is {role}.",
    declared_variables=_DECLARED_VARS,
    parent_version_id="pmv-001",
    created_at=_NOW,
    created_by="user:test",
)

_PROMPT = Prompt(
    id="prm-001",
    name="Portrait greeting",
    node_type=NodeType.TEXT,
    status=PromptStatus.APPROVED,
    owner="designer:test",
    current_version_id="pmv-001",
    tags=["portrait"],
    created_at=_NOW,
    updated_at=_NOW,
    current_version=_VERSION_1,
)

_AB = PromptAbComparison(
    id="ab-0001",
    prompt_id="prm-001",
    from_version_id="pmv-001",
    to_version_id="pmv-002",
    style_version_id="stv-001",
    user_input={"name": "Alice", "role": "CEO"},
    from_run_id="run-from-001",
    to_run_id="run-to-001",
    status="done",
    created_at=_NOW,
    started_at=_NOW,
    finished_at=_NOW,
)

_USAGE = PromptUsage(
    id="pmu-001",
    prompt_id="prm-001",
    prompt_version_id="pmv-001",
    style_version_id="stv-001",
    node_id="txt1",
    pinned=False,
    created_at=_NOW,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prompt_service(**overrides: Any) -> AsyncMock:
    svc = AsyncMock(spec=PromptService)
    svc.get = AsyncMock(return_value=_PROMPT)
    svc.get_version = AsyncMock(side_effect=[_VERSION_1, _VERSION_2])
    svc.list_usages = AsyncMock(return_value=([_USAGE], 1))
    svc.trigger_ab = AsyncMock(return_value=_AB)
    svc._version_repo = AsyncMock()
    svc._version_repo.get = AsyncMock(side_effect=[_VERSION_1, _VERSION_2])
    for key, val in overrides.items():
        setattr(svc, key, AsyncMock(return_value=val) if not isinstance(val, AsyncMock) else val)
    return svc


def _make_run_service() -> AsyncMock:
    rs = AsyncMock(spec=RunService)
    from_run = AsyncMock()
    from_run.id = "run-from-001"
    to_run = AsyncMock()
    to_run.id = "run-to-001"
    rs.execute = AsyncMock(side_effect=[from_run, to_run])
    return rs


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Scenario 1: successful A/B trigger
# ---------------------------------------------------------------------------


def test_ab_compare_returns_ab_id_and_run_ids(client: TestClient) -> None:
    """Scenario 1: POST /api/prompts/{id}/ab → 200 with ab_id, from_run_id, to_run_id."""
    svc = _make_prompt_service()
    rs = _make_run_service()

    app.dependency_overrides[get_prompt_service] = lambda: svc
    app.dependency_overrides[get_run_service] = lambda: rs

    try:
        resp = client.post(
            "/api/prompts/prm-001/ab",
            json={
                "from_version": "pmv-001",
                "to_version": "pmv-002",
                "style_version_id": "stv-001",
                "user_input": {"name": "Alice", "role": "CEO"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "ab_id" in data
    assert "from_run_id" in data
    assert "to_run_id" in data
    assert "status" in data
    assert data["from_run_id"] == "run-from-001"
    assert data["to_run_id"] == "run-to-001"
    assert data["status"] in {"running", "done"}

    # trigger_ab must have been called once
    svc.trigger_ab.assert_awaited_once()


# ---------------------------------------------------------------------------
# Scenario 2: unknown prompt_id → 404
# ---------------------------------------------------------------------------


def test_ab_compare_unknown_prompt_returns_404(client: TestClient) -> None:
    """Scenario 2: Prompt not found → 404."""
    svc = _make_prompt_service()
    svc.trigger_ab = AsyncMock(side_effect=PromptNotFoundError("Prompt 'ghost' not found"))
    svc._version_repo.get = AsyncMock(return_value=_VERSION_1)

    rs = _make_run_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    app.dependency_overrides[get_run_service] = lambda: rs

    try:
        resp = client.post(
            "/api/prompts/ghost/ab",
            json={
                "from_version": "pmv-001",
                "to_version": "pmv-002",
                "style_version_id": "stv-001",
                "user_input": {},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Scenario 3: same from/to version → 422
# ---------------------------------------------------------------------------


def test_ab_compare_same_version_returns_422(client: TestClient) -> None:
    """Scenario 3: from_version == to_version → 422 (meaningless comparison)."""
    svc = _make_prompt_service()
    svc.trigger_ab = AsyncMock(
        side_effect=PromptAbSameVersionError(
            "from_version_id and to_version_id are the same: 'pmv-001'."
        )
    )

    rs = _make_run_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    app.dependency_overrides[get_run_service] = lambda: rs

    try:
        resp = client.post(
            "/api/prompts/prm-001/ab",
            json={
                "from_version": "pmv-001",
                "to_version": "pmv-001",  # same!
                "style_version_id": "stv-001",
                "user_input": {},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Scenario 4: style_version not linked → 422
# ---------------------------------------------------------------------------


def test_ab_compare_style_not_linked_returns_422(client: TestClient) -> None:
    """Scenario 4: style_version_id has no node referencing this prompt → 422."""
    svc = _make_prompt_service()
    svc.trigger_ab = AsyncMock(
        side_effect=StyleVersionHasNoPromptNodeError(
            "StyleVersion 'stv-999' has no node referencing prompt 'prm-001'."
        )
    )

    rs = _make_run_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    app.dependency_overrides[get_run_service] = lambda: rs

    try:
        resp = client.post(
            "/api/prompts/prm-001/ab",
            json={
                "from_version": "pmv-001",
                "to_version": "pmv-002",
                "style_version_id": "stv-999",  # not linked
                "user_input": {},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422, resp.text
