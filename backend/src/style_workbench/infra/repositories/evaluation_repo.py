from __future__ import annotations

from datetime import UTC
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.infra.db.models.evaluation import Evaluation


class EvaluationRepository(Protocol):
    async def save(self, result: EvaluationResult) -> None: ...

    async def get_by_node_execution(self, ne_id: str) -> list[EvaluationResult]: ...


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
        )
        self._session.add(orm)
        await self._session.flush()

    async def get_by_node_execution(self, ne_id: str) -> list[EvaluationResult]:
        stmt = select(Evaluation).where(Evaluation.node_execution_id == ne_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_entity(row) for row in rows]


def _orm_to_entity(orm: Evaluation) -> EvaluationResult:
    dimensions: list[DimensionScore] = []
    for d in orm.dimensions:
        dimensions.append(
            DimensionScore(
                name=str(d["name"]),
                score=float(d["score"]),
                rationale=str(d["rationale"]),
            )
        )
    # DB의 created_at은 timezone-aware datetime이어야 함.
    # SQLAlchemy DateTime(timezone=True)로 정의되어 있으므로 tzinfo가 있음.
    created_at = orm.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return EvaluationResult(
        id=orm.id,
        node_execution_id=orm.node_execution_id,
        evaluator_model=orm.evaluator_model,
        dimensions=dimensions,
        notable_issues=[],
        retry_guidance=orm.retry_guidance,
        created_at=created_at,
    )
