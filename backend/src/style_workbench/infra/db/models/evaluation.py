from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    node_execution_id: Mapped[str] = mapped_column(
        Text, ForeignKey("node_executions.id", ondelete="CASCADE"), nullable=False
    )
    evaluator_model: Mapped[str] = mapped_column(Text, nullable=False)
    overall_result: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    retry_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
