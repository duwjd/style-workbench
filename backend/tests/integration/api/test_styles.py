from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from style_workbench.api.deps import get_style_service
from style_workbench.core.errors import DagValidationError, StyleNotFoundError
from style_workbench.infra.repositories.style_repo import StyleVersionRecord
from style_workbench.main import app
from style_workbench.services.style_service import StyleService

_NOW = datetime(2026, 1, 1, 0, 0, 0)

_VALID_VERSION_RECORD = StyleVersionRecord(
    version_id="ver-2",
    version=2,
    current_version=2,
    created_at=_NOW,
)

_VALID_DAG_PAYLOAD: dict[str, Any] = {
    "dag": {
        "nodes": [
            {
                "id": "A",
                "type": "text_generation",
                "model": {"provider": "openai", "model_id": "gpt-4o"},
                "prompt_template": "Generate a portrait photo",
                "inputs": [],
            }
        ],
        "edges": [],
        "variables": [],
    }
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /api/styles/{style_id}/versions  — 201 happy path
# ---------------------------------------------------------------------------


def test_create_version_returns_201(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(return_value=_VALID_VERSION_RECORD)

    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/styles/style-1/versions",
            json=_VALID_DAG_PAYLOAD,
        )
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 201
    body = resp.json()
    assert body["version_id"] == "ver-2"
    assert body["version"] == 2
    assert body["current_version"] == 2


def test_create_version_passes_brief(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(return_value=_VALID_VERSION_RECORD)

    payload = {**_VALID_DAG_PAYLOAD, "brief": {"concept": "portrait"}}
    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post("/api/styles/style-1/versions", json=payload)
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 201
    call_kwargs = mock_svc.save_dag.call_args
    assert call_kwargs.kwargs.get("brief") == {"concept": "portrait"}


# ---------------------------------------------------------------------------
# POST /api/styles/{style_id}/versions  — 404 style not found
# ---------------------------------------------------------------------------


def test_create_version_404_when_style_missing(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(side_effect=StyleNotFoundError("Style 'ghost' not found"))

    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post("/api/styles/ghost/versions", json=_VALID_DAG_PAYLOAD)
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/styles/{style_id}/versions  — 422 DAG validation error
# ---------------------------------------------------------------------------


def test_create_version_422_on_dag_validation_error(client: TestClient) -> None:
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(
        side_effect=DagValidationError("DAG must contain at least one node")
    )

    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post("/api/styles/style-1/versions", json=_VALID_DAG_PAYLOAD)
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 422


def test_create_version_422_on_empty_nodes(client: TestClient) -> None:
    """Empty nodes array should be caught by domain validation and return 422."""
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(
        side_effect=DagValidationError("DAG must contain at least one node")
    )

    payload: dict[str, Any] = {
        "dag": {"nodes": [], "edges": [], "variables": []},
    }
    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post("/api/styles/style-1/versions", json=payload)
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# variable_mapping — payload preserved round-trip
# ---------------------------------------------------------------------------


_DAG_WITH_VARIABLE_MAPPING: dict[str, Any] = {
    "dag": {
        "nodes": [
            {
                "id": "A",
                "type": "text_generation",
                "model": {"provider": "openai", "model_id": "gpt-4o"},
                "prompt_template": "Hello {name}, welcome to {brand}",
                "inputs": [],
                "variable_mapping": {
                    "name": {"source": "user_input", "role": "customer_name"},
                    "brand": {"source": "constant", "value": "gemgem"},
                },
            }
        ],
        "edges": [],
        "variables": [],
    }
}


def test_create_version_with_variable_mapping_returns_201(client: TestClient) -> None:
    """POST /versions with variable_mapping should be accepted (201)."""
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(return_value=_VALID_VERSION_RECORD)

    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        resp = client.post(
            "/api/styles/style-1/versions",
            json=_DAG_WITH_VARIABLE_MAPPING,
        )
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    assert resp.status_code == 201


def test_create_version_variable_mapping_passed_to_service(client: TestClient) -> None:
    """variable_mapping in the payload must reach service.save_dag as part of the DAG."""
    mock_svc = AsyncMock(spec=StyleService)
    mock_svc.save_dag = AsyncMock(return_value=_VALID_VERSION_RECORD)

    app.dependency_overrides[get_style_service] = lambda: mock_svc
    try:
        client.post("/api/styles/style-1/versions", json=_DAG_WITH_VARIABLE_MAPPING)
    finally:
        app.dependency_overrides.pop(get_style_service, None)

    call_kwargs = mock_svc.save_dag.call_args.kwargs
    dag = call_kwargs["dag"]
    node_a = next(n for n in dag.nodes if n.id == "A")
    assert "name" in node_a.variable_mapping
    assert node_a.variable_mapping["name"].source == "user_input"
    assert node_a.variable_mapping["name"].role == "customer_name"
    assert "brand" in node_a.variable_mapping
    assert node_a.variable_mapping["brand"].source == "constant"
    assert node_a.variable_mapping["brand"].value == "gemgem"


def test_create_version_invalid_variable_mapping_source_returns_422(
    client: TestClient,
) -> None:
    """Unknown source value should be rejected by Pydantic with 422."""
    payload: dict[str, Any] = {
        "dag": {
            "nodes": [
                {
                    "id": "A",
                    "type": "text_generation",
                    "model": {"provider": "openai", "model_id": "gpt-4o"},
                    "prompt_template": "Hello {name}",
                    "inputs": [],
                    "variable_mapping": {
                        "name": {"source": "INVALID_SOURCE"},
                    },
                }
            ],
            "edges": [],
            "variables": [],
        }
    }
    # No mock needed — Pydantic validation fails before the handler runs
    resp = client.post("/api/styles/style-1/versions", json=payload)
    assert resp.status_code == 422


def test_create_version_user_input_mapping_missing_role_returns_422(
    client: TestClient,
) -> None:
    """user_input mapping without role should be rejected with 422."""
    payload: dict[str, Any] = {
        "dag": {
            "nodes": [
                {
                    "id": "A",
                    "type": "text_generation",
                    "model": {"provider": "openai", "model_id": "gpt-4o"},
                    "prompt_template": "Hello {name}",
                    "inputs": [],
                    "variable_mapping": {
                        "name": {"source": "user_input"},  # role missing
                    },
                }
            ],
            "edges": [],
            "variables": [],
        }
    }
    resp = client.post("/api/styles/style-1/versions", json=payload)
    assert resp.status_code == 422
