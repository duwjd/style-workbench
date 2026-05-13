from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from style_workbench.core.errors import DagValidationError, StyleNotFoundError
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType
from style_workbench.infra.repositories.style_repo import (
    StyleRecord,
    StyleRepository,
    StyleVersionRecord,
)
from style_workbench.services.style_service import StyleService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, 0, 0, 0)


def _node(nid: str, template: str = "hello") -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="openai", model_id="gpt-4o"),
        prompt_template=template,
    )


def _valid_dag() -> DAG:
    return DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B")], variables=[])


def _make_style_record(version: int = 1) -> StyleRecord:
    from style_workbench.domain.style.entity import Style

    style = Style(
        id="style-1",
        name="Test",
        concept="portrait",
        vertical="biz",
        tags=[],
        status="draft",
        current_version=version,
        dag=_valid_dag(),
    )
    return StyleRecord(style=style, version_id="ver-1", created_at=_NOW)


def _make_version_record(version: int = 2) -> StyleVersionRecord:
    return StyleVersionRecord(
        version_id="ver-2",
        version=version,
        current_version=version,
        created_at=_NOW,
    )


def _make_repo(
    *,
    existing: StyleRecord | None = None,
    version_record: StyleVersionRecord | None = None,
) -> StyleRepository:
    """Build a mock StyleRepository."""
    repo = AsyncMock(spec=StyleRepository)
    repo.get = AsyncMock(return_value=existing)
    repo.create_version = AsyncMock(return_value=version_record or _make_version_record())
    return repo  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# save_dag — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_dag_creates_new_version() -> None:
    existing = _make_style_record(version=1)
    version_record = _make_version_record(version=2)
    repo = _make_repo(existing=existing, version_record=version_record)
    svc = StyleService(repo=repo)

    result = await svc.save_dag("style-1", _valid_dag())

    repo.create_version.assert_awaited_once()  # type: ignore[attr-defined]
    assert result.version == 2
    assert result.version_id == "ver-2"


@pytest.mark.asyncio
async def test_save_dag_passes_brief_to_repo() -> None:
    existing = _make_style_record(version=1)
    repo = _make_repo(existing=existing)
    svc = StyleService(repo=repo)

    brief: dict[str, Any] = {"concept": "portrait", "tone": "formal"}
    await svc.save_dag("style-1", _valid_dag(), brief=brief)

    _call_kwargs = repo.create_version.call_args  # type: ignore[attr-defined]
    assert _call_kwargs.kwargs.get("brief") == brief or _call_kwargs.args[2] == brief


# ---------------------------------------------------------------------------
# save_dag — style not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_dag_raises_not_found_when_style_missing() -> None:
    repo = _make_repo(existing=None)
    svc = StyleService(repo=repo)

    with pytest.raises(StyleNotFoundError):
        await svc.save_dag("ghost-id", _valid_dag())

    repo.create_version.assert_not_awaited()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# save_dag — DAG validation failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_dag_rejects_empty_nodes() -> None:
    existing = _make_style_record(version=1)
    repo = _make_repo(existing=existing)
    svc = StyleService(repo=repo)

    empty_dag = DAG(nodes=[], edges=[], variables=[])
    with pytest.raises(DagValidationError, match="at least one node"):
        await svc.save_dag("style-1", empty_dag)

    repo.create_version.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_save_dag_rejects_cyclic_dag() -> None:
    existing = _make_style_record(version=1)
    repo = _make_repo(existing=existing)
    svc = StyleService(repo=repo)

    cyclic_dag = DAG(
        nodes=[_node("A"), _node("B")],
        edges=[Edge("A", "B"), Edge("B", "A")],
        variables=[],
    )
    with pytest.raises(DagValidationError):
        await svc.save_dag("style-1", cyclic_dag)

    repo.create_version.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_save_dag_rejects_dangling_edge() -> None:
    existing = _make_style_record(version=1)
    repo = _make_repo(existing=existing)
    svc = StyleService(repo=repo)

    dangling_dag = DAG(
        nodes=[_node("A")],
        edges=[Edge("A", "GHOST")],
        variables=[],
    )
    with pytest.raises(DagValidationError):
        await svc.save_dag("style-1", dangling_dag)


@pytest.mark.asyncio
async def test_save_dag_rejects_undefined_placeholder() -> None:
    existing = _make_style_record(version=1)
    repo = _make_repo(existing=existing)
    svc = StyleService(repo=repo)

    undeclared_var_dag = DAG(
        nodes=[_node("A", template="Hello {name}")],
        edges=[],
        variables=[],  # 'name' not declared
    )
    with pytest.raises(DagValidationError):
        await svc.save_dag("style-1", undeclared_var_dag)
