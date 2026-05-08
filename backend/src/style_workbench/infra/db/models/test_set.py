from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class TestSet(Base):
    __tablename__ = "test_sets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list[TestSetItem]] = relationship(
        "TestSetItem",
        back_populates="test_set",
        cascade="all, delete-orphan",
    )


class TestSetItem(Base):
    __tablename__ = "test_set_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    test_set_id: Mapped[str] = mapped_column(
        Text, ForeignKey("test_sets.id", ondelete="CASCADE"), nullable=False
    )
    files: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # `metadata` is reserved on SQLAlchemy's DeclarativeBase — use item_metadata as Python attr
    item_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    test_set: Mapped[TestSet] = relationship("TestSet", back_populates="items")
