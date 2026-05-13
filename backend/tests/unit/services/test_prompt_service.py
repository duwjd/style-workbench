"""Unit tests for PromptService (spec §10.1).

Uses AsyncMock repositories — no DB required.
Covers: CRUD, version creation, promote, lifecycle transitions, FR-3 validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from style_workbench.core.errors import (
    InvalidPromptStatusTransitionError,
    MissingDeclaredVariableError,
    PromptAbSameVersionError,
    PromptDeprecatedError,
    PromptNotFoundError,
    PromptVersionNotFoundError,
    StyleVersionHasNoPromptNodeError,
)
from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    NodeType,
    Prompt,
    PromptAbComparison,
    PromptFilters,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.services.prompt_service import PromptService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 11, tzinfo=UTC)


def _make_prompt(
    pid: str = "prm-1",
    status: PromptStatus = PromptStatus.DRAFT,
    current_version_id: str | None = "pmv-1",
) -> Prompt:
    return Prompt(
        id=pid,
        name="Test Prompt",
        node_type=NodeType.TEXT,
        status=status,
        current_version_id=current_version_id,
        tags=["test"],
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_version(
    vid: str = "pmv-1",
    prompt_id: str = "prm-1",
    version: int = 1,
) -> PromptVersion:
    return PromptVersion(
        id=vid,
        prompt_id=prompt_id,
        version=version,
        body="Hello {name}",
        declared_variables=[DeclaredVariable(name="name")],
        created_at=_NOW,
    )


@pytest.fixture
def mock_prompt_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock()
    repo.get_with_version = AsyncMock()
    repo.update = AsyncMock()
    repo.list = AsyncMock()
    return repo


@pytest.fixture
def mock_version_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock()
    repo.get_by_prompt_and_number = AsyncMock()
    repo.list_for_prompt = AsyncMock()
    repo.next_version_number = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def mock_usage_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock()
    repo.list_for_prompt = AsyncMock()
    repo.count_for_prompt = AsyncMock(return_value=0)
    repo.update_run_score = AsyncMock()
    return repo


@pytest.fixture
def mock_ab_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def service(
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
    mock_usage_repo: AsyncMock,
    mock_ab_repo: AsyncMock,
) -> PromptService:
    return PromptService(mock_prompt_repo, mock_version_repo, mock_usage_repo, mock_ab_repo)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_stores_prompt_and_version(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    saved_prompt = _make_prompt(current_version_id=None)
    saved_version = _make_version()
    updated_prompt = _make_prompt(current_version_id="pmv-1")

    mock_prompt_repo.save.return_value = saved_prompt
    mock_version_repo.save.return_value = saved_version
    mock_prompt_repo.update.return_value = updated_prompt

    result = await service.create(
        name="Test",
        node_type=NodeType.TEXT,
        body="Hello {name}",
        declared_variables=[DeclaredVariable(name="name")],
    )

    mock_prompt_repo.save.assert_awaited_once()
    mock_version_repo.save.assert_awaited_once()
    mock_prompt_repo.update.assert_awaited_once()
    assert result.current_version is not None


@pytest.mark.asyncio
async def test_create_initial_status_is_draft_by_default(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    saved_prompt = _make_prompt(status=PromptStatus.DRAFT, current_version_id=None)
    mock_prompt_repo.save.return_value = saved_prompt
    mock_version_repo.save.return_value = _make_version()
    mock_prompt_repo.update.return_value = _make_prompt()

    await service.create(
        name="X",
        node_type=NodeType.IMAGE,
        body="prompt body",
        declared_variables=[],
    )
    saved_arg: Prompt = mock_prompt_repo.save.call_args[0][0]
    assert saved_arg.status == PromptStatus.DRAFT


@pytest.mark.asyncio
async def test_create_raises_on_undeclared_placeholder(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    with pytest.raises(MissingDeclaredVariableError):
        await service.create(
            name="Bad",
            node_type=NodeType.TEXT,
            body="Hello {unknown_var}",
            declared_variables=[],  # 'unknown_var' is not declared
        )
    mock_prompt_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_with_imported_from(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    saved_prompt = _make_prompt(current_version_id=None)
    saved_prompt.imported_from = "prompt_optimizer/modules/portrait"
    mock_prompt_repo.save.return_value = saved_prompt
    mock_version_repo.save.return_value = _make_version()
    mock_prompt_repo.update.return_value = _make_prompt()

    await service.create(
        name="Import",
        node_type=NodeType.IMAGE,
        body="static body",
        declared_variables=[],
        imported_from="prompt_optimizer/modules/portrait",
        initial_status=PromptStatus.APPROVED,
    )
    saved_arg: Prompt = mock_prompt_repo.save.call_args[0][0]
    assert saved_arg.imported_from == "prompt_optimizer/modules/portrait"
    assert saved_arg.status == PromptStatus.APPROVED


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_prompt_with_version(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt = _make_prompt()
    prompt.current_version = _make_version()
    mock_prompt_repo.get_with_version.return_value = prompt

    result = await service.get("prm-1")
    assert result.id == "prm-1"
    assert result.current_version is not None


@pytest.mark.asyncio
async def test_get_raises_not_found(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    mock_prompt_repo.get_with_version.return_value = None
    with pytest.raises(PromptNotFoundError):
        await service.get("nonexistent")


# ---------------------------------------------------------------------------
# update_meta
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_meta_name_and_tags(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt = _make_prompt()
    updated = _make_prompt()
    updated.name = "New Name"
    updated.tags = ["a", "b"]
    mock_prompt_repo.get.return_value = prompt
    mock_prompt_repo.update.return_value = updated

    await service.update_meta("prm-1", name="New Name", tags=["a", "b"])

    assert mock_prompt_repo.update.call_args[0][0].name == "New Name"
    assert mock_prompt_repo.update.call_args[0][0].tags == ["a", "b"]


@pytest.mark.asyncio
async def test_update_meta_valid_status_transition(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt = _make_prompt(status=PromptStatus.DRAFT)
    updated = _make_prompt(status=PromptStatus.REVIEWING)
    mock_prompt_repo.get.return_value = prompt
    mock_prompt_repo.update.return_value = updated

    result = await service.update_meta("prm-1", status=PromptStatus.REVIEWING)
    assert result.status == PromptStatus.REVIEWING


@pytest.mark.asyncio
async def test_update_meta_invalid_transition_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    # draft → approved is not a valid transition
    prompt = _make_prompt(status=PromptStatus.DRAFT)
    mock_prompt_repo.get.return_value = prompt

    with pytest.raises(InvalidPromptStatusTransitionError):
        await service.update_meta("prm-1", status=PromptStatus.APPROVED)


@pytest.mark.asyncio
async def test_update_meta_not_found_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    mock_prompt_repo.get.return_value = None
    with pytest.raises(PromptNotFoundError):
        await service.update_meta("ghost", name="x")


# ---------------------------------------------------------------------------
# create_version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_version_increments_and_saves(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    prompt = _make_prompt(current_version_id="pmv-1")
    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.next_version_number.return_value = 2
    new_ver = _make_version(vid="pmv-2", version=2)
    mock_version_repo.save.return_value = new_ver

    result = await service.create_version(
        prompt_id="prm-1",
        body="Updated {name}",
        declared_variables=[DeclaredVariable(name="name")],
        change_note="tone update",
    )

    assert result.version == 2
    saved_arg: PromptVersion = mock_version_repo.save.call_args[0][0]
    assert saved_arg.parent_version_id == "pmv-1"
    assert saved_arg.change_note == "tone update"


@pytest.mark.asyncio
async def test_create_version_raises_on_undeclared_placeholder(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    prompt = _make_prompt()
    mock_prompt_repo.get.return_value = prompt

    with pytest.raises(MissingDeclaredVariableError):
        await service.create_version(
            prompt_id="prm-1",
            body="Hi {unknown}",
            declared_variables=[],
        )
    mock_version_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_version_not_found_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    mock_prompt_repo.get.return_value = None
    with pytest.raises(PromptNotFoundError):
        await service.create_version(
            prompt_id="ghost",
            body="body",
            declared_variables=[],
        )


# ---------------------------------------------------------------------------
# promote_version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promote_version_updates_current_version_id(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    prompt = _make_prompt(status=PromptStatus.APPROVED, current_version_id="pmv-1")
    version = _make_version(vid="pmv-2", version=2)
    updated_prompt = _make_prompt(current_version_id="pmv-2")

    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.get.return_value = version
    mock_prompt_repo.update.return_value = updated_prompt

    result = await service.promote_version("prm-1", "pmv-2")

    promoted_arg: Prompt = mock_prompt_repo.update.call_args[0][0]
    assert promoted_arg.current_version_id == "pmv-2"
    assert result.current_version is version


@pytest.mark.asyncio
async def test_promote_deprecated_prompt_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompt = _make_prompt(status=PromptStatus.DEPRECATED)
    mock_prompt_repo.get.return_value = prompt

    with pytest.raises(PromptDeprecatedError):
        await service.promote_version("prm-1", "pmv-2")


@pytest.mark.asyncio
async def test_promote_version_not_found_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    prompt = _make_prompt(status=PromptStatus.APPROVED)
    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.get.return_value = None

    with pytest.raises(PromptVersionNotFoundError):
        await service.promote_version("prm-1", "nonexistent-version")


@pytest.mark.asyncio
async def test_promote_version_wrong_prompt_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
) -> None:
    """A version that exists but belongs to a different prompt must raise."""
    prompt = _make_prompt(pid="prm-1", status=PromptStatus.APPROVED)
    wrong_version = _make_version(vid="pmv-x", prompt_id="prm-OTHER")
    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.get.return_value = wrong_version

    with pytest.raises(PromptVersionNotFoundError):
        await service.promote_version("prm-1", "pmv-x")


@pytest.mark.asyncio
async def test_promote_prompt_not_found_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    mock_prompt_repo.get.return_value = None
    with pytest.raises(PromptNotFoundError):
        await service.promote_version("ghost", "pmv-1")


# ---------------------------------------------------------------------------
# lifecycle transition matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_status, to_status, should_raise",
    [
        # Allowed
        (PromptStatus.DRAFT, PromptStatus.REVIEWING, False),
        (PromptStatus.REVIEWING, PromptStatus.APPROVED, False),
        (PromptStatus.REVIEWING, PromptStatus.DRAFT, False),
        (PromptStatus.APPROVED, PromptStatus.DEPRECATED, False),
        # Forbidden
        (PromptStatus.DRAFT, PromptStatus.APPROVED, True),
        (PromptStatus.DRAFT, PromptStatus.DEPRECATED, True),
        (PromptStatus.APPROVED, PromptStatus.DRAFT, True),
        (PromptStatus.APPROVED, PromptStatus.REVIEWING, True),
        (PromptStatus.DEPRECATED, PromptStatus.DRAFT, True),
        (PromptStatus.DEPRECATED, PromptStatus.REVIEWING, True),
        (PromptStatus.DEPRECATED, PromptStatus.APPROVED, True),
    ],
)
@pytest.mark.asyncio
async def test_status_transition_matrix(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    from_status: PromptStatus,
    to_status: PromptStatus,
    should_raise: bool,
) -> None:
    prompt = _make_prompt(status=from_status)
    mock_prompt_repo.get.return_value = prompt
    if not should_raise:
        updated = _make_prompt(status=to_status)
        mock_prompt_repo.update.return_value = updated

    if should_raise:
        with pytest.raises(InvalidPromptStatusTransitionError):
            await service.update_meta("prm-1", status=to_status)
    else:
        result = await service.update_meta("prm-1", status=to_status)
        assert result.status == to_status


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_delegates_to_repo(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
) -> None:
    prompts = [_make_prompt("prm-1"), _make_prompt("prm-2")]
    mock_prompt_repo.list.return_value = prompts

    filters = PromptFilters(node_type=NodeType.TEXT, limit=10, offset=0)
    result = await service.list_prompts(filters)

    mock_prompt_repo.list.assert_awaited_once_with(filters)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# record_usage + update_usage_score
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_usage_saves_usage(
    service: PromptService,
    mock_usage_repo: AsyncMock,
) -> None:
    usage = PromptUsage(
        id="use-1",
        prompt_id="prm-1",
        prompt_version_id="pmv-1",
        style_version_id="stv-1",
        node_id="txt1",
        pinned=False,
    )
    mock_usage_repo.save.return_value = usage

    result = await service.record_usage(
        prompt_id="prm-1",
        prompt_version_id="pmv-1",
        style_version_id="stv-1",
        node_id="txt1",
    )
    assert result.id == "use-1"
    mock_usage_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_usage_score(
    service: PromptService,
    mock_usage_repo: AsyncMock,
) -> None:
    updated_usage = PromptUsage(
        id="use-1",
        prompt_id="prm-1",
        prompt_version_id="pmv-1",
        style_version_id="stv-1",
        node_id="txt1",
        last_run_score=0.85,
    )
    mock_usage_repo.update_run_score.return_value = updated_usage

    result = await service.update_usage_score("use-1", 0.85)
    assert result.last_run_score == pytest.approx(0.85)


@pytest.mark.asyncio
async def test_update_usage_score_not_found_raises(
    service: PromptService,
    mock_usage_repo: AsyncMock,
) -> None:
    mock_usage_repo.update_run_score.return_value = None
    with pytest.raises(PromptNotFoundError):
        await service.update_usage_score("ghost-usage", 0.5)


# ---------------------------------------------------------------------------
# trigger_ab (A/B comparison — 단계 5)
# ---------------------------------------------------------------------------


def _make_run_service_mock(
    *,
    from_run_id: str = "run-from",
    to_run_id: str = "run-to",
) -> AsyncMock:
    """Create a minimal RunService mock that satisfies trigger_ab's interface."""
    from style_workbench.services.run_service import RunService

    mock_rs = AsyncMock(spec=RunService)

    from_run = AsyncMock()
    from_run.id = from_run_id
    to_run = AsyncMock()
    to_run.id = to_run_id

    mock_rs.execute = AsyncMock(side_effect=[from_run, to_run])
    return mock_rs


@pytest.mark.asyncio
async def test_ab_comparison_creates_two_runs(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
    mock_usage_repo: AsyncMock,
    mock_ab_repo: AsyncMock,
) -> None:
    """trigger_ab → two execute() calls → from_run_id and to_run_id populated."""
    prompt = _make_prompt(status=PromptStatus.APPROVED)
    from_ver = _make_version(vid="pmv-1", prompt_id="prm-1", version=1)
    to_ver = _make_version(vid="pmv-2", prompt_id="prm-1", version=2)

    usage = PromptUsage(
        id="use-1",
        prompt_id="prm-1",
        prompt_version_id="pmv-1",
        style_version_id="stv-1",
        node_id="txt1",
    )

    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.get.side_effect = [from_ver, to_ver]
    mock_usage_repo.list_for_prompt.return_value = [usage]

    saved_ab = PromptAbComparison(
        id="ab-1",
        prompt_id="prm-1",
        from_version_id="pmv-1",
        to_version_id="pmv-2",
        style_version_id="stv-1",
        user_input={"name": "Alice"},
        status="running",
    )
    updated_ab = PromptAbComparison(
        id="ab-1",
        prompt_id="prm-1",
        from_version_id="pmv-1",
        to_version_id="pmv-2",
        style_version_id="stv-1",
        user_input={"name": "Alice"},
        from_run_id="run-from",
        to_run_id="run-to",
        status="done",
    )
    mock_ab_repo.save.return_value = saved_ab
    mock_ab_repo.update.return_value = updated_ab

    mock_run_service = _make_run_service_mock(from_run_id="run-from", to_run_id="run-to")

    result = await service.trigger_ab(
        prompt_id="prm-1",
        from_version_id="pmv-1",
        to_version_id="pmv-2",
        style_version_id="stv-1",
        user_input={"name": "Alice"},
        run_service=mock_run_service,
    )

    # Two execute() calls must have been made (serial execution per FR-8)
    assert mock_run_service.execute.await_count == 2

    # AB record must be saved and then updated
    mock_ab_repo.save.assert_awaited_once()
    mock_ab_repo.update.assert_awaited_once()

    # Result must carry both run ids
    assert result.from_run_id == "run-from"
    assert result.to_run_id == "run-to"


@pytest.mark.asyncio
async def test_ab_comparison_same_version_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
    mock_ab_repo: AsyncMock,
) -> None:
    """from_version_id == to_version_id → PromptAbSameVersionError."""
    prompt = _make_prompt()
    mock_prompt_repo.get.return_value = prompt

    mock_run_service = _make_run_service_mock()

    with pytest.raises(PromptAbSameVersionError):
        await service.trigger_ab(
            prompt_id="prm-1",
            from_version_id="pmv-1",
            to_version_id="pmv-1",  # same!
            style_version_id="stv-1",
            user_input={},
            run_service=mock_run_service,
        )

    # No execute() call should have happened
    mock_run_service.execute.assert_not_awaited()
    mock_ab_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_ab_comparison_failed_prompt_lookup(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_version_repo: AsyncMock,
    mock_usage_repo: AsyncMock,
    mock_ab_repo: AsyncMock,
) -> None:
    """style_version_id has no node referencing this prompt → 422."""
    prompt = _make_prompt()
    from_ver = _make_version(vid="pmv-1", prompt_id="prm-1", version=1)
    to_ver = _make_version(vid="pmv-2", prompt_id="prm-1", version=2)

    mock_prompt_repo.get.return_value = prompt
    mock_version_repo.get.side_effect = [from_ver, to_ver]

    # No usages for this style_version → empty list
    mock_usage_repo.list_for_prompt.return_value = []

    mock_run_service = _make_run_service_mock()

    with pytest.raises(StyleVersionHasNoPromptNodeError):
        await service.trigger_ab(
            prompt_id="prm-1",
            from_version_id="pmv-1",
            to_version_id="pmv-2",
            style_version_id="stv-99",  # not linked to this prompt
            user_input={},
            run_service=mock_run_service,
        )

    mock_run_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_ab_comparison_prompt_not_found_raises(
    service: PromptService,
    mock_prompt_repo: AsyncMock,
    mock_ab_repo: AsyncMock,
) -> None:
    """Unknown prompt_id → PromptNotFoundError."""
    mock_prompt_repo.get.return_value = None
    mock_run_service = _make_run_service_mock()

    with pytest.raises(PromptNotFoundError):
        await service.trigger_ab(
            prompt_id="ghost",
            from_version_id="pmv-1",
            to_version_id="pmv-2",
            style_version_id="stv-1",
            user_input={},
            run_service=mock_run_service,
        )
