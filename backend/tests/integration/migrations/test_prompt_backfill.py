"""Integration tests for the prompt_usages backfill migration (spec §13 단계 4).

Tests spec §5.4 단계 2 requirements:
    - style_versions rows with inline prompt_template are converted to
      prompts + prompt_versions + prompt_usages rows.
    - Nodes get their prompt_id / prompt_version_id / prompt_pinned set.
    - prompt_template is preserved (rollback safety).
    - Idempotent: re-running the migration inserts 0 additional rows.
    - downgrade restores the original state.

Strategy:
    - Requires a live PostgreSQL database (DATABASE_URL env var / settings).
    - Tests are SKIPPED if the DB is not reachable (same pattern as conftest.py).
    - Migration logic is tested by directly calling upgrade() / downgrade() functions
      from the migration module with a patched alembic op.get_bind().
    - The DB schema is created from scratch for each test (isolated).

Why PostgreSQL required (not SQLite):
    - The migration inserts into ``prompts.tags`` which is a PostgreSQL TEXT[] column.
    - SQLite does not support Python list binding for array columns.
    - This is an intentional constraint: backfill migrations are production operations
      targeting PostgreSQL.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from style_workbench.core.config import settings

# ---------------------------------------------------------------------------
# Schema setup — create prompt-library tables on top of the test DB
# ---------------------------------------------------------------------------


async def _ensure_schema(conn: Any) -> None:
    """Create the minimum tables needed by the backfill migration."""
    stmts = [
        """
        CREATE TABLE IF NOT EXISTS styles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            current_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS style_versions (
            id TEXT PRIMARY KEY,
            style_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            dag JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            node_type TEXT NOT NULL,
            owner TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            current_version_id TEXT,
            tags TEXT[] NOT NULL DEFAULT '{}',
            imported_from TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_prompts_imported_from
            ON prompts (imported_from) WHERE imported_from IS NOT NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id TEXT PRIMARY KEY,
            prompt_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            body TEXT NOT NULL,
            declared_variables JSONB NOT NULL DEFAULT '[]',
            model_default JSONB,
            parent_version_id TEXT,
            change_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS prompt_usages (
            id TEXT PRIMARY KEY,
            prompt_id TEXT NOT NULL,
            prompt_version_id TEXT NOT NULL,
            style_version_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            pinned BOOLEAN NOT NULL DEFAULT FALSE,
            last_run_score NUMERIC(4,3),
            last_run_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(style_version_id, node_id)
        )
        """,
    ]
    for stmt in stmts:
        await conn.execute(text(stmt))


async def _teardown_schema(conn: Any) -> None:
    """Drop tables created by this test (clean isolation)."""
    for tbl in ["prompt_usages", "prompt_versions", "prompts", "style_versions", "styles"]:
        await conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_STYLE_ID = "mig-test-style-001"
_SV_ID_1 = "mig-test-sv-001"
_SV_ID_2 = "mig-test-sv-002"

_NODE_1: dict[str, Any] = {
    "id": "node-txt-1",
    "type": "text_generation",
    "prompt_template": "Hello {name}, you are {role}.",
    "model": {"provider": "openai", "model_id": "gpt-4o"},
    "inputs": [],
}
_NODE_2: dict[str, Any] = {
    "id": "node-img-1",
    "type": "image_generation",
    "prompt_template": "Professional headshot of {person_name}.",
    "model": {"provider": "replicate", "model_id": "some/model"},
    "inputs": [],
}
_NODE_3: dict[str, Any] = {
    "id": "node-txt-2",
    "type": "text_generation",
    "prompt_template": "Welcome to {company}.",
    "model": {"provider": "openai", "model_id": "gpt-4o"},
    "inputs": [],
}
_NODE_NO_TEMPLATE: dict[str, Any] = {
    "id": "node-no-template",
    "type": "image_generation",
    "prompt_template": "",
    "model": {"provider": "replicate", "model_id": "some/model"},
    "inputs": [],
}

_DAG_1: dict[str, Any] = {
    "nodes": [_NODE_1, _NODE_2, _NODE_NO_TEMPLATE],
    "edges": [],
    "variables": [],
}
_DAG_2: dict[str, Any] = {"nodes": [_NODE_3], "edges": [], "variables": []}


async def _insert_fixtures(session: AsyncSession) -> None:
    await session.execute(
        text("INSERT INTO styles (id, name) VALUES (:id, :name)"),
        {"id": _STYLE_ID, "name": "Migration Test Style"},
    )
    await session.execute(
        text(
            "INSERT INTO style_versions (id, style_id, version, dag) "
            "VALUES (:id, :style_id, :version, CAST(:dag AS jsonb))"
        ),
        {"id": _SV_ID_1, "style_id": _STYLE_ID, "version": 1, "dag": json.dumps(_DAG_1)},
    )
    await session.execute(
        text(
            "INSERT INTO style_versions (id, style_id, version, dag) "
            "VALUES (:id, :style_id, :version, CAST(:dag AS jsonb))"
        ),
        {"id": _SV_ID_2, "style_id": _STYLE_ID, "version": 2, "dag": json.dumps(_DAG_2)},
    )
    await session.commit()


async def _count_rows(session: AsyncSession, table: str) -> int:
    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return result.scalar_one()


async def _fetch_dag(session: AsyncSession, sv_id: str) -> dict[str, Any]:
    result = await session.execute(
        text("SELECT dag FROM style_versions WHERE id = :id"), {"id": sv_id}
    )
    row = result.fetchone()
    assert row is not None
    return row[0]  # JSONB is returned as dict by asyncpg


# ---------------------------------------------------------------------------
# Migration execution helpers
# ---------------------------------------------------------------------------

_MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "alembic"
    / "versions"
    / "a1b2c3d4e5f6_backfill_prompt_usages_from_inline.py"
)


def _load_migration_module(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, _MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _run_upgrade(sync_conn: Any) -> None:
    mock_op = MagicMock()
    mock_op.get_bind.return_value = sync_conn
    module = _load_migration_module("backfill_up")
    module.__dict__["op"] = mock_op
    module.upgrade()


def _run_downgrade(sync_conn: Any) -> None:
    mock_op = MagicMock()
    mock_op.get_bind.return_value = sync_conn
    module = _load_migration_module("backfill_down")
    module.__dict__["op"] = mock_op
    module.downgrade()


# ---------------------------------------------------------------------------
# pytest fixtures for DB sessions
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncSession:  # type: ignore[return]
    """Async session pointing at the test PostgreSQL database.

    Skips the test if the database is not reachable.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.connect() as probe:
            await probe.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL not available: {exc}")

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            async with session.begin():
                await _ensure_schema(session)
            yield session
        finally:
            async with session.begin():
                await _teardown_schema(session)
    await engine.dispose()


@pytest.fixture
def sync_conn_factory(db_session: AsyncSession) -> Any:
    """Return a factory that creates a synchronous connection from the test DB URL."""
    import sqlalchemy as sa  # noqa: PLC0415

    sync_url = settings.database_url.replace("+asyncpg", "")
    engine = sa.create_engine(sync_url)

    def _factory() -> Any:
        return engine.connect()

    return _factory, engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_creates_prompts_versions_usages(db_session: AsyncSession) -> None:
    """Primary path: 2 style_versions (3 nodes with templates) -> 3 prompts/versions/usages."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    # Re-read counts in async session
    await db_session.expire_all()
    n_prompts = await _count_rows(db_session, "prompts")
    n_versions = await _count_rows(db_session, "prompt_versions")
    n_usages = await _count_rows(db_session, "prompt_usages")

    # 3 nodes have non-empty prompt_template (_NODE_1, _NODE_2, _NODE_3)
    assert n_prompts == 3, f"Expected 3 prompts, got {n_prompts}"
    assert n_versions == 3, f"Expected 3 prompt_versions, got {n_versions}"
    assert n_usages == 3, f"Expected 3 prompt_usages, got {n_usages}"


@pytest.mark.asyncio
async def test_backfill_sets_node_prompt_id_in_jsonb(db_session: AsyncSession) -> None:
    """Verify that node JSONB fields are updated: prompt_id + prompt_version_id + prompt_pinned."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    await db_session.expire_all()
    dag1 = await _fetch_dag(db_session, _SV_ID_1)
    nodes = {n["id"]: n for n in dag1["nodes"]}

    txt_node = nodes["node-txt-1"]
    assert txt_node.get("prompt_id"), "prompt_id must be set"
    assert txt_node.get("prompt_version_id"), "prompt_version_id must be set"
    assert txt_node.get("prompt_pinned") is True, "prompt_pinned must be True"
    assert txt_node.get("prompt_template") == "Hello {name}, you are {role}.", (
        "prompt_template must be preserved"
    )

    no_tmpl_node = nodes["node-no-template"]
    assert not no_tmpl_node.get("prompt_id"), "Node with empty body must not get prompt_id"


@pytest.mark.asyncio
async def test_backfill_all_usages_are_pinned(db_session: AsyncSession) -> None:
    """All created prompt_usages must have pinned=True."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    await db_session.expire_all()
    result = await db_session.execute(text("SELECT pinned FROM prompt_usages"))
    rows = result.fetchall()

    assert all(row[0] is True for row in rows), "All usages must be pinned=True"


@pytest.mark.asyncio
async def test_backfill_idempotent_on_rerun(db_session: AsyncSession) -> None:
    """Re-running the migration inserts 0 additional rows."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()

        await db_session.expire_all()
        n_prompts_1 = await _count_rows(db_session, "prompts")

        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    await db_session.expire_all()
    n_prompts_2 = await _count_rows(db_session, "prompts")

    assert n_prompts_1 == n_prompts_2, f"Idempotency violated: {n_prompts_1} -> {n_prompts_2}"


@pytest.mark.asyncio
async def test_backfill_downgrade_removes_all_inline_rows(db_session: AsyncSession) -> None:
    """downgrade() removes all inline-created prompts/versions/usages and restores JSONB."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()

        with sync_engine.connect() as conn:
            _run_downgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    await db_session.expire_all()
    assert await _count_rows(db_session, "prompts") == 0
    assert await _count_rows(db_session, "prompt_versions") == 0
    assert await _count_rows(db_session, "prompt_usages") == 0

    dag1 = await _fetch_dag(db_session, _SV_ID_1)
    nodes = {n["id"]: n for n in dag1["nodes"]}
    assert not nodes["node-txt-1"].get("prompt_id"), "prompt_id must be cleared by downgrade"


@pytest.mark.asyncio
async def test_backfill_prompt_template_preserved_after_upgrade(
    db_session: AsyncSession,
) -> None:
    """Regression: prompt_template field must survive the upgrade unchanged."""
    await _insert_fixtures(db_session)

    sync_url = settings.database_url.replace("+asyncpg", "")
    sync_engine = sa.create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            _run_upgrade(conn)
            conn.commit()
    finally:
        sync_engine.dispose()

    await db_session.expire_all()
    dag2 = await _fetch_dag(db_session, _SV_ID_2)
    node3 = next(n for n in dag2["nodes"] if n["id"] == "node-txt-2")
    assert node3["prompt_template"] == "Welcome to {company}.", (
        "prompt_template must be preserved verbatim"
    )
