from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class NodeInputCreate(BaseModel):
    source: str
    role: str


class VariableMappingPayload(BaseModel):
    source: Literal["user_input", "node_output", "constant"]
    role: str | None = None
    node_id: str | None = None
    value: str | None = None

    @model_validator(mode="after")
    def _check_required_fields(self) -> VariableMappingPayload:
        if self.source == "user_input" and not self.role:
            raise ValueError("source='user_input' requires a non-empty 'role'")
        if self.source == "node_output" and not self.node_id:
            raise ValueError("source='node_output' requires a non-empty 'node_id'")
        if self.source == "constant" and self.value is None:
            raise ValueError("source='constant' requires a 'value'")
        return self


class NodeCreate(BaseModel):
    id: str
    type: str
    model: dict[str, str]
    prompt_template: str
    inputs: list[NodeInputCreate] = []
    variable_mapping: dict[str, VariableMappingPayload] = {}


class DagCreate(BaseModel):
    nodes: list[NodeCreate] = []
    edges: list[dict[str, str]] = []
    variables: list[str] = []


class StyleCreateRequest(BaseModel):
    name: str
    concept: str
    vertical: str
    tags: list[str] = []
    dag: DagCreate = DagCreate()


class StyleResponse(BaseModel):
    id: str
    name: str
    concept: str
    vertical: str
    tags: list[str]
    status: str
    current_version: int
    version_id: str
    created_at: datetime


class NodeInputResponse(BaseModel):
    source: str
    role: str


class NodeResponse(BaseModel):
    id: str
    type: str
    model: dict[str, str]
    prompt_template: str
    inputs: list[NodeInputResponse]
    variable_mapping: dict[str, VariableMappingPayload] = {}


class DagResponse(BaseModel):
    nodes: list[NodeResponse]
    edges: list[dict[str, str]]
    variables: list[str]


class StyleDetailResponse(StyleResponse):
    dag: DagResponse


class StyleListItemResponse(BaseModel):
    id: str
    name: str
    concept: str
    vertical: str
    tags: list[str]
    status: str
    current_version: int
    version_id: str
    created_at: datetime


class StyleStatusUpdateRequest(BaseModel):
    status: str  # "approved" | "rejected" | "draft"


class DagCreateRequest(BaseModel):
    dag: DagCreate
    brief: dict[str, object] | None = None


class StyleVersionResponse(BaseModel):
    version_id: str
    version: int
    current_version: int
    created_at: datetime
