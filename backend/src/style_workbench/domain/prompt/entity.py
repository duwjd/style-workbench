"""Domain entities for the Prompt Library (F05).

Lifecycle:
    draft → reviewing → approved → deprecated

Versioning:
    Prompt (meta) 1 — N PromptVersion (body, immutable).
    prompts.current_version_id points to the active version.
    parent_version_id tracks the F02 lineage tree.

No external dependencies — this module must stay pure domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class NodeType(StrEnum):
    """Prompt node type — mirrors domain/style/entity.py NodeType values."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    COMPOSITION = "composition"


class PromptStatus(StrEnum):
    """Lifecycle status for a Prompt (spec §4 FR-9)."""

    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    DEPRECATED = "deprecated"

    # Allowed forward / backward transitions
    _TRANSITIONS: dict[str, frozenset[str]]  # declared below

    def can_transition_to(self, target: PromptStatus) -> bool:  # noqa: D102
        return target in _STATUS_TRANSITIONS.get(self, frozenset())


# Defined outside the class body to avoid StrEnum field-name conflicts.
_STATUS_TRANSITIONS: dict[PromptStatus, frozenset[PromptStatus]] = {
    PromptStatus.DRAFT: frozenset({PromptStatus.REVIEWING}),
    PromptStatus.REVIEWING: frozenset({PromptStatus.APPROVED, PromptStatus.DRAFT}),
    PromptStatus.APPROVED: frozenset({PromptStatus.DEPRECATED}),
    PromptStatus.DEPRECATED: frozenset(),  # terminal
}


@dataclass(frozen=True)
class DeclaredVariable:
    """A single declared placeholder variable in a prompt body.

    name     — the identifier used in ``{name}`` syntax.
    role     — semantic role (e.g. "person_name", "job_title").
    required — whether the variable must be supplied at runtime.
    """

    name: str
    role: str = ""
    required: bool = True


@dataclass(frozen=True)
class ModelDefault:
    """Optional recommended model for a prompt version."""

    provider: str
    model_id: str


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


@dataclass
class PromptVersion:
    """Immutable body snapshot of a Prompt at a point in time.

    Each save of the body creates a new row; previous rows are never mutated.
    parent_version_id enables tree traversal for F02 Optimizer lineage.
    """

    id: str
    prompt_id: str
    version: int
    body: str
    declared_variables: list[DeclaredVariable] = field(default_factory=list)
    model_default: ModelDefault | None = None
    parent_version_id: str | None = None
    change_note: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None  # "user:<id>" or "auto:F02"


@dataclass
class Prompt:
    """Top-level Prompt entity — holds mutable metadata.

    Body changes go to PromptVersion; only name/tags/status/owner are mutable
    in-place.  current_version_id is updated by the promote operation.
    """

    id: str
    name: str
    node_type: NodeType
    status: PromptStatus = PromptStatus.DRAFT
    owner: str | None = None
    current_version_id: str | None = None
    tags: list[str] = field(default_factory=list)
    imported_from: str | None = None  # FR-7 idempotency key
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Eagerly-loaded for read paths only; not persisted here.
    current_version: PromptVersion | None = None


@dataclass
class PromptUsage:
    """Record linking a PromptVersion to a StyleVersion node.

    Uniqueness: (style_version_id, node_id) — one node → one prompt.
    last_run_score is updated by RunService after evaluation (spec §4 FR-6).
    """

    id: str
    prompt_id: str
    prompt_version_id: str
    style_version_id: str
    node_id: str
    pinned: bool = False
    last_run_score: float | None = None
    last_run_at: datetime | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Filters (used by PromptRepo.list)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptFilters:
    """Search / filter parameters for listing prompts (spec §6.1)."""

    node_type: NodeType | None = None
    tags: list[str] = field(default_factory=list)
    status: PromptStatus | None = None
    q: str | None = None  # keyword match on name + tags
    limit: int = 20
    offset: int = 0


# ---------------------------------------------------------------------------
# Re-export allowed transition map for use in validation / service
# ---------------------------------------------------------------------------

AllowedTransitions = Literal[
    "draft→reviewing",
    "reviewing→approved",
    "reviewing→draft",
    "approved→deprecated",
]


# ---------------------------------------------------------------------------
# NodeType compatibility mapping (spec §단계 2 결정 1)
#
# domain/prompt.NodeType  ("text"|"image"|"video"|"composition")
# domain/style.NodeType   ("text_generation"|"image_generation"|...)
#
# The two enums have different vocabularies.  This function bridges them without
# importing domain/style (that would create a cross-domain import which violates
# CLAUDE.md §2.1 layer rules).  Callers pass style node_type as a plain string.
# ---------------------------------------------------------------------------

_PROMPT_TO_STYLE_NODE_TYPES: dict[str, frozenset[str]] = {
    "text": frozenset({"text_generation"}),
    "image": frozenset({"image_generation"}),
    "video": frozenset({"video_generation"}),
    "composition": frozenset({"composition"}),
}


@dataclass
class PromptAbComparison:
    """Record of an A/B comparison between two PromptVersions.

    Stores the two run IDs created by the comparison trigger.
    Lifecycle: created → (from_run + to_run settle asynchronously) → done.

    spec §4 FR-8, §13 단계 5.
    """

    id: str
    prompt_id: str
    from_version_id: str
    to_version_id: str
    style_version_id: str
    user_input: dict[str, str]
    from_run_id: str | None = None
    to_run_id: str | None = None
    status: str = "running"  # "running" | "done" | "failed"
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


def compatible_with_node_type(prompt_node_type: NodeType, style_node_type: str) -> bool:
    """Return True if *prompt_node_type* (Prompt Library) is compatible with *style_node_type*.

    Example::

        compatible_with_node_type(NodeType.TEXT, "text_generation")  # True
        compatible_with_node_type(NodeType.IMAGE, "text_generation") # False

    The mapping is intentionally one-directional: we convert the Prompt Library
    NodeType to the set of equivalent style NodeType strings.  The style NodeType
    enum lives in ``domain/style/entity.py`` and is NOT imported here to keep
    domain boundaries clean.
    """
    allowed = _PROMPT_TO_STYLE_NODE_TYPES.get(str(prompt_node_type), frozenset())
    return style_node_type in allowed
