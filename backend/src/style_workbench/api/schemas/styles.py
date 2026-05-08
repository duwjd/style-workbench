from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NodeInputCreate(BaseModel):
    source: str
    role: str


class NodeCreate(BaseModel):
    id: str
    type: str
    model: dict[str, str]
    prompt_template: str
    inputs: list[NodeInputCreate] = []


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
