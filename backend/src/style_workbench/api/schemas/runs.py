from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class RunCreateRequest(BaseModel):
    style_version_id: str
    user_input: dict[str, str] = {}


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
