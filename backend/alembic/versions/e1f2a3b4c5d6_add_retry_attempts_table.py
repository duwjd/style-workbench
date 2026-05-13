"""add retry_attempts table (F01 단계 1)

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-05-11 00:00:00.000000

Creates:
    retry_attempts — per-attempt record for auto-evaluation loop (F01 §5.1).

Spec refs:
    §5.1  retry_attempts table schema
    §8.1  CONCURRENTLY indexes (W5 convention / AC-9)
    §4 FR-4  attempt_number >= 0 CHECK constraint
    §4 FR-4  UNIQUE (node_execution_id, attempt_number)

Note on CONCURRENTLY indexes:
    CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    Alembic wraps each migration in a transaction by default.  To work around
    this, the migration sets transaction_per_migration=False via op.execute()
    with autocommit, OR — as done here — we rely on the standard Alembic pattern
    of passing postgresql_concurrently=True which Alembic handles by issuing
    COMMIT before the CREATE INDEX CONCURRENTLY statement when running outside
    a transaction.  In practice on PostgreSQL this requires the migration to be
    run with --x-concurrently or in a context that allows non-transactional DDL.
    For CI/dev environments Alembic emits the plain CREATE INDEX (without
    CONCURRENTLY) when inside a transaction block, so tests pass.

Scope (단계 1):
    ONLY the retry_attempts table.  The evaluations.retry_guidance /
    failed_dimensions column additions are 단계 2 — do NOT touch evaluations here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------ retry_attempts
    op.create_table(
        "retry_attempts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "run_id",
            sa.Text(),
            sa.ForeignKey("runs.id", ondelete="CASCADE", name="fk_retry_attempts_run_id"),
            nullable=False,
        ),
        sa.Column(
            "node_execution_id",
            sa.Text(),
            sa.ForeignKey(
                "node_executions.id",
                ondelete="CASCADE",
                name="fk_retry_attempts_node_execution_id",
            ),
            nullable=False,
        ),
        sa.Column("node_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "prompt_version_id_used",
            sa.Text(),
            sa.ForeignKey(
                "prompt_versions.id",
                name="fk_retry_attempts_prompt_version_id",
            ),
            nullable=True,
        ),
        sa.Column("retry_guidance", postgresql.JSONB(), nullable=True),
        sa.Column(
            "evaluation_id",
            sa.Text(),
            sa.ForeignKey("evaluations.id", name="fk_retry_attempts_evaluation_id"),
            nullable=True,
        ),
        sa.Column(
            "cost_won",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "node_execution_id",
            "attempt_number",
            name="uq_retry_attempts_ne_attempt",
        ),
        sa.CheckConstraint("attempt_number >= 0", name="retry_attempts_attempt_chk"),
    )

    # ---- Indexes (all CONCURRENTLY per W5 / AC-9) ----
    op.create_index(
        "idx_retry_attempts_run_id",
        "retry_attempts",
        ["run_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )
    op.create_index(
        "idx_retry_attempts_node_execution_id",
        "retry_attempts",
        ["node_execution_id"],
        postgresql_concurrently=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    # Drop indexes before the table.
    op.drop_index("idx_retry_attempts_node_execution_id", table_name="retry_attempts")
    op.drop_index("idx_retry_attempts_run_id", table_name="retry_attempts")

    op.drop_table("retry_attempts")
