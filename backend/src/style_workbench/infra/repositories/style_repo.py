from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.core.ids import new_ulid
from style_workbench.domain.style.entity import DAG, Style
from style_workbench.domain.style.schema import dag_from_dict, dag_to_dict
from style_workbench.infra.db.models.style import Style as StyleORM
from style_workbench.infra.db.models.style import StyleVersion as StyleVersionORM


@dataclass
class StyleRecord:
    style: Style
    version_id: str
    created_at: datetime


class StyleRepository(Protocol):
    async def save(self, style: Style) -> StyleRecord: ...
    async def get(self, style_id: str) -> StyleRecord | None: ...
    async def get_version(self, style_version_id: str) -> tuple[str, DAG] | None: ...
    async def list(self, limit: int = 50, offset: int = 0) -> list[StyleRecord]: ...
    async def update_status(self, style_id: str, status: str) -> StyleRecord | None: ...


class SqlAlchemyStyleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, style: Style) -> StyleRecord:
        version_id = new_ulid()
        orm_style = StyleORM(
            id=style.id,
            name=style.name,
            concept=style.concept,
            vertical=style.vertical,
            tags=style.tags,
            status=style.status,
            current_version=style.current_version,
            created_by=style.created_by,
        )
        orm_version = StyleVersionORM(
            id=version_id,
            style_id=style.id,
            version=style.current_version,
            dag=dag_to_dict(style.dag),
        )
        self._session.add(orm_style)
        self._session.add(orm_version)
        await self._session.flush()
        await self._session.refresh(orm_style)
        return StyleRecord(
            style=style,
            version_id=version_id,
            created_at=orm_style.created_at,
        )

    async def get(self, style_id: str) -> StyleRecord | None:
        stmt = (
            select(StyleORM, StyleVersionORM)
            .join(StyleVersionORM, StyleVersionORM.style_id == StyleORM.id)
            .where(StyleORM.id == style_id)
            .where(StyleVersionORM.version == StyleORM.current_version)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        orm_style, orm_version = row.tuple()
        style = _orm_to_domain(orm_style, orm_version)
        return StyleRecord(
            style=style,
            version_id=orm_version.id,
            created_at=orm_style.created_at,
        )

    async def get_version(self, style_version_id: str) -> tuple[str, DAG] | None:
        stmt = select(StyleVersionORM).where(StyleVersionORM.id == style_version_id)
        orm_version = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm_version is None:
            return None
        dag_data: dict[str, Any] = orm_version.dag
        return orm_version.style_id, dag_from_dict(dag_data)

    async def list(self, limit: int = 50, offset: int = 0) -> list[StyleRecord]:
        stmt = (
            select(StyleORM, StyleVersionORM)
            .join(StyleVersionORM, StyleVersionORM.style_id == StyleORM.id)
            .where(StyleVersionORM.version == StyleORM.current_version)
            .order_by(StyleORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            StyleRecord(
                style=_orm_to_domain(orm_style, orm_version),
                version_id=orm_version.id,
                created_at=orm_style.created_at,
            )
            for orm_style, orm_version in (row.tuple() for row in rows)
        ]

    async def update_status(self, style_id: str, status: str) -> StyleRecord | None:
        stmt = select(StyleORM).where(StyleORM.id == style_id)
        orm_style = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm_style is None:
            return None
        orm_style.status = status
        await self._session.flush()
        return await self.get(style_id)


def _orm_to_domain(orm_style: StyleORM, orm_version: StyleVersionORM) -> Style:
    dag_data: dict[str, Any] = orm_version.dag
    dag = dag_from_dict(dag_data)
    return Style(
        id=orm_style.id,
        name=orm_style.name,
        concept=orm_style.concept or "",
        vertical=orm_style.vertical or "",
        tags=list(orm_style.tags) if orm_style.tags else [],
        status=orm_style.status,
        current_version=orm_style.current_version,
        dag=dag,
        created_by=orm_style.created_by,
    )
