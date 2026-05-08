from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.base import Base


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=new_ulid)
    style_version_id: Mapped[str] = mapped_column(
        Text, ForeignKey("style_versions.id"), nullable=False
    )
    format: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    exported_by: Mapped[str | None] = mapped_column(Text, nullable=True)
