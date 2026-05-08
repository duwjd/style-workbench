from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    concept: Mapped[str | None] = mapped_column(Text, nullable=True)
    vertical: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list[StyleVersion]] = relationship(
        "StyleVersion",
        back_populates="style",
        cascade="all, delete-orphan",
    )


class StyleVersion(Base):
    __tablename__ = "style_versions"
    __table_args__ = (
        UniqueConstraint("style_id", "version", name="uq_style_versions_style_id_version"),
        Index("idx_style_versions_dag", "dag", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    style_id: Mapped[str] = mapped_column(
        Text, ForeignKey("styles.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dag: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    brief: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parent_variant_of: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    style: Mapped[Style] = relationship("Style", back_populates="versions")
