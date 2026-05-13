"""Repository Protocol for RetryAttempt (F01 §FR-4).

Convention (backend/CLAUDE.md §5.3):
  - Protocol (interface) lives here in domain/auto_loop/repo.py.
  - SQLAlchemy implementation lives in infra/repositories/retry_attempt_repo.py.
  - All methods use domain entities as input/output — no ORM objects here.
  - domain must NOT import from infra / services / api.
"""

from __future__ import annotations

from typing import Protocol

from style_workbench.domain.auto_loop.entity import RetryAttempt, RetryAttemptWithEval


class RetryAttemptRepo(Protocol):
    """Persistence interface for RetryAttempt records."""

    async def create(self, retry_attempt: RetryAttempt) -> RetryAttempt:
        """Persist a new RetryAttempt row and return the saved entity.

        The unique constraint (node_execution_id, attempt_number) is enforced
        at the DB level; callers must not insert duplicates.
        """
        ...

    async def list_by_run(self, run_id: str) -> list[RetryAttempt]:
        """Return all retry attempts for the given run, ordered by started_at ASC."""
        ...

    async def list_by_node_execution(self, node_execution_id: str) -> list[RetryAttempt]:
        """Return all retry attempts for a node execution, ordered by attempt_number ASC."""
        ...

    async def list_with_evaluations(self, run_id: str) -> list[RetryAttemptWithEval]:
        """Return retry attempts with evaluation outcome via single JOIN query.

        Ordered by (node_id, attempt_number) ASC to group per-node timelines.
        passed and failed_dimensions are resolved from the joined Evaluation row.
        For attempts where evaluation_id IS NULL (budget guard fired first),
        passed is None and failed_dimensions is [].
        """
        ...
