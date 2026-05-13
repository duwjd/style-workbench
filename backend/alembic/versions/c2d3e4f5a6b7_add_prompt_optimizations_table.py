"""add prompt_optimizations table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-12 00:00:00.000000

F02 Prompt Optimizer — spec §5.1.

DDL:
    prompt_optimizations — F02 Prompt Optimizer 호출 1건당 row 1개.
      - FK to prompts (CASCADE), prompt_versions (×2: parent + new, CASCADE/SET NULL).
      - succeeded=false row는 failure_reason 필수.
      - cost_won NUMERIC(12,2), latency_ms INT.
      - eval_evidence JSONB: {evaluation_id, run_id, node_execution_id}.

Indexes (모두 CONCURRENTLY — W5 / AC-8):
    idx_prompt_optimizations_prompt_id        — GET /optimizations 쿼리
    idx_prompt_optimizations_parent_version_id — lineage 추적
    idx_prompt_optimizations_created_at        — 최신순 정렬

Downgrade:
    Drops indexes (CONCURRENTLY) then table (exact reverse).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # Create prompt_optimizations table
    # -----------------------------------------------------------------------
    op.create_table(
        "prompt_optimizations",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "prompt_id",
            sa.Text,
            sa.ForeignKey("prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.Text,
            sa.ForeignKey("prompt_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # new_version_id: NULL when F02 call fails (succeeded=false)
        sa.Column(
            "new_version_id",
            sa.Text,
            sa.ForeignKey("prompt_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # retry_guidance JSONB — evaluator가 출력한 수정 지침
        sa.Column(
            "retry_guidance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        # failed_dimensions JSONB array — e.g. ["composition", "lighting"]
        sa.Column(
            "failed_dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        # eval_evidence JSONB — {evaluation_id, run_id, node_execution_id}
        sa.Column(
            "eval_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column(
            "cost_won",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # -----------------------------------------------------------------------
    # Indexes — all CONCURRENTLY (W5 / AC-8)
    # NOTE: CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    #       Alembic handles this with postgresql_concurrently=True by issuing
    #       the statement outside the transaction block.
    # -----------------------------------------------------------------------
    op.create_index(
        "idx_prompt_optimizations_prompt_id",
        "prompt_optimizations",
        ["prompt_id"],
        postgresql_concurrently=True,
    )
    op.create_index(
        "idx_prompt_optimizations_parent_version_id",
        "prompt_optimizations",
        ["parent_version_id"],
        postgresql_concurrently=True,
    )
    op.create_index(
        "idx_prompt_optimizations_created_at",
        "prompt_optimizations",
        [sa.text("created_at DESC")],
        postgresql_concurrently=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_prompt_optimizations_created_at",
        table_name="prompt_optimizations",
        postgresql_concurrently=True,
    )
    op.drop_index(
        "idx_prompt_optimizations_parent_version_id",
        table_name="prompt_optimizations",
        postgresql_concurrently=True,
    )
    op.drop_index(
        "idx_prompt_optimizations_prompt_id",
        table_name="prompt_optimizations",
        postgresql_concurrently=True,
    )
    op.drop_table("prompt_optimizations")
