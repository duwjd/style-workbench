"""Pydantic request / response schemas for the Prompt Library API (F05 + F02).

Spec references:
    §6.1  Endpoint list
    §6.2  GET /api/prompts/{id} response structure
    §6.3  POST /api/prompts/{id}/versions request + warning policy
    §6.4  ETag / If-Match (headers; handled at router level)
    F02 §6  POST /api/prompts/{id}/optimize + GET /api/prompts/{id}/optimizations

Conventions (CLAUDE.md §3.3):
    - All fields snake_case.
    - ``model_config = ConfigDict(from_attributes=True)`` on response models that
      may be constructed from ORM-derived domain objects.
    - to_domain() / from_domain() helpers mirror the style/eval schema pattern.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from style_workbench.domain.prompt.entity import (
    DeclaredVariable,
    ModelDefault,
    NodeType,
    Prompt,
    PromptAbComparison,
    PromptFilters,
    PromptStatus,
    PromptUsage,
    PromptVersion,
)
from style_workbench.domain.prompt.optimization import PromptOptimization

# ---------------------------------------------------------------------------
# Shared patterns for warning detection (spec §6.3 결정 2)
#
# PLACEHOLDER_PATTERN in domain/prompt/template.py matches {word} only (\w+).
# \w+ includes digits, so {0} is technically matched by the domain pattern.
# Per spec §6.3 decision: numeric ({0}), format-spec ({name:>10}), and
# attribute-access ({a.b}) placeholders emit warnings rather than 422.
# ---------------------------------------------------------------------------

_NUMERIC_PLACEHOLDER = re.compile(r"\{(\d+)\}")  # {0}, {1}, …
_FORMAT_SPEC_PLACEHOLDER = re.compile(r"\{[^}]+:[^}]+\}")  # {name:>10}, {val:.2f}
_ATTR_ACCESS_PLACEHOLDER = re.compile(r"\{[^}]+\.[^}]+\}")  # {a.b}, {obj.field}


def _detect_suspicious_placeholders(body: str) -> list[str]:
    """Return warning strings for non-standard placeholder patterns in *body*.

    These patterns are ignored by safe_substitute() but may indicate authoring
    mistakes.  Per spec §6.3 they produce warnings, not 422 errors.
    """
    warnings: list[str] = []
    numeric = _NUMERIC_PLACEHOLDER.findall(body)
    if numeric:
        warnings.append(
            f"Positional placeholder(s) found: {{{', '.join(numeric)}}} — "
            "these are ignored by safe_substitute(); use named placeholders instead."
        )
    if _FORMAT_SPEC_PLACEHOLDER.search(body):
        warnings.append(
            "Format-spec placeholder(s) detected (e.g. {name:>10}) — "
            "these are ignored by safe_substitute() and will be left verbatim."
        )
    if _ATTR_ACCESS_PLACEHOLDER.search(body):
        warnings.append(
            "Attribute-access placeholder(s) detected (e.g. {a.b}) — "
            "these are ignored by safe_substitute() and will be left verbatim."
        )
    return warnings


# ---------------------------------------------------------------------------
# Value object schemas
# ---------------------------------------------------------------------------


class DeclaredVariableSchema(BaseModel):
    """Single declared placeholder variable.  Maps to domain DeclaredVariable."""

    name: str
    role: str = ""
    required: bool = True

    def to_domain(self) -> DeclaredVariable:
        return DeclaredVariable(name=self.name, role=self.role, required=self.required)

    @classmethod
    def from_domain(cls, dv: DeclaredVariable) -> DeclaredVariableSchema:
        return cls(name=dv.name, role=dv.role, required=dv.required)


class ModelDefaultSchema(BaseModel):
    """Optional recommended model for a prompt version."""

    provider: str
    model_id: str

    def to_domain(self) -> ModelDefault:
        return ModelDefault(provider=self.provider, model_id=self.model_id)

    @classmethod
    def from_domain(cls, md: ModelDefault) -> ModelDefaultSchema:
        return cls(provider=md.provider, model_id=md.model_id)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PromptCreate(BaseModel):
    """POST /api/prompts request body.

    Creates a new Prompt with status=draft and version=1.
    """

    name: str
    node_type: NodeType
    body: str
    declared_variables: list[DeclaredVariableSchema] = Field(default_factory=list)
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)
    model_default: ModelDefaultSchema | None = None
    change_note: str | None = None
    created_by: str | None = None


class PromptMetaUpdate(BaseModel):
    """PUT /api/prompts/{id} request body — partial update of mutable metadata.

    Body changes require POST /api/prompts/{id}/versions instead.
    At least one field must be supplied (validated at service level).
    """

    name: str | None = None
    tags: list[str] | None = None
    status: PromptStatus | None = None
    owner: str | None = None


class PromptVersionCreate(BaseModel):
    """POST /api/prompts/{id}/versions request body.

    Per spec §6.3:
    - 422 if body contains alphanumeric placeholders not listed in declared_variables.
    - warnings (list[str]) populated for numeric / format-spec / attr-access patterns.
    """

    body: str
    declared_variables: list[DeclaredVariableSchema] = Field(default_factory=list)
    change_note: str | None = None
    model_default: ModelDefaultSchema | None = None
    created_by: str | None = None

    @field_validator("body")
    @classmethod
    def _body_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("body must not be empty")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PromptVersionResponse(BaseModel):
    """Response for a single PromptVersion."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str
    version: int
    body: str
    declared_variables: list[DeclaredVariableSchema]
    model_default: ModelDefaultSchema | None
    parent_version_id: str | None
    change_note: str | None
    created_at: datetime | None
    created_by: str | None

    @classmethod
    def from_domain(cls, pv: PromptVersion) -> PromptVersionResponse:
        return cls(
            id=pv.id,
            prompt_id=pv.prompt_id,
            version=pv.version,
            body=pv.body,
            declared_variables=[
                DeclaredVariableSchema.from_domain(d) for d in pv.declared_variables
            ],
            model_default=ModelDefaultSchema.from_domain(pv.model_default)
            if pv.model_default
            else None,
            parent_version_id=pv.parent_version_id,
            change_note=pv.change_note,
            created_at=pv.created_at,
            created_by=pv.created_by,
        )


class PromptUsageResponse(BaseModel):
    """Single usage entry for a prompt (style + node)."""

    model_config = ConfigDict(from_attributes=True)

    style_version_id: str
    style_name: str | None  # populated by the repo join; may be None if style deleted
    node_id: str
    pinned: bool
    last_run_score: float | None

    @classmethod
    def from_domain(cls, pu: PromptUsage, style_name: str | None = None) -> PromptUsageResponse:
        return cls(
            style_version_id=pu.style_version_id,
            style_name=style_name,
            node_id=pu.node_id,
            pinned=pu.pinned,
            last_run_score=pu.last_run_score,
        )


class PromptResponse(BaseModel):
    """GET /api/prompts/{id} — full prompt with current_version + usages ≤20.

    Matches spec §6.2 JSON structure exactly.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    node_type: NodeType
    status: PromptStatus
    owner: str | None
    tags: list[str]
    current_version: PromptVersionResponse | None
    usages: list[PromptUsageResponse]
    usage_count_total: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        prompt: Prompt,
        usages: list[PromptUsage],
        usage_count_total: int,
        style_names: dict[str, str] | None = None,
    ) -> PromptResponse:
        """Build a PromptResponse from domain objects.

        Args:
            prompt:            The domain Prompt entity (with current_version populated).
            usages:            Usage list (≤20).
            usage_count_total: Total usage count (for pagination UI).
            style_names:       Mapping of style_version_id → style name for the usage panel.
                               Pass None or empty dict if names are unavailable.
        """
        _style_names = style_names or {}
        return cls(
            id=prompt.id,
            name=prompt.name,
            node_type=prompt.node_type,
            status=prompt.status,
            owner=prompt.owner,
            tags=prompt.tags,
            current_version=(
                PromptVersionResponse.from_domain(prompt.current_version)
                if prompt.current_version is not None
                else None
            ),
            usages=[
                PromptUsageResponse.from_domain(u, style_name=_style_names.get(u.style_version_id))
                for u in usages
            ],
            usage_count_total=usage_count_total,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )


class PromptSummary(BaseModel):
    """Lightweight list-item response — body is NOT included to keep payloads small."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    node_type: NodeType
    status: PromptStatus
    owner: str | None
    tags: list[str]
    current_version_id: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, prompt: Prompt) -> PromptSummary:
        return cls(
            id=prompt.id,
            name=prompt.name,
            node_type=prompt.node_type,
            status=prompt.status,
            owner=prompt.owner,
            tags=prompt.tags,
            current_version_id=prompt.current_version_id,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )


class PromptListResponse(BaseModel):
    """Paginated list response for GET /api/prompts."""

    items: list[PromptSummary]
    total: int
    limit: int
    offset: int


class PromptVersionListResponse(BaseModel):
    """Paginated list response for GET /api/prompts/{id}/versions.

    Items use the same PromptVersionResponse schema as the single-version endpoint
    (GET /api/prompts/{id}/versions/{v}) so that A/B compare screens can render
    the body diff without a second round-trip.
    """

    items: list[PromptVersionResponse]
    total: int
    limit: int
    offset: int


class PromptVersionCreateResponse(BaseModel):
    """201 response after POST /api/prompts/{id}/versions.

    Includes the new version details plus any authoring warnings (spec §6.3).
    """

    version: PromptVersionResponse
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# A/B comparison schemas (spec §4 FR-8, §13 단계 5)
# ---------------------------------------------------------------------------


class PromptAbRequest(BaseModel):
    """POST /api/prompts/{id}/ab request body.

    from_version and to_version may be prompt_version_id strings (ULID) or
    integer version numbers.  The router resolves integer → id via service.get_version().

    spec §4 FR-8.
    """

    from_version: str
    """PromptVersion id (pmv_...) or integer version number as string."""

    to_version: str
    """PromptVersion id (pmv_...) or integer version number as string."""

    style_version_id: str
    """StyleVersion where the prompt is used — determines node context for execution."""

    user_input: dict[str, str] = Field(default_factory=dict)
    """Runtime placeholder values passed to both runs."""


class PromptAbResponse(BaseModel):
    """Response for POST /api/prompts/{id}/ab.

    Frontend uses from_run_id / to_run_id to subscribe to existing SSE channels
    (GET /api/runs/{run_id}/events) independently.  No merged SSE channel is needed.
    """

    model_config = ConfigDict(from_attributes=True)

    ab_id: str
    prompt_id: str
    from_version_id: str
    to_version_id: str
    style_version_id: str
    from_run_id: str | None
    to_run_id: str | None
    status: str

    @classmethod
    def from_domain(cls, ab: PromptAbComparison) -> PromptAbResponse:
        return cls(
            ab_id=ab.id,
            prompt_id=ab.prompt_id,
            from_version_id=ab.from_version_id,
            to_version_id=ab.to_version_id,
            style_version_id=ab.style_version_id,
            from_run_id=ab.from_run_id,
            to_run_id=ab.to_run_id,
            status=ab.status,
        )


# ---------------------------------------------------------------------------
# ETag helpers
# ---------------------------------------------------------------------------


def compute_etag(updated_at: datetime | None) -> str:
    """Derive a weak ETag value from the prompt's updated_at timestamp.

    Format: W/"<iso-timestamp-hash>" — stable for the same updated_at value,
    changes whenever the prompt metadata is modified.
    """
    if updated_at is None:
        return 'W/"none"'
    # Use the full ISO timestamp string as the ETag body — deterministic and cheap.
    tag_body = updated_at.isoformat()
    return f'W/"{tag_body}"'


def parse_if_match(if_match: str | None) -> str | None:
    """Strip the W/" … " wrapper from an If-Match header value.

    Returns the inner timestamp string, or None if the header is absent.
    """
    if if_match is None:
        return None
    # Strip surrounding quotes and weak indicator
    return if_match.strip().removeprefix('W/"').removesuffix('"')


# ---------------------------------------------------------------------------
# F02 Prompt Optimizer — request / response schemas (spec §6.2, §6.3)
# ---------------------------------------------------------------------------


class PromptOptimizeRequest(BaseModel):
    """POST /api/prompts/{id}/optimize request body.

    두 가지 모드 중 하나를 선택한다 (둘 다 None 이면 422):
      - evaluation_id 모드: evaluation 에서 retry_guidance / failed_dimensions 자동 추출.
      - 직접 입력 모드: retry_guidance + failed_dimensions + parent_version_id 직접 지정.
    """

    # 자동 추출 모드
    evaluation_id: str | None = None

    # 직접 입력 모드
    retry_guidance: dict[str, object] | None = None
    failed_dimensions: list[str] | None = None
    parent_version_id: str | None = None

    @model_validator(mode="after")
    def _require_at_least_one_mode(self) -> PromptOptimizeRequest:
        has_eval = self.evaluation_id is not None
        has_direct = self.retry_guidance is not None or self.failed_dimensions is not None
        if not has_eval and not has_direct:
            raise ValueError(
                "Either evaluation_id or (retry_guidance / failed_dimensions) must be provided."
            )
        return self


class PromptOptimizeResponse(BaseModel):
    """200 response for POST /api/prompts/{id}/optimize.

    spec §6.3: 200 응답 + succeeded=false 로 invalid output 도 정상 응답.
    HTTP 422 를 쓰지 않는 이유: F02 호출 자체는 성공, LLM 출력만 부적합.
    """

    model_config = ConfigDict(from_attributes=True)

    optimization_id: str
    prompt_id: str
    parent_version_id: str
    new_version_id: str | None
    change_summary: str | None
    cost_won: str  # Decimal → str (JSON 직렬화 안전)
    latency_ms: int | None
    succeeded: bool
    failure_reason: str | None = None

    @classmethod
    def from_domain(cls, opt: PromptOptimization) -> PromptOptimizeResponse:
        return cls(
            optimization_id=opt.id,
            prompt_id=opt.prompt_id,
            parent_version_id=opt.parent_version_id,
            new_version_id=opt.new_version_id,
            change_summary=opt.change_summary,
            cost_won=str(opt.cost_won),
            latency_ms=opt.latency_ms,
            succeeded=opt.succeeded,
            failure_reason=opt.failure_reason,
        )


class PromptOptimizationSummary(BaseModel):
    """단일 F02 호출 이력 row (list-item 용)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str
    parent_version_id: str
    new_version_id: str | None
    change_summary: str | None
    cost_won: str
    latency_ms: int | None
    succeeded: bool
    failure_reason: str | None
    created_at: datetime | None

    @classmethod
    def from_domain(cls, opt: PromptOptimization) -> PromptOptimizationSummary:
        return cls(
            id=opt.id,
            prompt_id=opt.prompt_id,
            parent_version_id=opt.parent_version_id,
            new_version_id=opt.new_version_id,
            change_summary=opt.change_summary,
            cost_won=str(opt.cost_won),
            latency_ms=opt.latency_ms,
            succeeded=opt.succeeded,
            failure_reason=opt.failure_reason,
            created_at=opt.created_at,
        )


class PromptOptimizationListResponse(BaseModel):
    """GET /api/prompts/{id}/optimizations 응답.

    spec §6.1 — 페이지네이션.
    """

    items: list[PromptOptimizationSummary]
    total: int
    limit: int
    offset: int


def build_filters(
    node_type: str | None,
    tags: str | None,
    status: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> PromptFilters:
    """Parse query parameters into a PromptFilters domain object.

    Args:
        tags: Comma-separated tag list, e.g. ``"portrait,professional"``.
    """
    parsed_node_type: NodeType | None = NodeType(node_type) if node_type else None
    parsed_status: PromptStatus | None = PromptStatus(status) if status else None
    parsed_tags: list[str] = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    return PromptFilters(
        node_type=parsed_node_type,
        tags=parsed_tags,
        status=parsed_status,
        q=q or None,
        limit=limit,
        offset=offset,
    )
