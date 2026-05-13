"""SQLAlchemy 2.0 async implementation of PromptOptimizationRepo (F02).

Convention (backend/CLAUDE.md §5.3):
  - Protocol interface lives in domain/prompt/optimization.py.
  - This module implements the protocol.
  - ORM ↔ domain entity conversion is done by module-private helper functions.
  - ORM models are NEVER returned to callers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.domain.prompt.optimization import PromptOptimization
from style_workbench.infra.db.models.prompt_optimization import PromptOptimizationORM

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Private ORM ↔ domain helpers
# ---------------------------------------------------------------------------


def _optimization_to_orm(opt: PromptOptimization) -> PromptOptimizationORM:
    return PromptOptimizationORM(
        id=opt.id,
        prompt_id=opt.prompt_id,
        parent_version_id=opt.parent_version_id,
        new_version_id=opt.new_version_id,
        retry_guidance=dict(opt.retry_guidance),
        failed_dimensions=list(opt.failed_dimensions),
        eval_evidence=dict(opt.eval_evidence) if opt.eval_evidence is not None else None,
        change_summary=opt.change_summary,
        cost_won=opt.cost_won,
        latency_ms=opt.latency_ms,
        succeeded=opt.succeeded,
        failure_reason=opt.failure_reason,
    )


def _orm_to_optimization(orm: PromptOptimizationORM) -> PromptOptimization:
    return PromptOptimization(
        id=orm.id,
        prompt_id=orm.prompt_id,
        parent_version_id=orm.parent_version_id,
        new_version_id=orm.new_version_id,
        retry_guidance=dict(orm.retry_guidance) if orm.retry_guidance else {},
        failed_dimensions=list(orm.failed_dimensions) if orm.failed_dimensions else [],
        eval_evidence=_coerce_eval_evidence(orm.eval_evidence),
        change_summary=orm.change_summary,
        cost_won=Decimal(str(orm.cost_won)) if orm.cost_won is not None else Decimal("0"),
        latency_ms=orm.latency_ms,
        succeeded=orm.succeeded,
        failure_reason=orm.failure_reason,
        created_at=_ensure_utc(orm.created_at),
    )


def _coerce_eval_evidence(data: Any) -> dict[str, str] | None:
    if data is None:
        return None
    return {str(k): str(v) for k, v in data.items()}


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ---------------------------------------------------------------------------
# Repository implementation
# ---------------------------------------------------------------------------


class SqlAlchemyPromptOptimizationRepo:
    """SQLAlchemy 2.0 async implementation of PromptOptimizationRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, opt: PromptOptimization) -> PromptOptimization:
        """Insert a new PromptOptimization row and return it with DB-assigned timestamps."""
        orm = _optimization_to_orm(opt)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        logger.info(
            "prompt_optimization_created",
            optimization_id=orm.id,
            prompt_id=orm.prompt_id,
            succeeded=orm.succeeded,
        )
        return _orm_to_optimization(orm)

    async def list_for_prompt(
        self, prompt_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[PromptOptimization], int]:
        """Return (items, total) for the given prompt, ordered by created_at DESC."""
        count_stmt = select(func.count()).where(PromptOptimizationORM.prompt_id == prompt_id)
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(PromptOptimizationORM)
            .where(PromptOptimizationORM.prompt_id == prompt_id)
            .order_by(PromptOptimizationORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(page_stmt)).scalars().all()
        return [_orm_to_optimization(row) for row in rows], total

    async def get(self, optimization_id: str) -> PromptOptimization | None:
        """Return a PromptOptimization by its id, or None if not found."""
        stmt = select(PromptOptimizationORM).where(PromptOptimizationORM.id == optimization_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_optimization(orm)
