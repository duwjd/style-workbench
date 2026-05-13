from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class RunCreateRequest(BaseModel):
    style_version_id: str
    user_input: dict[str, str] = {}


class RunAbortRequest(BaseModel):
    reason: str | None = None


class NodeExecutionResponse(BaseModel):
    id: str
    node_id: str
    node_type: str
    model_provider: str | None
    model_id: str | None
    artifact_url: str | None
    cost: Decimal | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None


class RunResponse(BaseModel):
    id: str
    style_version_id: str
    style_id: str
    status: str
    total_cost: Decimal | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    node_executions: list[NodeExecutionResponse]


class RetryAttemptResponse(BaseModel):
    """One attempt row enriched with evaluation outcome (spec §6.2)."""

    id: str
    node_id: str
    attempt_number: int
    prompt_version_id_used: str | None
    # retry_guidance carried from the *prior* failed attempt (None for attempt 0)
    retry_guidance: dict[str, Any] | None
    evaluation_id: str | None
    cost_won: Decimal
    # passed is None when the evaluator was never called (budget guard fired first)
    passed: bool | None
    failed_dimensions: list[str]
    started_at: datetime
    finished_at: datetime | None


class RetryAttemptListResponse(BaseModel):
    """Response for GET /api/runs/{run_id}/retry-attempts (spec §6.2)."""

    run_id: str
    attempts: list[RetryAttemptResponse]
    total_attempts: int
    # succeeded: True if the last attempt's evaluation passed.
    # None when there are no attempts or the last attempt has no evaluation yet.
    succeeded: bool | None
