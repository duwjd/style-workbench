"""SQLAlchemy ORM model for the prompt_optimizations table (F02).

spec §5.1:
    prompt_optimizations — F02 Prompt Optimizer 호출 1건당 row 1개.

Design notes:
    - 기존 테이블 변경 없음 (spec §5.2).
    - prompt_versions.parent_version_id 는 F05 단계 1에서 이미 존재.
    - eval_evidence JSONB 는 {evaluation_id, run_id, node_execution_id} 를 담는다.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class PromptOptimizationORM(Base):
    """ORM model for the ``prompt_optimizations`` table."""

    __tablename__ = "prompt_optimizations"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)

    prompt_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    new_version_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    retry_guidance: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()),
        nullable=False,
    )
    failed_dimensions: Mapped[list[Any]] = mapped_column(
        JSONB(astext_type=Text()),
        nullable=False,
        server_default="[]",
    )
    # {evaluation_id, run_id, node_execution_id} — F02 호출의 원천 evaluation 참조
    eval_evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(astext_type=Text()),
        nullable=True,
    )

    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    cost_won: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0",
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
