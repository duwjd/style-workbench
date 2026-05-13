"""Unit tests for tools/import_prompts.py (spec §13 단계 4 / AC-3).

Strategy:
    - _import_one() and run_import() are tested with an AsyncMock PromptService so that
      no real database or ARRAY-type SQLAlchemy dialect is required in unit tests.
    - Helper functions (_resolve_node_type, _clean_name, _extract_tags, etc.) are tested
      directly — they are pure functions with no I/O.
    - AC-3 acceptance criteria (>=10 files, idempotency, error handling) are all covered.

Coverage targets (spec §13 단계 4 / AC-3):
    - >=10 files with varied node_type patterns -> N prompts inserted.
    - Re-run (idempotency) -> 0 additional calls to service.create().
    - Empty file -> ValueError -> counted as error -> exit code 1.
    - Bad encoding -> UnicodeDecodeError -> counted as error -> exit code 1.
    - dry_run=True -> service.create() never called.
    - node_type suffix detection for all four types.
    - Default node_type fallback -> "text" with warning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from style_workbench.domain.prompt.entity import NodeType, Prompt, PromptStatus

# ---------------------------------------------------------------------------
# Fixture: source directory with >=10 diverse files
# ---------------------------------------------------------------------------

_FIXTURE_FILES: list[tuple[str, str]] = [
    # (relative_path, content)
    # text node
    ("portrait/professional/biz_portrait_text.md", "Hello {name}, you are {role}."),
    ("portrait/professional/greeting_text.txt", "Dear {name}, welcome to {company}."),
    # image node
    ("portrait/image/headshot_image.md", "Professional headshot of {person_name}."),
    ("portrait/image/background_image.txt", "Office background, formal style."),
    # video node
    ("video/intro_video.md", "Intro video for {brand} by {creator}."),
    ("video/outro_video.txt", "Outro with {call_to_action}."),
    # composition node
    ("composition/layout_composition.md", "Layout: {title}, {subtitle}"),
    ("composition/overlay_composition.txt", "Text overlay: {tagline}"),
    # no suffix -> default text with WARNING
    ("misc/no_suffix_at_all.md", "Just a plain prompt with {placeholder}."),
    ("misc/another_plain.txt", "Another prompt for {audience}."),
    # nested tags
    ("vertical/beauty/facial_image.md", "Facial image for {model_name}."),
]


def _build_fixture_dir(tmp_path: Path) -> Path:
    source = tmp_path / "prompts"
    for rel, content in _FIXTURE_FILES:
        target = source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return source


# ---------------------------------------------------------------------------
# Shared mock-service factory
# ---------------------------------------------------------------------------


def _make_mock_service(
    *,
    existing_imported_from: set[str] | None = None,
) -> MagicMock:
    """Build a MagicMock PromptService for use in _import_one / run_import tests.

    existing_imported_from: set of imported_from values to simulate already-existing prompts.
    """
    svc = MagicMock()

    # find_by_imported_from returns None for unknown paths, a Prompt for known ones.
    async def _find(path: str) -> Prompt | None:
        if existing_imported_from and path in existing_imported_from:
            return Prompt(
                id="prm-existing",
                name="existing",
                node_type=NodeType.TEXT,
                status=PromptStatus.APPROVED,
                imported_from=path,
            )
        return None

    svc.find_by_imported_from = _find

    created_prompts: list[dict[str, Any]] = []

    async def _create(**kwargs: Any) -> Prompt:
        created_prompts.append(kwargs)
        return Prompt(
            id=f"prm-{len(created_prompts)}",
            name=kwargs.get("name", ""),
            node_type=kwargs.get("node_type", NodeType.TEXT),
            status=kwargs.get("initial_status", PromptStatus.APPROVED),
            imported_from=kwargs.get("imported_from"),
        )

    svc.create = _create
    svc._created_prompts = created_prompts
    return svc


# ---------------------------------------------------------------------------
# _import_one unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_one_new_file_calls_create(tmp_path: Path) -> None:
    """_import_one on a new file calls service.create() and returns 'imported'."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "greeting_text.md"
    file_path.write_text("Hello {name}.", encoding="utf-8")

    svc = _make_mock_service()
    result = await _import_one(
        file_path=file_path,
        source_root=tmp_path,
        service=svc,  # type: ignore[arg-type]
        dry_run=False,
    )

    assert result == "imported"
    assert len(svc._created_prompts) == 1
    created = svc._created_prompts[0]
    assert created["node_type"] == NodeType.TEXT
    assert created["initial_status"] == PromptStatus.APPROVED
    assert created["imported_from"] == str(file_path.resolve())


@pytest.mark.asyncio
async def test_import_one_existing_file_returns_skipped(tmp_path: Path) -> None:
    """_import_one on an already-imported file returns 'skipped' without calling create()."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "greeting_text.md"
    file_path.write_text("Hello {name}.", encoding="utf-8")

    existing = {str(file_path.resolve())}
    svc = _make_mock_service(existing_imported_from=existing)
    result = await _import_one(
        file_path=file_path,
        source_root=tmp_path,
        service=svc,  # type: ignore[arg-type]
        dry_run=False,
    )

    assert result == "skipped"
    assert len(svc._created_prompts) == 0


@pytest.mark.asyncio
async def test_import_one_dry_run_skips_create(tmp_path: Path) -> None:
    """dry_run=True causes _import_one to return 'imported' without calling service.create()."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "greeting_text.md"
    file_path.write_text("Hello {name}.", encoding="utf-8")

    svc = _make_mock_service()
    result = await _import_one(
        file_path=file_path,
        source_root=tmp_path,
        service=svc,  # type: ignore[arg-type]
        dry_run=True,
    )

    assert result == "imported"
    assert len(svc._created_prompts) == 0  # no DB writes


@pytest.mark.asyncio
async def test_import_one_empty_file_raises(tmp_path: Path) -> None:
    """_import_one raises ValueError for an empty file."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "empty_text.md"
    file_path.write_text("   \n  ", encoding="utf-8")

    svc = _make_mock_service()
    with pytest.raises(ValueError, match="empty"):
        await _import_one(
            file_path=file_path,
            source_root=tmp_path,
            service=svc,  # type: ignore[arg-type]
            dry_run=False,
        )


@pytest.mark.asyncio
async def test_import_one_bad_encoding_raises(tmp_path: Path) -> None:
    """_import_one raises UnicodeDecodeError for a non-UTF-8 file."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "bad_image.md"
    file_path.write_bytes(b"\xff\xfe bad \xc0\xaf content")

    svc = _make_mock_service()
    with pytest.raises(UnicodeDecodeError):
        await _import_one(
            file_path=file_path,
            source_root=tmp_path,
            service=svc,  # type: ignore[arg-type]
            dry_run=False,
        )


@pytest.mark.asyncio
async def test_import_one_sets_correct_node_type_for_image(tmp_path: Path) -> None:
    """_import_one correctly maps *_image.md to NodeType.IMAGE."""
    from style_workbench.tools.import_prompts import _import_one

    file_path = tmp_path / "headshot_image.md"
    file_path.write_text("A portrait of {person_name}.", encoding="utf-8")

    svc = _make_mock_service()
    await _import_one(
        file_path=file_path,
        source_root=tmp_path,
        service=svc,  # type: ignore[arg-type]
        dry_run=False,
    )
    assert svc._created_prompts[0]["node_type"] == NodeType.IMAGE


@pytest.mark.asyncio
async def test_import_one_sets_correct_tags(tmp_path: Path) -> None:
    """_import_one derives tags from the ancestor directory names."""
    from style_workbench.tools.import_prompts import _import_one

    source = tmp_path / "prompts"
    file_path = source / "portrait" / "professional" / "headshot_image.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("Portrait of {name}.", encoding="utf-8")

    svc = _make_mock_service()
    await _import_one(
        file_path=file_path,
        source_root=source,
        service=svc,  # type: ignore[arg-type]
        dry_run=False,
    )
    assert svc._created_prompts[0]["tags"] == ["portrait", "professional"]


# ---------------------------------------------------------------------------
# run_import integration: mock PromptService injected via patch
# ---------------------------------------------------------------------------


def _patch_run_import_infra(
    mock_svc: MagicMock,
) -> tuple[Any, ...]:
    """Return a tuple of context managers that patch the DB/SQLAlchemy layer in run_import."""
    mock_session = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_engine_instance = AsyncMock()
    mock_engine_instance.dispose = AsyncMock()

    return (
        patch(
            "style_workbench.tools.import_prompts.create_async_engine",
            return_value=mock_engine_instance,
        ),
        patch(
            "style_workbench.tools.import_prompts.async_sessionmaker",
            return_value=MagicMock(return_value=mock_ctx),
        ),
        patch("style_workbench.tools.import_prompts.PromptService", return_value=mock_svc),
        patch(
            "style_workbench.tools.import_prompts.SqlAlchemyPromptRepo",
            return_value=MagicMock(),
        ),
        patch(
            "style_workbench.tools.import_prompts.SqlAlchemyPromptVersionRepo",
            return_value=MagicMock(),
        ),
        patch(
            "style_workbench.tools.import_prompts.SqlAlchemyPromptUsageRepo",
            return_value=MagicMock(),
        ),
    )


@pytest.mark.asyncio
async def test_run_import_10_files_ac3_primary(tmp_path: Path) -> None:
    """AC-3: >=10 files -> 11 calls to service.create() (one per file)."""
    from style_workbench.tools.import_prompts import run_import

    source = _build_fixture_dir(tmp_path)
    mock_svc = _make_mock_service()

    with _patch_run_import_infra(mock_svc)[0], _patch_run_import_infra(mock_svc)[1]:
        # Use contextlib.ExitStack-style with multiple patches
        patches = _patch_run_import_infra(mock_svc)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            exit_code = await run_import(
                source=source, db_url="postgresql://fake/db", dry_run=False
            )

    assert exit_code == 0
    assert len(mock_svc._created_prompts) == len(_FIXTURE_FILES), (
        f"Expected {len(_FIXTURE_FILES)} creates, got {len(mock_svc._created_prompts)}"
    )


@pytest.mark.asyncio
async def test_run_import_idempotent_zero_new_creates(tmp_path: Path) -> None:
    """AC-3 idempotency: when all files already exist, service.create() is never called."""
    from style_workbench.tools.import_prompts import run_import

    source = _build_fixture_dir(tmp_path)

    # All files are "already imported"
    all_paths = {str((source / rel).resolve()) for rel, _ in _FIXTURE_FILES}
    mock_svc = _make_mock_service(existing_imported_from=all_paths)

    patches = _patch_run_import_infra(mock_svc)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        exit_code = await run_import(source=source, db_url="postgresql://fake/db", dry_run=False)

    assert exit_code == 0
    assert len(mock_svc._created_prompts) == 0, "Idempotent: no new creates expected"


@pytest.mark.asyncio
async def test_run_import_error_file_returns_exit_1(tmp_path: Path) -> None:
    """A file that fails to import results in exit code 1 (partial failure)."""
    from style_workbench.tools.import_prompts import run_import

    source = tmp_path / "mixed_source"
    source.mkdir()
    # Valid file
    (source / "valid_text.md").write_text("Good content with {placeholder}.", encoding="utf-8")
    # Empty file (will raise ValueError)
    (source / "empty_text.md").write_text("   \n  ", encoding="utf-8")

    mock_svc = _make_mock_service()

    patches = _patch_run_import_infra(mock_svc)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        exit_code = await run_import(source=source, db_url="postgresql://fake/db", dry_run=False)

    assert exit_code == 1
    # The valid file was still processed
    assert len(mock_svc._created_prompts) >= 1


@pytest.mark.asyncio
async def test_run_import_dry_run_no_db_writes(tmp_path: Path) -> None:
    """dry_run=True: service.create() is never called regardless of how many files exist."""
    from style_workbench.tools.import_prompts import run_import

    source = _build_fixture_dir(tmp_path)
    mock_svc = _make_mock_service()

    patches = _patch_run_import_infra(mock_svc)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        exit_code = await run_import(source=source, db_url="postgresql://fake/db", dry_run=True)

    assert exit_code == 0
    assert len(mock_svc._created_prompts) == 0


@pytest.mark.asyncio
async def test_run_import_missing_source_returns_exit_2(tmp_path: Path) -> None:
    """Non-existent source directory -> exit code 2 (fatal)."""
    from style_workbench.tools.import_prompts import run_import

    nonexistent = tmp_path / "does_not_exist"
    exit_code = await run_import(source=nonexistent, db_url=None, dry_run=False)

    assert exit_code == 2


@pytest.mark.asyncio
async def test_run_import_empty_source_returns_exit_0(tmp_path: Path) -> None:
    """Source directory with no .md/.txt files -> 0 imported, exit code 0."""
    from style_workbench.tools.import_prompts import run_import

    source = tmp_path / "empty_source"
    source.mkdir()
    (source / "README.rst").write_text("Not a prompt file", encoding="utf-8")

    exit_code = await run_import(source=source, db_url=None, dry_run=False)

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Unit tests for module-level helpers (no DB, no I/O)
# ---------------------------------------------------------------------------


def test_resolve_node_type_text() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _resolve_node_type

    nt, matched = _resolve_node_type("biz_portrait_text")
    assert nt == NodeType.TEXT
    assert matched is True


def test_resolve_node_type_image() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _resolve_node_type

    nt, matched = _resolve_node_type("headshot_image")
    assert nt == NodeType.IMAGE
    assert matched is True


def test_resolve_node_type_video() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _resolve_node_type

    nt, matched = _resolve_node_type("intro_video")
    assert nt == NodeType.VIDEO
    assert matched is True


def test_resolve_node_type_composition() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _resolve_node_type

    nt, matched = _resolve_node_type("layout_composition")
    assert nt == NodeType.COMPOSITION
    assert matched is True


def test_resolve_node_type_no_match_defaults_text() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _resolve_node_type

    nt, matched = _resolve_node_type("no_suffix_at_all")
    assert nt == NodeType.TEXT
    assert matched is False


def test_clean_name_strips_suffix() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _clean_name

    assert _clean_name("biz_portrait_image", NodeType.IMAGE) == "biz_portrait"
    assert _clean_name("intro_video", NodeType.VIDEO) == "intro"
    assert _clean_name("layout_composition", NodeType.COMPOSITION) == "layout"
    assert _clean_name("greeting_text", NodeType.TEXT) == "greeting"


def test_clean_name_no_suffix_unchanged() -> None:
    from style_workbench.domain.prompt.entity import NodeType
    from style_workbench.tools.import_prompts import _clean_name

    assert _clean_name("no_match_at_all", NodeType.TEXT) == "no_match_at_all"


def test_extract_tags_from_nested_path(tmp_path: Path) -> None:
    from style_workbench.tools.import_prompts import _extract_tags

    source_root = tmp_path / "prompts"
    file_path = source_root / "portrait" / "professional" / "biz_portrait_image.md"

    tags = _extract_tags(file_path, source_root)
    assert tags == ["portrait", "professional"]


def test_extract_tags_flat_file(tmp_path: Path) -> None:
    from style_workbench.tools.import_prompts import _extract_tags

    source_root = tmp_path / "prompts"
    file_path = source_root / "flat_image.md"

    tags = _extract_tags(file_path, source_root)
    assert tags == []


def test_build_declared_variables_from_body() -> None:
    from style_workbench.tools.import_prompts import _build_declared_variables

    body = "Hello {name}, you are {role} at {company}."
    dvars = _build_declared_variables(body)

    names = {v.name for v in dvars}
    assert names == {"name", "role", "company"}
    assert all(v.required for v in dvars)
    assert all(v.role == "unknown" for v in dvars)


def test_build_declared_variables_no_placeholders() -> None:
    from style_workbench.tools.import_prompts import _build_declared_variables

    dvars = _build_declared_variables("A prompt with no placeholders.")
    assert dvars == []


def test_walk_prompt_files_finds_md_and_txt(tmp_path: Path) -> None:
    from style_workbench.tools.import_prompts import _walk_prompt_files

    source = tmp_path / "walk_test"
    (source / "sub").mkdir(parents=True)
    (source / "a_text.md").write_text("body", encoding="utf-8")
    (source / "b_image.txt").write_text("body", encoding="utf-8")
    (source / "sub" / "c_video.md").write_text("body", encoding="utf-8")
    (source / "skip_me.rst").write_text("body", encoding="utf-8")  # should be ignored

    files = _walk_prompt_files(source)
    names = {f.name for f in files}

    assert "a_text.md" in names
    assert "b_image.txt" in names
    assert "c_video.md" in names
    assert "skip_me.rst" not in names


def test_body_hash_is_not_empty_and_16_chars() -> None:
    from style_workbench.tools.import_prompts import _body_hash

    h = _body_hash("Hello {name}.")
    assert len(h) == 16
    assert h != ""


def test_body_hash_different_for_different_bodies() -> None:
    from style_workbench.tools.import_prompts import _body_hash

    assert _body_hash("body A") != _body_hash("body B")
