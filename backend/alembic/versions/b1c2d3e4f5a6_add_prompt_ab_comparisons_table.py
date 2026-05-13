"""add prompt_ab_comparisons table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-05-12 00:00:00.000000

spec §4 FR-8, §13 단계 5 — A/B comparison table.

DDL:
    prompt_ab_comparisons — stores A/B comparison trigger records.
      - FK to prompts, prompt_versions (×2), style_versions, runs (×2).
      - status: running | done | failed.

Indexes:
    idx_prompt_ab_comparisons_prompt_id  (CONCURRENTLY — W5 closing, AC-7)

Downgrade:
    Drops index then table (exact reverse of upgrade).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Create prompt_ab_comparisons table
    # -----------------------------------------------------------------------
    op.create_table(
        "prompt_ab_comparisons",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "prompt_id",
            sa.Text,
            sa.ForeignKey("prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_version_id",
            sa.Text,
            sa.ForeignKey("prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_version_id",
            sa.Text,
            sa.ForeignKey("prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "style_version_id",
            sa.Text,
            sa.ForeignKey("style_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # user_input JSONB — runtime placeholder values
        sa.Column(
            "user_input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Nullable until the respective run is created / completed
        sa.Column(
            "from_run_id",
            sa.Text,
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "to_run_id",
            sa.Text,
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # status: running | done | failed
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -----------------------------------------------------------------------
    # Index — CONCURRENTLY (W5 / AC-7)
    # NOTE: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    #       Alembic wraps migrations in a transaction by default; we use
    #       postgresql_concurrently=True which Alembic handles by issuing the
    #       statement outside the transaction block.
    # -----------------------------------------------------------------------
    op.create_index(
        "idx_prompt_ab_comparisons_prompt_id",
        "prompt_ab_comparisons",
        ["prompt_id"],
        postgresql_concurrently=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_prompt_ab_comparisons_prompt_id",
        table_name="prompt_ab_comparisons",
        postgresql_concurrently=True,
    )
    op.drop_table("prompt_ab_comparisons")
