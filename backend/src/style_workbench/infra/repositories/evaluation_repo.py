from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.infra.db.models.evaluation import Evaluation
from style_workbench.infra.db.models.run import NodeExecution as NodeExecutionORM


@dataclass
class EvaluationRecord:
    """Repo 계층 전용 record — 도메인 엔티티와 별도로 persistence 필드를 포함한다."""

    id: str
    node_execution_id: str
    # node_id / node_type 은 node_executions JOIN 으로 보강 (list_by_run 에서 사용)
    node_id: str
    node_type: str
    evaluator_model: str
    overall_result: str
    dimensions: list[dict[str, Any]]
    retry_guidance: dict[str, Any] | None
    failed_dimensions: list[str] = field(default_factory=list)
    human_verdict: str | None = None
    human_comment: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EvaluationRepository(Protocol):
    async def save(self, result: EvaluationResult) -> None: ...

    async def get_by_node_execution(self, ne_id: str) -> list[EvaluationResult]: ...

    async def get_record_by_id(self, evaluation_id: str) -> EvaluationRecord | None: ...

    async def list_by_run(self, run_id: str) -> list[EvaluationRecord]: ...

    async def update_human_verdict(
        self,
        evaluation_id: str,
        verdict: str,
        comment: str | None,
    ) -> EvaluationRecord | None: ...


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, result: EvaluationResult) -> None:
        orm = Evaluation(
            id=result.id,
            node_execution_id=result.node_execution_id,
            evaluator_model=result.evaluator_model,
            overall_result=result.overall_result,
            dimensions=[
                {"name": d.name, "score": d.score, "rationale": d.rationale}
                for d in result.dimensions
            ],
            retry_guidance=result.retry_guidance,
            failed_dimensions=result.failed_dimensions,
        )
        self._session.add(orm)
        await self._session.flush()

    async def get_by_node_execution(self, ne_id: str) -> list[EvaluationResult]:
        stmt = select(Evaluation).where(Evaluation.node_execution_id == ne_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_entity(row) for row in rows]

    async def get_record_by_id(self, evaluation_id: str) -> EvaluationRecord | None:
        stmt = (
            select(Evaluation, NodeExecutionORM.node_id, NodeExecutionORM.node_type)
            .join(NodeExecutionORM, NodeExecutionORM.id == Evaluation.node_execution_id)
            .where(Evaluation.id == evaluation_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        orm_eval, node_id, node_type = row.tuple()
        return _orm_to_record(orm_eval, node_id=str(node_id), node_type=str(node_type))

    async def list_by_run(self, run_id: str) -> list[EvaluationRecord]:
        """run_id 에 속한 모든 node_execution 의 evaluation 을 반환한다."""
        stmt = (
            select(Evaluation, NodeExecutionORM.node_id, NodeExecutionORM.node_type)
            .join(NodeExecutionORM, NodeExecutionORM.id == Evaluation.node_execution_id)
            .where(NodeExecutionORM.run_id == run_id)
            .order_by(Evaluation.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            _orm_to_record(orm_eval, node_id=str(node_id), node_type=str(node_type))
            for orm_eval, node_id, node_type in (row.tuple() for row in rows)
        ]

    async def update_human_verdict(
        self,
        evaluation_id: str,
        verdict: str,
        comment: str | None,
    ) -> EvaluationRecord | None:
        stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
        orm_eval = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm_eval is None:
            return None
        orm_eval.human_verdict = verdict
        orm_eval.human_comment = comment
        await self._session.flush()
        return await self.get_record_by_id(evaluation_id)


def _tz_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _orm_to_entity(orm: Evaluation) -> EvaluationResult:
    dimensions: list[DimensionScore] = [
        DimensionScore(
            name=str(d["name"]),
            score=float(d["score"]),
            rationale=str(d["rationale"]),
        )
        for d in orm.dimensions
    ]
    return EvaluationResult(
        id=orm.id,
        node_execution_id=orm.node_execution_id,
        evaluator_model=orm.evaluator_model,
        dimensions=dimensions,
        notable_issues=[],
        retry_guidance=orm.retry_guidance,
        created_at=_tz_aware(orm.created_at),
    )


def _orm_to_record(
    orm: Evaluation,
    *,
    node_id: str,
    node_type: str,
) -> EvaluationRecord:
    failed_dims: list[str] = list(orm.failed_dimensions) if orm.failed_dimensions else []
    return EvaluationRecord(
        id=orm.id,
        node_execution_id=orm.node_execution_id,
        node_id=node_id,
        node_type=node_type,
        evaluator_model=orm.evaluator_model,
        overall_result=orm.overall_result,
        dimensions=list(orm.dimensions),
        retry_guidance=orm.retry_guidance,
        failed_dimensions=failed_dims,
        human_verdict=orm.human_verdict,
        human_comment=orm.human_comment,
        created_at=_tz_aware(orm.created_at),
    )
