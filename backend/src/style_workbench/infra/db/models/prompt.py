"""SQLAlchemy ORM models for the Prompt Library (F05).

Tables:
    prompts            — Prompt meta (spec §5.1)
    prompt_versions    — Immutable body snapshots (spec §5.2)
    prompt_usages      — StyleVersion-node → PromptVersion links (spec §5.3)

Note: prompts.current_version_id FK to prompt_versions is added via
      ALTER TABLE in the Alembic migration to avoid circular creation order.
      We declare it here as a plain ForeignKey so SQLAlchemy relationship()
      works at runtime, but the migration script must handle ordering.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class PromptORM(Base):
    """ORM model for the ``prompts`` table."""

    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    # current_version_id FK to prompt_versions added via ALTER in migration.
    current_version_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("prompt_versions.id", use_alter=True, name="fk_prompts_current_version_id"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    imported_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list[PromptVersionORM]] = relationship(
        "PromptVersionORM",
        back_populates="prompt",
        foreign_keys="PromptVersionORM.prompt_id",
        cascade="all, delete-orphan",
    )
    current_version: Mapped[PromptVersionORM | None] = relationship(
        "PromptVersionORM",
        foreign_keys=[current_version_id],
        lazy="select",
    )
    usages: Mapped[list[PromptUsageORM]] = relationship(
        "PromptUsageORM",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )


class PromptVersionORM(Base):
    """ORM model for the ``prompt_versions`` table."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_id_version"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    prompt_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # [{name, role, required}]
    declared_variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    # {provider, model_id} optional
    model_default: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    parent_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("prompt_versions.id"), nullable=True
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    prompt: Mapped[PromptORM] = relationship(
        "PromptORM",
        back_populates="versions",
        foreign_keys=[prompt_id],
    )


class PromptUsageORM(Base):
    """ORM model for the ``prompt_usages`` table."""

    __tablename__ = "prompt_usages"
    __table_args__ = (
        UniqueConstraint("style_version_id", "node_id", name="uq_prompt_usages_style_version_node"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    prompt_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    prompt_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompt_versions.id", ondelete="CASCADE"), nullable=False
    )
    style_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("style_versions.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_run_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prompt: Mapped[PromptORM] = relationship("PromptORM", back_populates="usages")


class PromptAbComparisonORM(Base):
    """ORM model for the ``prompt_ab_comparisons`` table.

    Stores A/B comparison triggers (spec §4 FR-8, §13 단계 5).
    """

    __tablename__ = "prompt_ab_comparisons"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    prompt_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    from_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompt_versions.id", ondelete="CASCADE"), nullable=False
    )
    to_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("prompt_versions.id", ondelete="CASCADE"), nullable=False
    )
    style_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("style_versions.id", ondelete="CASCADE"), nullable=False
    )
    user_input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    from_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    to_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
