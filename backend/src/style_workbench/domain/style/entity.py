from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NodeType(StrEnum):
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    COMPOSITION = "composition"


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model_id: str


@dataclass(frozen=True)
class NodeInput:
    source: str  # "user_input" | "node_output:<node_id>"
    role: str


@dataclass
class Node:
    id: str
    type: NodeType
    model: ModelRef
    prompt_template: str
    inputs: list[NodeInput] = field(default_factory=list)
    output_schema: dict[str, str] | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    target: str


@dataclass
class DAG:
    nodes: list[Node]
    edges: list[Edge]
    variables: list[str] = field(default_factory=list)


@dataclass
class Style:
    id: str
    name: str
    concept: str
    vertical: str
    tags: list[str]
    status: str
    current_version: int
    dag: DAG
    created_by: str | None = None
