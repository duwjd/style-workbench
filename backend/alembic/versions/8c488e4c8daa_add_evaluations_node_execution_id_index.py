"""add evaluations node_execution_id index

Revision ID: 8c488e4c8daa
Revises: 8fcd0834bebf
Create Date: 2026-05-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "8c488e4c8daa"
down_revision: str | None = "8fcd0834bebf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # evaluations.node_execution_id 인덱스 추가.
    # init 마이그레이션(8fcd0834bebf)에서 누락된 인덱스를 보완한다.
    op.create_index(
        "ix_evaluations_node_execution_id",
        "evaluations",
        ["node_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_evaluations_node_execution_id", table_name="evaluations")
