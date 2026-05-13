"""SQLAlchemy 2.0 async implementations of PromptRepo, PromptVersionRepo, PromptUsageRepo.

Convention (backend/CLAUDE.md §5.3):
  - Protocol interfaces live in domain/prompt/repo.py.
  - This module implements those protocols.
  - ORM ↔ domain entity conversion is done by module-private helper functions.
  - ORM models are NEVER returned to callers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import Text, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    ModelDefault,
    NodeType,
    Prompt,
    PromptAbComparison,
    PromptFilters,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.infra.db.models.prompt import (
    PromptAbComparisonORM,
    PromptORM,
    PromptUsageORM,
    PromptVersionORM,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Private ORM ↔ domain helpers
# ---------------------------------------------------------------------------


def _prompt_to_orm(prompt: Prompt) -> PromptORM:
    return PromptORM(
        id=prompt.id,
        name=prompt.name,
        node_type=str(prompt.node_type),
        owner=prompt.owner,
        status=str(prompt.status),
        current_version_id=prompt.current_version_id,
        tags=list(prompt.tags),
        imported_from=prompt.imported_from,
    )


def _orm_to_prompt(orm: PromptORM) -> Prompt:
    return Prompt(
        id=orm.id,
        name=orm.name,
        node_type=NodeType(orm.node_type),
        status=PromptStatus(orm.status),
        owner=orm.owner,
        current_version_id=orm.current_version_id,
        tags=list(orm.tags) if orm.tags else [],
        imported_from=orm.imported_from,
        created_at=_ensure_utc(orm.created_at),
        updated_at=_ensure_utc(orm.updated_at),
    )


def _orm_to_prompt_with_version(orm: PromptORM) -> Prompt:
    prompt = _orm_to_prompt(orm)
    if orm.current_version is not None:
        prompt.current_version = _orm_to_prompt_version(orm.current_version)
    return prompt


def _prompt_version_to_orm(version: PromptVersion) -> PromptVersionORM:
    return PromptVersionORM(
        id=version.id,
        prompt_id=version.prompt_id,
        version=version.version,
        body=version.body,
        declared_variables=_declared_vars_to_jsonb(version.declared_variables),
        model_default=_model_default_to_jsonb(version.model_default),
        parent_version_id=version.parent_version_id,
        change_note=version.change_note,
        created_by=version.created_by,
    )


def _orm_to_prompt_version(orm: PromptVersionORM) -> PromptVersion:
    return PromptVersion(
        id=orm.id,
        prompt_id=orm.prompt_id,
        version=orm.version,
        body=orm.body,
        declared_variables=_jsonb_to_declared_vars(orm.declared_variables),
        model_default=_jsonb_to_model_default(orm.model_default),
        parent_version_id=orm.parent_version_id,
        change_note=orm.change_note,
        created_at=_ensure_utc(orm.created_at),
        created_by=orm.created_by,
    )


def _prompt_usage_to_orm(usage: PromptUsage) -> PromptUsageORM:
    return PromptUsageORM(
        id=usage.id,
        prompt_id=usage.prompt_id,
        prompt_version_id=usage.prompt_version_id,
        style_version_id=usage.style_version_id,
        node_id=usage.node_id,
        pinned=usage.pinned,
        last_run_score=(
            Decimal(str(usage.last_run_score)) if usage.last_run_score is not None else None
        ),
        last_run_at=usage.last_run_at,
    )


def _orm_to_prompt_usage(orm: PromptUsageORM) -> PromptUsage:
    return PromptUsage(
        id=orm.id,
        prompt_id=orm.prompt_id,
        prompt_version_id=orm.prompt_version_id,
        style_version_id=orm.style_version_id,
        node_id=orm.node_id,
        pinned=orm.pinned,
        last_run_score=float(orm.last_run_score) if orm.last_run_score is not None else None,
        last_run_at=_ensure_utc(orm.last_run_at) if orm.last_run_at is not None else None,
        created_at=_ensure_utc(orm.created_at),
    )


# ---------------------------------------------------------------------------
# JSONB serialisation helpers
# ---------------------------------------------------------------------------


def _declared_vars_to_jsonb(
    declared: list[DeclaredVariable],
) -> list[dict[str, Any]]:
    return [{"name": v.name, "role": v.role, "required": v.required} for v in declared]


def _jsonb_to_declared_vars(data: list[dict[str, Any]]) -> list[DeclaredVariable]:
    return [
        DeclaredVariable(
            name=row["name"],
            role=row.get("role", ""),
            required=row.get("required", True),
        )
        for row in (data or [])
    ]


def _model_default_to_jsonb(md: ModelDefault | None) -> dict[str, Any] | None:
    if md is None:
        return None
    return {"provider": md.provider, "model_id": md.model_id}


def _jsonb_to_model_default(data: dict[str, Any] | None) -> ModelDefault | None:
    if not data:
        return None
    return ModelDefault(provider=data["provider"], model_id=data["model_id"])


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ---------------------------------------------------------------------------
# Repository implementations
# ---------------------------------------------------------------------------


class SqlAlchemyPromptRepo:
    """SQLAlchemy 2.0 async implementation of PromptRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, prompt: Prompt) -> Prompt:
        orm = _prompt_to_orm(prompt)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_prompt(orm)

    async def get(self, prompt_id: str) -> Prompt | None:
        stmt = select(PromptORM).where(PromptORM.id == prompt_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_prompt(orm)

    async def get_with_version(self, prompt_id: str) -> Prompt | None:
        stmt = select(PromptORM).where(PromptORM.id == prompt_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        # Eagerly load current_version if current_version_id is set
        if orm.current_version_id is not None:
            ver_stmt = select(PromptVersionORM).where(PromptVersionORM.id == orm.current_version_id)
            version_orm = (await self._session.execute(ver_stmt)).scalar_one_or_none()
            if version_orm is not None:
                orm.current_version = version_orm
        return _orm_to_prompt_with_version(orm)

    async def update(self, prompt: Prompt) -> Prompt:
        stmt = select(PromptORM).where(PromptORM.id == prompt.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            # Caller must verify existence before calling update; this is a safety net.
            raise ValueError(f"Prompt '{prompt.id}' not found during update")
        orm.name = prompt.name
        orm.tags = list(prompt.tags)
        orm.status = str(prompt.status)
        orm.owner = prompt.owner
        orm.current_version_id = prompt.current_version_id
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_prompt(orm)

    async def find_by_imported_from(self, imported_from: str) -> Prompt | None:
        stmt = select(PromptORM).where(PromptORM.imported_from == imported_from)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_prompt(orm)

    async def list(self, filters: PromptFilters) -> list[Prompt]:
        stmt = select(PromptORM)

        if filters.node_type is not None:
            stmt = stmt.where(PromptORM.node_type == str(filters.node_type))
        if filters.status is not None:
            stmt = stmt.where(PromptORM.status == str(filters.status))
        if filters.tags:
            # Use @> (array containment) via literal SQL fragment for GIN index usage.
            # asyncpg requires a proper cast; we bind the tag list as a PostgreSQL array literal.
            stmt = stmt.where(
                PromptORM.tags.contains(sa.cast(sa.literal(filters.tags), ARRAY(Text())))
            )
        if filters.q:
            pattern = f"%{filters.q}%"
            stmt = stmt.where(PromptORM.name.ilike(pattern))

        stmt = (
            stmt.order_by(PromptORM.created_at.desc()).limit(filters.limit).offset(filters.offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_prompt(row) for row in rows]


class SqlAlchemyPromptVersionRepo:
    """SQLAlchemy 2.0 async implementation of PromptVersionRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, version: PromptVersion) -> PromptVersion:
        orm = _prompt_version_to_orm(version)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_prompt_version(orm)

    async def get(self, version_id: str) -> PromptVersion | None:
        stmt = select(PromptVersionORM).where(PromptVersionORM.id == version_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_prompt_version(orm)

    async def get_by_prompt_and_number(self, prompt_id: str, version: int) -> PromptVersion | None:
        stmt = select(PromptVersionORM).where(
            PromptVersionORM.prompt_id == prompt_id,
            PromptVersionORM.version == version,
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_prompt_version(orm)

    async def list_for_prompt(self, prompt_id: str) -> list[PromptVersion]:
        stmt = (
            select(PromptVersionORM)
            .where(PromptVersionORM.prompt_id == prompt_id)
            .order_by(PromptVersionORM.version.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_prompt_version(row) for row in rows]

    async def list_by_prompt(
        self,
        prompt_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PromptVersion], int]:
        """Return paginated versions ordered by version DESC, plus total count.

        Used by GET /api/prompts/{id}/versions (A/B trigger dialog).
        """
        count_stmt = select(func.count()).where(PromptVersionORM.prompt_id == prompt_id)
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(PromptVersionORM)
            .where(PromptVersionORM.prompt_id == prompt_id)
            .order_by(PromptVersionORM.version.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(page_stmt)).scalars().all()
        return [_orm_to_prompt_version(row) for row in rows], total

    async def next_version_number(self, prompt_id: str) -> int:
        stmt = select(func.max(PromptVersionORM.version)).where(
            PromptVersionORM.prompt_id == prompt_id
        )
        max_ver: int | None = (await self._session.execute(stmt)).scalar_one_or_none()
        return (max_ver or 0) + 1


class SqlAlchemyPromptUsageRepo:
    """SQLAlchemy 2.0 async implementation of PromptUsageRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, usage: PromptUsage) -> PromptUsage:
        orm = _prompt_usage_to_orm(usage)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_prompt_usage(orm)

    async def get(self, usage_id: str) -> PromptUsage | None:
        stmt = select(PromptUsageORM).where(PromptUsageORM.id == usage_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_prompt_usage(orm)

    async def list_for_prompt(
        self, prompt_id: str, limit: int = 20, offset: int = 0
    ) -> list[PromptUsage]:
        stmt = (
            select(PromptUsageORM)
            .where(PromptUsageORM.prompt_id == prompt_id)
            .order_by(PromptUsageORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_prompt_usage(row) for row in rows]

    async def count_for_prompt(self, prompt_id: str) -> int:
        stmt = select(func.count()).where(PromptUsageORM.prompt_id == prompt_id)
        count: int = (await self._session.execute(stmt)).scalar_one()
        return count

    async def update_run_score(
        self,
        usage_id: str,
        score: float,
    ) -> PromptUsage | None:
        stmt = select(PromptUsageORM).where(PromptUsageORM.id == usage_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        orm.last_run_score = Decimal(str(score))
        orm.last_run_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_prompt_usage(orm)


# ---------------------------------------------------------------------------
# A/B Comparison ORM ↔ domain helpers
# ---------------------------------------------------------------------------


def _ab_to_orm(ab: PromptAbComparison) -> PromptAbComparisonORM:
    return PromptAbComparisonORM(
        id=ab.id,
        prompt_id=ab.prompt_id,
        from_version_id=ab.from_version_id,
        to_version_id=ab.to_version_id,
        style_version_id=ab.style_version_id,
        user_input=dict(ab.user_input),
        from_run_id=ab.from_run_id,
        to_run_id=ab.to_run_id,
        status=ab.status,
        started_at=ab.started_at,
        finished_at=ab.finished_at,
    )


def _orm_to_ab(orm: PromptAbComparisonORM) -> PromptAbComparison:
    return PromptAbComparison(
        id=orm.id,
        prompt_id=orm.prompt_id,
        from_version_id=orm.from_version_id,
        to_version_id=orm.to_version_id,
        style_version_id=orm.style_version_id,
        user_input=dict(orm.user_input) if orm.user_input else {},
        from_run_id=orm.from_run_id,
        to_run_id=orm.to_run_id,
        status=orm.status,
        created_at=_ensure_utc(orm.created_at),
        started_at=_ensure_utc(orm.started_at) if orm.started_at else None,
        finished_at=_ensure_utc(orm.finished_at) if orm.finished_at else None,
    )


class SqlAlchemyPromptAbComparisonRepo:
    """SQLAlchemy 2.0 async implementation of PromptAbComparisonRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, comparison: PromptAbComparison) -> PromptAbComparison:
        orm = _ab_to_orm(comparison)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_ab(orm)

    async def get(self, ab_id: str) -> PromptAbComparison | None:
        stmt = select(PromptAbComparisonORM).where(PromptAbComparisonORM.id == ab_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return _orm_to_ab(orm)

    async def update(self, comparison: PromptAbComparison) -> PromptAbComparison:
        stmt = select(PromptAbComparisonORM).where(PromptAbComparisonORM.id == comparison.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise ValueError(f"PromptAbComparison '{comparison.id}' not found during update")
        orm.from_run_id = comparison.from_run_id
        orm.to_run_id = comparison.to_run_id
        orm.status = comparison.status
        orm.started_at = comparison.started_at
        orm.finished_at = comparison.finished_at
        await self._session.flush()
        await self._session.refresh(orm)
        return _orm_to_ab(orm)
