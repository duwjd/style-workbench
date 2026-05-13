from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class DimensionScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    score: float
    rationale: str


class EvaluationResponse(BaseModel):
    """GET /runs/{run_id}/evaluations 및 POST /evaluations/{id}/verdict 공통 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    node_execution_id: str
    node_id: str
    node_type: str
    evaluator_model: str
    overall_result: str
    dimensions: list[dict[str, Any]]
    retry_guidance: dict[str, Any] | None
    failed_dimensions: list[str] = []
    human_verdict: str | None
    human_comment: str | None
    created_at: datetime


class VerdictRequest(BaseModel):
    verdict: Literal["approved", "rejected"]
    comment: str | None = None
