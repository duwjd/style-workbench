from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from style_workbench.core.ids import new_ulid
from style_workbench.infra.db.models.run import NodeExecution as NEORM
from style_workbench.infra.db.models.run import Run as RunORM
from style_workbench.infra.db.models.style import StyleVersion as StyleVersionORM


@dataclass
class NodeExecutionRecord:
    id: str
    node_id: str
    node_type: str
    model_provider: str | None
    model_id: str | None
    artifact_url: str | None
    raw_response: dict[str, Any] | None
    cost: Decimal | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None


@dataclass
class RunRecord:
    id: str
    style_version_id: str
    style_id: str
    status: str
    total_cost: Decimal | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    node_executions: list[NodeExecutionRecord] = field(default_factory=list)


class RunRepository(Protocol):
    async def create(self, style_version_id: str, user_input: dict[str, Any]) -> RunRecord: ...

    async def update_status(
        self,
        run_id: str,
        status: str,
        total_cost: Decimal | None = None,
        finished_at: datetime | None = None,
    ) -> None: ...

    async def get(self, run_id: str) -> RunRecord | None: ...

    async def get_node_execution(self, ne_id: str) -> NodeExecutionRecord | None: ...

    async def abort_run(self, run_id: str, finished_at: datetime) -> None: ...


class SqlAlchemyRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, style_version_id: str, user_input: dict[str, Any]) -> RunRecord:
        now = datetime.now(UTC)
        orm_run = RunORM(
            id=new_ulid(),
            style_version_id=style_version_id,
            user_input=user_input,
            status="running",
            started_at=now,
        )
        self._session.add(orm_run)
        await self._session.flush()
        await self._session.refresh(orm_run)
        # resolve style_id from style_versions
        sv_stmt = select(StyleVersionORM.style_id).where(StyleVersionORM.id == style_version_id)
        style_id: str = (await self._session.execute(sv_stmt)).scalar_one()
        return RunRecord(
            id=orm_run.id,
            style_version_id=orm_run.style_version_id,
            style_id=style_id,
            status=orm_run.status,
            total_cost=orm_run.total_cost,
            created_at=orm_run.created_at,
            started_at=orm_run.started_at,
            finished_at=orm_run.finished_at,
            node_executions=[],
        )

    async def update_status(
        self,
        run_id: str,
        status: str,
        total_cost: Decimal | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        stmt = select(RunORM).where(RunORM.id == run_id)
        orm_run = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm_run is None:
            return
        orm_run.status = status
        if total_cost is not None:
            orm_run.total_cost = total_cost
        if finished_at is not None:
            orm_run.finished_at = finished_at
        await self._session.flush()

    async def get(self, run_id: str) -> RunRecord | None:
        stmt = (
            select(RunORM, StyleVersionORM.style_id)
            .options(selectinload(RunORM.node_executions))
            .join(StyleVersionORM, StyleVersionORM.id == RunORM.style_version_id)
            .where(RunORM.id == run_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        orm_run, style_id = row.tuple()
        return _run_orm_to_record(orm_run, style_id=style_id)

    async def get_node_execution(self, ne_id: str) -> NodeExecutionRecord | None:
        stmt = select(NEORM).where(NEORM.id == ne_id)
        ne = (await self._session.execute(stmt)).scalar_one_or_none()
        if ne is None:
            return None
        return _ne_orm_to_record(ne)

    async def abort_run(self, run_id: str, finished_at: datetime) -> None:
        """Mark the run and any running node_executions as aborted."""
        run_stmt = select(RunORM).where(RunORM.id == run_id)
        orm_run = (await self._session.execute(run_stmt)).scalar_one_or_none()
        if orm_run is None:
            return
        orm_run.status = "aborted"
        orm_run.finished_at = finished_at

        # Bulk-update all node_executions that are still in-progress
        ne_stmt = (
            update(NEORM)
            .where(NEORM.run_id == run_id)
            .where(NEORM.status.in_(["running", "pending"]))
            .values(status="aborted", finished_at=finished_at)
        )
        await self._session.execute(ne_stmt)
        await self._session.flush()


def _ne_orm_to_record(ne: NEORM) -> NodeExecutionRecord:
    return NodeExecutionRecord(
        id=ne.id,
        node_id=ne.node_id,
        node_type=ne.node_type,
        model_provider=ne.model_provider,
        model_id=ne.model_id,
        artifact_url=ne.artifact_url,
        raw_response=ne.raw_response,
        cost=ne.cost,
        status=ne.status,
        started_at=ne.started_at,
        finished_at=ne.finished_at,
    )


def _run_orm_to_record(orm_run: RunORM, style_id: str = "") -> RunRecord:
    ne_list: list[NodeExecutionRecord] = []
    for ne in getattr(orm_run, "node_executions", []):
        ne_list.append(_ne_orm_to_record(ne))
    return RunRecord(
        id=orm_run.id,
        style_version_id=orm_run.style_version_id,
        style_id=style_id,
        status=orm_run.status,
        total_cost=orm_run.total_cost,
        created_at=orm_run.created_at,
        started_at=orm_run.started_at,
        finished_at=orm_run.finished_at,
        node_executions=ne_list,
    )
