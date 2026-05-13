"""Domain entity for retry attempt tracking (F01 §FR-4, §5.1).

RetryAttempt records a single node execution attempt within an auto-evaluation
loop run.  One row per (node_execution_id, attempt_number) pair.

Domain layer: NO imports from services / infra / adapters / engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class RetryAttempt:
    """Immutable record of one attempt to execute a DAG node.

    Fields map 1-to-1 with retry_attempts table columns (spec §5.1).

    attempt_number starts at 0 (first attempt = 0, first retry = 1, ...).
    retry_guidance is None for attempt_number == 0 (no prior failure yet).
    evaluation_id is None until the evaluation step completes for this attempt.
    prompt_version_id_used is None for inline-prompt nodes (no PromptVersion FK).
    """

    id: str
    run_id: str
    node_execution_id: str
    node_id: str
    attempt_number: int
    cost_won: Decimal
    started_at: datetime
    prompt_version_id_used: str | None = None
    retry_guidance: dict[str, object] | None = None
    evaluation_id: str | None = None
    finished_at: datetime | None = None


@dataclass
class RetryAttemptWithEval:
    """RetryAttempt enriched with evaluation outcome fields.

    Used by the GET /api/runs/{run_id}/retry-attempts endpoint to avoid
    N+1 queries.  passed and failed_dimensions are resolved from the
    joined Evaluation row (NULL evaluation_id → passed=None).
    """

    attempt: RetryAttempt
    # None when evaluation_id is NULL (budget guard fired before evaluator)
    passed: bool | None
    failed_dimensions: list[str]
