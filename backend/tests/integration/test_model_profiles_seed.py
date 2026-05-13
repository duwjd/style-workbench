"""Integration test: Phase-1 model_profiles seed migration

Verifies that after `alembic upgrade head` the model_profiles table contains
exactly the 8 Phase-1 models with correct provider/type assignments.

Requires a live database (skipped if DATABASE_URL is unavailable).
Run with:  pytest tests/integration/test_model_profiles_seed.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Expected rows inserted by migration c3a1f9b2e045_seed_model_profiles_phase1
_EXPECTED_SEED = [
    # (name, type, provider, model_id in profile)
    ("GPT-5.4", "text", "openai", "gpt-5.4"),
    ("Claude Sonnet 4.6", "text", "anthropic", "claude-sonnet-4-6"),
    ("Claude Opus 4.6", "text", "anthropic", "claude-opus-4-6"),
    ("Nano Banana Pro", "image", "replicate", "google/nano-banana-pro"),
    ("GPT-Image-1", "image", "openai", "gpt-image-1"),
    ("Kling v2.5 Turbo Pro", "video", "replicate", "kuaishou/kling-v2.5-turbo-pro"),
    ("Seedance 1.5 Pro", "video", "replicate", "bytedance/seedance-1.5-pro"),
    ("Runway Gen3", "video", "replicate", "runway/gen3"),
]

_SEED_TAG = "seed_phase1"


@pytest.mark.asyncio
async def test_seed_phase1_row_count(session: AsyncSession) -> None:
    """model_profiles must have at least 8 seed_phase1 rows after migration."""
    result = await session.execute(
        text("SELECT COUNT(*) FROM model_profiles WHERE imported_from = :tag"),
        {"tag": _SEED_TAG},
    )
    count = result.scalar_one()
    assert count == 8, (
        f"Expected 8 seed_phase1 rows in model_profiles, got {count}. "
        "Run: uv run alembic upgrade head"
    )


@pytest.mark.asyncio
async def test_seed_phase1_model_ids_present(session: AsyncSession) -> None:
    """Each Phase-1 model must be findable by its model_id in the JSONB profile."""
    for name, type_, provider, model_id in _EXPECTED_SEED:
        result = await session.execute(
            text(
                "SELECT id, name, type, provider FROM model_profiles"
                " WHERE imported_from = :tag"
                " AND profile->>'model_id' = :model_id"
            ),
            {"tag": _SEED_TAG, "model_id": model_id},
        )
        row = result.fetchone()
        assert row is not None, (
            f"model_id={model_id!r} not found in model_profiles (seed_phase1). "
            "Check migration c3a1f9b2e045."
        )
        assert row.name == name, f"name mismatch for {model_id}: {row.name!r} != {name!r}"
        assert row.type == type_, f"type mismatch for {model_id}: {row.type!r} != {type_!r}"
        assert row.provider == provider, (
            f"provider mismatch for {model_id}: {row.provider!r} != {provider!r}"
        )


@pytest.mark.asyncio
async def test_seed_phase1_profiles_have_model_id_field(session: AsyncSession) -> None:
    """Every seed_phase1 row must have a non-empty model_id inside the JSONB profile."""
    result = await session.execute(
        text(
            "SELECT name, profile->>'model_id' AS model_id"
            " FROM model_profiles"
            " WHERE imported_from = :tag"
        ),
        {"tag": _SEED_TAG},
    )
    rows = result.fetchall()
    missing = [r.name for r in rows if not r.model_id]
    assert not missing, f"These seed rows have no model_id in profile: {missing}"


@pytest.mark.asyncio
async def test_seed_phase1_all_types_represented(session: AsyncSession) -> None:
    """Phase-1 seed must include text, image, and video model types."""
    result = await session.execute(
        text("SELECT DISTINCT type FROM model_profiles WHERE imported_from = :tag"),
        {"tag": _SEED_TAG},
    )
    types = {row[0] for row in result.fetchall()}
    assert types == {"text", "image", "video"}, (
        f"Expected types {{text, image, video}}, got {types}"
    )
