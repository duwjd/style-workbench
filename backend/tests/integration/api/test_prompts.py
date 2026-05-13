"""Integration tests for the Prompt Library API (F05, 단계 2 + 목록 endpoint).

Exit criteria: spec §13 단계 2 (8 scenarios) + GET /api/prompts/{id}/versions (3 scenarios).

Pattern: TestClient + app.dependency_overrides (mirrors test_styles.py).
No real DB required — all repository calls are mocked via AsyncMock(spec=PromptService).

Scenarios:
    1  POST /api/prompts → 201 + ETag header
    2  PUT /api/prompts/{id} with valid If-Match → 200
    3  PUT /api/prompts/{id} without If-Match → 412
    4  POST /api/prompts/{id}/versions → 201, version incremented, parent_version_id set
    5  POST /api/prompts/{id}/versions/{v}/promote → current_version_id updated
    6  GET /api/prompts?q=...&tags=...&status=...&node_type=...
    7  POST /api/prompts/{id}/versions with undeclared placeholder → 422
    8  POST /api/prompts/{id}/versions on deprecated prompt → 422
    9  GET /api/prompts/{id}/versions → items 3건, total=3, version DESC 정렬
    10 GET /api/prompts/{id}/versions?limit=2&offset=0 → items 2건 (pagination)
    11 GET /api/prompts/{unknown}/versions → 404
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_prompt_service
from style_workbench.api.schemas.prompts import compute_etag
from style_workbench.core.errors import MissingDeclaredVariableError, PromptDeprecatedError
from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    ModelDefault,
    NodeType,
    Prompt,
    PromptFilters,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.main import app
from style_workbench.services.prompt_service import PromptService

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 11, 13, 0, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Fixtures — domain objects
# ---------------------------------------------------------------------------

_DECLARED_VARS = [
    DeclaredVariable(name="name", role="person_name", required=True),
    DeclaredVariable(name="role", role="job_title", required=True),
]

_VERSION_1 = PromptVersion(
    id="pmv-001",
    prompt_id="prm-001",
    version=1,
    body="Hello {name}, your role is {role}.",
    declared_variables=_DECLARED_VARS,
    model_default=ModelDefault(provider="openai", model_id="gpt-5.4"),
    parent_version_id=None,
    change_note="initial",
    created_at=_NOW,
    created_by="user:test",
)

_VERSION_2 = PromptVersion(
    id="pmv-002",
    prompt_id="prm-001",
    version=2,
    body="Greetings {name}, serving as {role}.",
    declared_variables=_DECLARED_VARS,
    model_default=None,
    parent_version_id="pmv-001",
    change_note="tone adjustment",
    created_at=_LATER,
    created_by="user:test",
)

_PROMPT = Prompt(
    id="prm-001",
    name="Business portrait greeting",
    node_type=NodeType.TEXT,
    status=PromptStatus.DRAFT,
    owner="designer:jiwon",
    current_version_id="pmv-001",
    tags=["portrait", "professional"],
    created_at=_NOW,
    updated_at=_NOW,
    current_version=_VERSION_1,
)

_PROMPT_APPROVED = Prompt(
    id="prm-002",
    name="Approved prompt",
    node_type=NodeType.IMAGE,
    status=PromptStatus.APPROVED,
    owner=None,
    current_version_id="pmv-001",
    tags=[],
    created_at=_NOW,
    updated_at=_NOW,
    current_version=_VERSION_1,
)

_USAGE = PromptUsage(
    id="pmu-001",
    prompt_id="prm-001",
    prompt_version_id="pmv-001",
    style_version_id="stv-001",
    node_id="txt1",
    pinned=False,
    last_run_score=0.84,
    created_at=_NOW,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_mock_service(**overrides: Any) -> AsyncMock:
    """Build an AsyncMock(spec=PromptService) with sensible defaults."""
    svc = AsyncMock(spec=PromptService)
    svc.create = AsyncMock(return_value=_PROMPT)
    svc.get = AsyncMock(return_value=_PROMPT)
    svc.update_meta = AsyncMock(return_value=_PROMPT)
    svc.list_prompts = AsyncMock(return_value=[_PROMPT])
    svc.create_version = AsyncMock(return_value=_VERSION_2)
    svc.get_version = AsyncMock(return_value=_VERSION_1)
    svc.promote_version = AsyncMock(return_value=_PROMPT)
    svc.list_usages = AsyncMock(return_value=([_USAGE], 1))
    svc.list_versions = AsyncMock(return_value=([_VERSION_2, _VERSION_1], 2))
    for key, val in overrides.items():
        setattr(svc, key, AsyncMock(return_value=val) if not isinstance(val, AsyncMock) else val)
    return svc


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Scenario 1: POST /api/prompts → 201 + ETag
# ---------------------------------------------------------------------------


def test_create_prompt_returns_201_and_etag(client: TestClient) -> None:
    """Scenario 1: New prompt → 201 with ETag header."""
    svc = _make_mock_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.post(
            "/api/prompts",
            json={
                "name": "Business portrait greeting",
                "node_type": "text",
                "body": "Hello {name}, your role is {role}.",
                "declared_variables": [
                    {"name": "name", "role": "person_name", "required": True},
                    {"name": "role", "role": "job_title", "required": True},
                ],
                "owner": "designer:jiwon",
                "tags": ["portrait", "professional"],
            },
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "prm-001"
    assert body["name"] == "Business portrait greeting"
    assert body["node_type"] == "text"
    assert body["status"] == "draft"
    assert "ETag" in resp.headers
    etag = resp.headers["ETag"]
    assert etag.startswith('W/"'), f"ETag should be weak: {etag}"


# ---------------------------------------------------------------------------
# Scenario 2: PUT /api/prompts/{id} with valid If-Match → 200
# ---------------------------------------------------------------------------


def test_update_prompt_meta_with_if_match_returns_200(client: TestClient) -> None:
    """Scenario 2: PUT with correct ETag → 200, name updated."""
    svc = _make_mock_service()
    valid_etag = compute_etag(_NOW)
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.put(
            "/api/prompts/prm-001",
            json={"name": "Updated Name", "tags": ["updated"]},
            headers={"If-Match": valid_etag},
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 200, resp.text
    svc.update_meta.assert_called_once()
    call_kwargs = svc.update_meta.call_args.kwargs
    assert call_kwargs.get("name") == "Updated Name"
    assert call_kwargs.get("tags") == ["updated"]


# ---------------------------------------------------------------------------
# Scenario 3: PUT without If-Match → 412
# ---------------------------------------------------------------------------


def test_update_prompt_meta_without_if_match_returns_412(client: TestClient) -> None:
    """Scenario 3: Missing If-Match → 412 PreconditionFailed."""
    svc = _make_mock_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.put(
            "/api/prompts/prm-001",
            json={"name": "Will not apply"},
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 412, resp.text
    body = resp.json()
    assert body["error"] == "PreconditionFailedError"


# ---------------------------------------------------------------------------
# Scenario 4: POST /api/prompts/{id}/versions → 201, version=2, parent set
# ---------------------------------------------------------------------------


def test_create_version_returns_201_with_parent(client: TestClient) -> None:
    """Scenario 4: New version → 201, version increments, parent_version_id set."""
    svc = _make_mock_service()
    valid_etag = compute_etag(_NOW)
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.post(
            "/api/prompts/prm-001/versions",
            json={
                "body": "Greetings {name}, serving as {role}.",
                "declared_variables": [
                    {"name": "name", "role": "person_name", "required": True},
                    {"name": "role", "role": "job_title", "required": True},
                ],
                "change_note": "tone adjustment",
            },
            headers={"If-Match": valid_etag},
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "version" in body
    version_data = body["version"]
    assert version_data["version"] == 2
    assert version_data["parent_version_id"] == "pmv-001"


# ---------------------------------------------------------------------------
# Scenario 5: POST /api/prompts/{id}/versions/{v}/promote → current_version updated
# ---------------------------------------------------------------------------


def test_promote_version_updates_current(client: TestClient) -> None:
    """Scenario 5: Promote v1 → current_version_id changes."""
    promoted_prompt = Prompt(
        id="prm-001",
        name="Business portrait greeting",
        node_type=NodeType.TEXT,
        status=PromptStatus.DRAFT,
        owner="designer:jiwon",
        current_version_id="pmv-001",
        tags=["portrait"],
        created_at=_NOW,
        updated_at=_LATER,
        current_version=_VERSION_1,
    )
    svc = _make_mock_service()
    svc.promote_version = AsyncMock(return_value=promoted_prompt)
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.post("/api/prompts/prm-001/versions/1/promote")
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # current_version should be the promoted version
    assert body["current_version"]["version"] == 1
    svc.promote_version.assert_called_once_with(prompt_id="prm-001", version_id="pmv-001")


# ---------------------------------------------------------------------------
# Scenario 6: GET /api/prompts with search/filter parameters
# ---------------------------------------------------------------------------


def test_list_prompts_with_filters(client: TestClient) -> None:
    """Scenario 6: Search by q, tags, status, node_type."""
    svc = _make_mock_service()
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.get(
            "/api/prompts",
            params={
                "q": "portrait",
                "tags": "professional,korean",
                "status": "draft",
                "node_type": "text",
                "limit": "10",
                "offset": "0",
            },
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert body["limit"] == 10

    # Validate that the filter was passed correctly to the service
    assert svc.list_prompts.call_count >= 1
    call_args = svc.list_prompts.call_args_list[0]
    filters: PromptFilters = call_args.args[0]
    assert filters.node_type == NodeType.TEXT
    assert filters.status == PromptStatus.DRAFT
    assert filters.q == "portrait"
    assert "professional" in filters.tags
    assert "korean" in filters.tags


# ---------------------------------------------------------------------------
# Scenario 7: declared_variables missing → 422 MissingDeclaredVariableError
# ---------------------------------------------------------------------------


def test_create_version_missing_declared_variable_returns_422(client: TestClient) -> None:
    """Scenario 7: Body has {title} but declared_variables only has {name} → 422."""
    svc = _make_mock_service()
    # Override create_version to raise the domain error
    svc.create_version = AsyncMock(
        side_effect=MissingDeclaredVariableError(
            "Prompt body contains placeholder(s) not declared in declared_variables: title"
        )
    )
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.post(
            "/api/prompts/prm-001/versions",
            json={
                "body": "Hello {name}, your title is {title}.",
                "declared_variables": [
                    {"name": "name", "role": "person_name", "required": True}
                    # {title} is NOT declared — should cause 422
                ],
                "change_note": "test",
            },
            headers={"If-Match": compute_etag(_NOW)},
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"] == "MissingDeclaredVariableError"


# ---------------------------------------------------------------------------
# Scenario 8: deprecated prompt → 422 PromptDeprecatedError on new version
# ---------------------------------------------------------------------------


def test_create_version_on_deprecated_prompt_returns_422(client: TestClient) -> None:
    """Scenario 8: Creating a version on a deprecated prompt → 422."""
    deprecated_prompt = Prompt(
        id="prm-dep",
        name="Old Prompt",
        node_type=NodeType.TEXT,
        status=PromptStatus.DEPRECATED,
        owner=None,
        current_version_id="pmv-001",
        tags=[],
        created_at=_NOW,
        updated_at=_NOW,
        current_version=_VERSION_1,
    )
    svc = _make_mock_service()
    svc.get = AsyncMock(return_value=deprecated_prompt)
    svc.create_version = AsyncMock(
        side_effect=PromptDeprecatedError("Cannot create version on deprecated prompt 'prm-dep'")
    )
    valid_etag = compute_etag(_NOW)
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.post(
            "/api/prompts/prm-dep/versions",
            json={
                "body": "New body for {name}.",
                "declared_variables": [{"name": "name", "role": "person_name", "required": True}],
            },
            headers={"If-Match": valid_etag},
        )
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"] == "PromptDeprecatedError"


# ---------------------------------------------------------------------------
# Bonus: POST /api/prompts/{id}/ab — 단계 5 구현 완료 (smoke check)
# ---------------------------------------------------------------------------


def test_ab_endpoint_requires_body(client: TestClient) -> None:
    """A/B endpoint (단계 5): posting without a body returns 422, not 501.

    The endpoint is now implemented; posting without the required body fields
    returns 422 Unprocessable Entity from FastAPI's request validation.
    Full A/B scenarios are in tests/integration/api/test_prompt_ab.py.
    """
    resp = client.post("/api/prompts/prm-001/ab")
    # 422 = FastAPI request validation (missing required fields)
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Bonus: POST /api/prompts/import-modules → 501 placeholder
# ---------------------------------------------------------------------------


def test_import_modules_returns_501(client: TestClient) -> None:
    """import-modules endpoint is a 501 placeholder until 단계 4."""
    resp = client.post("/api/prompts/import-modules")
    assert resp.status_code == 501, resp.text


# ---------------------------------------------------------------------------
# Scenario 9: GET /api/prompts/{id}/versions → items N건, total, version DESC
# ---------------------------------------------------------------------------

_VERSION_3 = PromptVersion(
    id="pmv-003",
    prompt_id="prm-001",
    version=3,
    body="Hey {name}, you are a {role} professional.",
    declared_variables=_DECLARED_VARS,
    model_default=None,
    parent_version_id="pmv-002",
    change_note="third revision",
    created_at=datetime(2026, 5, 11, 14, 0, 0, tzinfo=UTC),
    created_by="user:test",
)


def test_list_versions_returns_all_items_version_desc(client: TestClient) -> None:
    """Scenario 9: 3 versions exist → items 3건, total=3, version DESC."""
    # Service returns versions in DESC order (newest first)
    versions_desc = [_VERSION_3, _VERSION_2, _VERSION_1]
    svc = _make_mock_service()
    svc.list_versions = AsyncMock(return_value=(versions_desc, 3))
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.get("/api/prompts/prm-001/versions")
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["limit"] == 50
    assert body["offset"] == 0

    # Verify version DESC order
    versions_in_response = [item["version"] for item in body["items"]]
    assert versions_in_response == [3, 2, 1], f"Expected [3,2,1] got {versions_in_response}"

    # Verify body is included (needed for A/B diff rendering)
    assert "body" in body["items"][0]
    assert body["items"][0]["body"] == _VERSION_3.body

    # Verify service was called with correct args
    svc.list_versions.assert_called_once_with("prm-001", limit=50, offset=0)


# ---------------------------------------------------------------------------
# Scenario 10: Pagination — limit=2, offset=0 → items 2건
# ---------------------------------------------------------------------------


def test_list_versions_pagination_limit(client: TestClient) -> None:
    """Scenario 10: limit=2 → 2 items, total still reflects full count."""
    versions_page = [_VERSION_3, _VERSION_2]
    svc = _make_mock_service()
    svc.list_versions = AsyncMock(return_value=(versions_page, 3))
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.get("/api/prompts/prm-001/versions", params={"limit": 2, "offset": 0})
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3  # total reflects all versions, not just this page
    assert body["limit"] == 2
    assert body["offset"] == 0

    svc.list_versions.assert_called_once_with("prm-001", limit=2, offset=0)


# ---------------------------------------------------------------------------
# Scenario 11: Unknown prompt → 404
# ---------------------------------------------------------------------------


def test_list_versions_unknown_prompt_returns_404(client: TestClient) -> None:
    """Scenario 11: prompt does not exist → 404."""
    from style_workbench.core.errors import PromptNotFoundError

    svc = _make_mock_service()
    svc.list_versions = AsyncMock(side_effect=PromptNotFoundError("Prompt 'prm-unknown' not found"))
    app.dependency_overrides[get_prompt_service] = lambda: svc
    try:
        resp = client.get("/api/prompts/prm-unknown/versions")
    finally:
        app.dependency_overrides.pop(get_prompt_service, None)

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error"] == "PromptNotFoundError"
