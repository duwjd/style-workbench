from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


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


@dataclass(frozen=True)
class VariableMapping:
    """Maps a single prompt placeholder to its runtime data source."""

    source: Literal["user_input", "node_output", "constant"]
    # source="user_input": which user-provided role (e.g. "photo", "name")
    role: str | None = None
    # source="node_output": id of the upstream node whose output to use
    node_id: str | None = None
    # source="constant": literal value to substitute
    value: str | None = None

    def __post_init__(self) -> None:
        if self.source == "user_input" and not self.role:
            raise ValueError("VariableMapping with source='user_input' requires a non-empty 'role'")
        if self.source == "node_output" and not self.node_id:
            raise ValueError(
                "VariableMapping with source='node_output' requires a non-empty 'node_id'"
            )
        if self.source == "constant" and self.value is None:
            raise ValueError("VariableMapping with source='constant' requires a 'value'")


@dataclass
class Node:
    id: str
    type: NodeType
    model: ModelRef
    prompt_template: str
    inputs: list[NodeInput] = field(default_factory=list)
    output_schema: dict[str, str] | None = None
    variable_mapping: dict[str, VariableMapping] = field(default_factory=dict)


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
