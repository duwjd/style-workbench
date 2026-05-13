"""SQLAlchemy ORM model for retry_attempts table (F01 §5.1).

Maps to the retry_attempts table created by Alembic migration
add_retry_attempts_table.  All FK relationships are declared here for
SQLAlchemy relationship() introspection; the migration script manages
creation ordering and CONCURRENTLY indexes.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class RetryAttemptORM(Base):
    """One row per (node_execution_id, attempt_number) within a Run.

    attempt_number:
        0  = first (original) execution attempt — retry_guidance is NULL.
        1+ = subsequent retries after a FAIL evaluation.

    cost_won reflects only *this* attempt's cost (not cumulative run total).
    The cumulative total is kept in runs.total_cost.
    """

    __tablename__ = "retry_attempts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    node_execution_id: Mapped[str] = mapped_column(
        Text, ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version_id_used: Mapped[str | None] = mapped_column(
        Text, ForeignKey("prompt_versions.id"), nullable=True
    )
    # JSONB nullable: NULL for attempt_number == 0 (first try, no prior guidance)
    retry_guidance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    evaluation_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("evaluations.id"), nullable=True
    )
    cost_won: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "node_execution_id", "attempt_number", name="uq_retry_attempts_ne_attempt"
        ),
        CheckConstraint("attempt_number >= 0", name="retry_attempts_attempt_chk"),
    )
