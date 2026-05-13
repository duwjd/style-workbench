"""Unit tests for infra/repositories/prompt_repo.py.

Uses AsyncMock session — no DB connection required.
Validates ORM ↔ domain entity mapping and query dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from style_workbench.domain.prompt.entity import (
    NodeType,
    Prompt,
    PromptStatus,
    PromptVersion,
)
from style_workbench.infra.repositories.prompt_repo import (
    SqlAlchemyPromptRepo,
    SqlAlchemyPromptUsageRepo,
    SqlAlchemyPromptVersionRepo,
    _jsonb_to_declared_vars,
    _jsonb_to_model_default,
    _orm_to_prompt,
    _orm_to_prompt_usage,
    _orm_to_prompt_version,
)

_NOW = datetime(2026, 5, 11, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Helpers: build ORM-like MagicMocks
# ---------------------------------------------------------------------------


def _make_prompt_orm(
    pid: str = "prm-1",
    name: str = "Test",
    node_type: str = "text",
    status: str = "draft",
    current_version_id: str | None = "pmv-1",
    tags: list[str] | None = None,
    imported_from: str | None = None,
) -> MagicMock:
    orm = MagicMock()
    orm.id = pid
    orm.name = name
    orm.node_type = node_type
    orm.status = status
    orm.owner = None
    orm.current_version_id = current_version_id
    orm.tags = tags or ["test"]
    orm.imported_from = imported_from
    orm.created_at = _NOW
    orm.updated_at = _NOW
    orm.current_version = None
    return orm


def _make_version_orm(
    vid: str = "pmv-1",
    prompt_id: str = "prm-1",
    version: int = 1,
    body: str = "Hello {name}",
    declared_variables: list[dict[str, Any]] | None = None,
    model_default: dict[str, Any] | None = None,
    parent_version_id: str | None = None,
) -> MagicMock:
    orm = MagicMock()
    orm.id = vid
    orm.prompt_id = prompt_id
    orm.version = version
    orm.body = body
    orm.declared_variables = declared_variables or [{"name": "name", "role": "", "required": True}]
    orm.model_default = model_default
    orm.parent_version_id = parent_version_id
    orm.change_note = None
    orm.created_at = _NOW
    orm.created_by = None
    return orm


def _make_usage_orm(
    uid: str = "use-1",
    prompt_id: str = "prm-1",
    prompt_version_id: str = "pmv-1",
    style_version_id: str = "stv-1",
    node_id: str = "txt1",
    pinned: bool = False,
    last_run_score: Decimal | None = None,
) -> MagicMock:
    orm = MagicMock()
    orm.id = uid
    orm.prompt_id = prompt_id
    orm.prompt_version_id = prompt_version_id
    orm.style_version_id = style_version_id
    orm.node_id = node_id
    orm.pinned = pinned
    orm.last_run_score = last_run_score
    orm.last_run_at = None
    orm.created_at = _NOW
    return orm


# ---------------------------------------------------------------------------
# JSONB helpers
# ---------------------------------------------------------------------------


def test_jsonb_to_declared_vars_round_trip() -> None:
    raw = [{"name": "x", "role": "job", "required": False}]
    result = _jsonb_to_declared_vars(raw)
    assert len(result) == 1
    assert result[0].name == "x"
    assert result[0].role == "job"
    assert result[0].required is False


def test_jsonb_to_declared_vars_empty() -> None:
    assert _jsonb_to_declared_vars([]) == []


def test_jsonb_to_declared_vars_none() -> None:
    assert _jsonb_to_declared_vars(None) == []  # type: ignore[arg-type]


def test_jsonb_to_model_default_round_trip() -> None:
    raw: dict[str, Any] = {"provider": "openai", "model_id": "gpt-5.4"}
    result = _jsonb_to_model_default(raw)
    assert result is not None
    assert result.provider == "openai"
    assert result.model_id == "gpt-5.4"


def test_jsonb_to_model_default_none() -> None:
    assert _jsonb_to_model_default(None) is None


# ---------------------------------------------------------------------------
# ORM → domain mapping
# ---------------------------------------------------------------------------


def test_orm_to_prompt_maps_fields() -> None:
    orm = _make_prompt_orm()
    prompt = _orm_to_prompt(orm)
    assert prompt.id == "prm-1"
    assert prompt.node_type == NodeType.TEXT
    assert prompt.status == PromptStatus.DRAFT
    assert prompt.tags == ["test"]


def test_orm_to_prompt_naive_datetime_gets_utc() -> None:
    orm = _make_prompt_orm()
    orm.created_at = datetime(2026, 5, 11)  # naive
    orm.updated_at = datetime(2026, 5, 11)  # naive
    prompt = _orm_to_prompt(orm)
    assert prompt.created_at is not None
    assert prompt.created_at.tzinfo is not None


def test_orm_to_prompt_version_maps_declared_variables() -> None:
    orm = _make_version_orm()
    version = _orm_to_prompt_version(orm)
    assert version.body == "Hello {name}"
    assert len(version.declared_variables) == 1
    assert version.declared_variables[0].name == "name"


def test_orm_to_prompt_usage_maps_score() -> None:
    orm = _make_usage_orm(last_run_score=Decimal("0.850"))
    usage = _orm_to_prompt_usage(orm)
    assert usage.last_run_score == pytest.approx(0.85)


def test_orm_to_prompt_usage_null_score() -> None:
    orm = _make_usage_orm()
    usage = _orm_to_prompt_usage(orm)
    assert usage.last_run_score is None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def prompt_repo(mock_session: AsyncMock) -> SqlAlchemyPromptRepo:
    return SqlAlchemyPromptRepo(mock_session)


@pytest.fixture
def version_repo(mock_session: AsyncMock) -> SqlAlchemyPromptVersionRepo:
    return SqlAlchemyPromptVersionRepo(mock_session)


@pytest.fixture
def usage_repo(mock_session: AsyncMock) -> SqlAlchemyPromptUsageRepo:
    return SqlAlchemyPromptUsageRepo(mock_session)


# ---------------------------------------------------------------------------
# SqlAlchemyPromptRepo.save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_repo_save_adds_and_flushes(
    prompt_repo: SqlAlchemyPromptRepo,
    mock_session: AsyncMock,
) -> None:
    prompt = Prompt(
        id="prm-new",
        name="New",
        node_type=NodeType.IMAGE,
        status=PromptStatus.DRAFT,
        tags=[],
    )
    mock_session.refresh = AsyncMock()

    # Intercept add to capture the ORM object
    added: list[Any] = []
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))

    # Make refresh update our ORM mock
    async def _refresh(obj: Any) -> None:
        obj.created_at = _NOW
        obj.updated_at = _NOW
        obj.tags = []
        obj.imported_from = None
        obj.owner = None
        obj.current_version_id = None
        obj.status = "draft"
        obj.node_type = "image"
        obj.name = "New"
        obj.id = "prm-new"

    mock_session.refresh = AsyncMock(side_effect=_refresh)

    await prompt_repo.save(prompt)

    mock_session.flush.assert_awaited_once()
    assert len(added) == 1
    assert added[0].id == "prm-new"


# ---------------------------------------------------------------------------
# SqlAlchemyPromptRepo.get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_repo_get_returns_none_when_not_found(
    prompt_repo: SqlAlchemyPromptRepo,
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)

    result = await prompt_repo.get("ghost")
    assert result is None


@pytest.mark.asyncio
async def test_prompt_repo_get_returns_domain_entity(
    prompt_repo: SqlAlchemyPromptRepo,
    mock_session: AsyncMock,
) -> None:
    orm = _make_prompt_orm()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = orm
    mock_session.execute = AsyncMock(return_value=result_mock)

    result = await prompt_repo.get("prm-1")
    assert result is not None
    assert isinstance(result, Prompt)
    assert result.id == "prm-1"


# ---------------------------------------------------------------------------
# SqlAlchemyPromptVersionRepo.next_version_number
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_repo_next_version_number_when_empty(
    version_repo: SqlAlchemyPromptVersionRepo,
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None  # MAX(version) = NULL
    mock_session.execute = AsyncMock(return_value=result_mock)

    num = await version_repo.next_version_number("prm-1")
    assert num == 1  # 0 + 1


@pytest.mark.asyncio
async def test_version_repo_next_version_number_increments(
    version_repo: SqlAlchemyPromptVersionRepo,
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = 3  # MAX(version) = 3
    mock_session.execute = AsyncMock(return_value=result_mock)

    num = await version_repo.next_version_number("prm-1")
    assert num == 4


# ---------------------------------------------------------------------------
# SqlAlchemyPromptVersionRepo.list_for_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_repo_list_for_prompt(
    version_repo: SqlAlchemyPromptVersionRepo,
    mock_session: AsyncMock,
) -> None:
    orm1 = _make_version_orm(vid="pmv-1", version=1)
    orm2 = _make_version_orm(vid="pmv-2", version=2)
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [orm1, orm2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    versions = await version_repo.list_for_prompt("prm-1")
    assert len(versions) == 2
    assert all(isinstance(v, PromptVersion) for v in versions)


# ---------------------------------------------------------------------------
# SqlAlchemyPromptUsageRepo.count_for_prompt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_repo_count_for_prompt(
    usage_repo: SqlAlchemyPromptUsageRepo,
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 5
    mock_session.execute = AsyncMock(return_value=result_mock)

    count = await usage_repo.count_for_prompt("prm-1")
    assert count == 5


# ---------------------------------------------------------------------------
# SqlAlchemyPromptUsageRepo.update_run_score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_repo_update_run_score(
    usage_repo: SqlAlchemyPromptUsageRepo,
    mock_session: AsyncMock,
) -> None:
    orm = _make_usage_orm()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = orm

    async def _refresh(obj: Any) -> None:
        obj.last_run_score = Decimal("0.900")
        obj.last_run_at = _NOW
        obj.created_at = _NOW

    mock_session.execute = AsyncMock(return_value=result_mock)
    mock_session.refresh = AsyncMock(side_effect=_refresh)

    usage = await usage_repo.update_run_score("use-1", 0.9)
    assert usage is not None
    assert float(orm.last_run_score) == pytest.approx(0.9)
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_repo_update_run_score_not_found_returns_none(
    usage_repo: SqlAlchemyPromptUsageRepo,
    mock_session: AsyncMock,
) -> None:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result_mock)

    usage = await usage_repo.update_run_score("ghost", 0.5)
    assert usage is None
