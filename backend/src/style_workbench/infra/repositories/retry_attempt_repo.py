"""SQLAlchemy implementation of RetryAttemptRepo (F01 §FR-4, §5.1).

Convention (backend/CLAUDE.md §5.3):
  - Protocol defined in domain/auto_loop/repo.py.
  - This module contains only the SQLAlchemy implementation.
  - ORM models are never exposed beyond this module.
  - All methods return domain entities (RetryAttempt), not ORM rows.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import outerjoin

from style_workbench.domain.auto_loop.entity import RetryAttempt, RetryAttemptWithEval
from style_workbench.infra.db.models.evaluation import Evaluation
from style_workbench.infra.db.models.retry_attempt import RetryAttemptORM


class SqlAlchemyRetryAttemptRepo:
    """Async SQLAlchemy implementation of RetryAttemptRepo Protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, retry_attempt: RetryAttempt) -> RetryAttempt:
        """Persist a new RetryAttempt row and return the saved entity.

        flush() ensures the row is visible within the current transaction
        (needed if subsequent queries within the same unit-of-work depend on it).
        """
        orm = RetryAttemptORM(
            id=retry_attempt.id,
            run_id=retry_attempt.run_id,
            node_execution_id=retry_attempt.node_execution_id,
            node_id=retry_attempt.node_id,
            attempt_number=retry_attempt.attempt_number,
            prompt_version_id_used=retry_attempt.prompt_version_id_used,
            retry_guidance=retry_attempt.retry_guidance,
            evaluation_id=retry_attempt.evaluation_id,
            cost_won=retry_attempt.cost_won,
            started_at=retry_attempt.started_at,
            finished_at=retry_attempt.finished_at,
        )
        self._session.add(orm)
        await self._session.flush()
        return _orm_to_entity(orm)

    async def list_by_run(self, run_id: str) -> list[RetryAttempt]:
        """Return all retry attempts for the given run, ordered by started_at ASC."""
        stmt = (
            select(RetryAttemptORM)
            .where(RetryAttemptORM.run_id == run_id)
            .order_by(RetryAttemptORM.started_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_entity(row) for row in rows]

    async def list_by_node_execution(self, node_execution_id: str) -> list[RetryAttempt]:
        """Return all retry attempts for a node execution, ordered by attempt_number ASC."""
        stmt = (
            select(RetryAttemptORM)
            .where(RetryAttemptORM.node_execution_id == node_execution_id)
            .order_by(RetryAttemptORM.attempt_number.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_entity(row) for row in rows]

    async def list_with_evaluations(self, run_id: str) -> list[RetryAttemptWithEval]:
        """Return retry attempts with evaluation outcome via single LEFT OUTER JOIN.

        Ordered by (node_id, attempt_number) ASC to group per-node timelines.
        For attempts with evaluation_id IS NULL (budget guard fired), passed=None
        and failed_dimensions=[].
        """
        j = outerjoin(
            RetryAttemptORM,
            Evaluation,
            RetryAttemptORM.evaluation_id == Evaluation.id,
        )
        stmt = (
            select(RetryAttemptORM, Evaluation)
            .select_from(j)
            .where(RetryAttemptORM.run_id == run_id)
            .order_by(RetryAttemptORM.node_id.asc(), RetryAttemptORM.attempt_number.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_orm_to_with_eval(attempt_orm, eval_orm) for attempt_orm, eval_orm in rows]


def _orm_to_entity(orm: RetryAttemptORM) -> RetryAttempt:
    return RetryAttempt(
        id=orm.id,
        run_id=orm.run_id,
        node_execution_id=orm.node_execution_id,
        node_id=orm.node_id,
        attempt_number=orm.attempt_number,
        cost_won=orm.cost_won if orm.cost_won is not None else Decimal("0"),
        started_at=orm.started_at,
        prompt_version_id_used=orm.prompt_version_id_used,
        retry_guidance=orm.retry_guidance,
        evaluation_id=orm.evaluation_id,
        finished_at=orm.finished_at,
    )


def _orm_to_with_eval(
    attempt_orm: RetryAttemptORM,
    eval_orm: Evaluation | None,
) -> RetryAttemptWithEval:
    attempt = _orm_to_entity(attempt_orm)
    if eval_orm is None:
        # Budget guard fired before evaluator — no evaluation row
        return RetryAttemptWithEval(attempt=attempt, passed=None, failed_dimensions=[])
    passed = eval_orm.overall_result == "pass"
    failed_dims: list[str] = list(eval_orm.failed_dimensions) if eval_orm.failed_dimensions else []
    return RetryAttemptWithEval(attempt=attempt, passed=passed, failed_dimensions=failed_dims)
