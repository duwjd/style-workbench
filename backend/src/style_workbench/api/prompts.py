"""FastAPI router for the Prompt Library (F05) and F02 Prompt Optimizer.

Spec §6.1 — 12 endpoints:

    GET    /api/prompts                           list_prompts
    GET    /api/prompts/{id}                      get_prompt          + ETag header
    POST   /api/prompts                           create_prompt       → 201
    PUT    /api/prompts/{id}                      update_prompt_meta  + If-Match
    POST   /api/prompts/{id}/versions             create_version      + If-Match → 201
    GET    /api/prompts/{id}/versions             list_versions       paginated
    GET    /api/prompts/{id}/versions/{v}         get_version
    POST   /api/prompts/{id}/versions/{v}/promote promote_version
    GET    /api/prompts/{id}/usages               list_usages         paginated
    POST   /api/prompts/{id}/ab                   A/B comparison      (단계 5)
    POST   /api/prompts/{id}/optimize             F02 Optimizer       → 200
    GET    /api/prompts/{id}/optimizations        F02 history         paginated
    POST   /api/prompts/import-modules            placeholder 501     (단계 4)

Rules enforced here (CLAUDE.md §3.2):
    - No HTTPException raised directly — all domain errors bubble to exception_handlers.py.
    - No external SDK imports.
    - All handlers are async def.
    - Responses are Pydantic schema objects, never ORM or domain entities directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, Query, Response

from style_workbench.api.deps import (
    get_evaluation_repo,
    get_prompt_optimization_repo,
    get_prompt_optimizer,
    get_prompt_service,
    get_run_service,
)
from style_workbench.api.schemas.prompts import (
    PromptAbRequest,
    PromptAbResponse,
    PromptCreate,
    PromptListResponse,
    PromptMetaUpdate,
    PromptOptimizationListResponse,
    PromptOptimizationSummary,
    PromptOptimizeRequest,
    PromptOptimizeResponse,
    PromptResponse,
    PromptSummary,
    PromptVersionCreate,
    PromptVersionCreateResponse,
    PromptVersionListResponse,
    PromptVersionResponse,
    _detect_suspicious_placeholders,
    build_filters,
    compute_etag,
)
from style_workbench.core.errors import (
    EvaluationNotFoundError,
    PreconditionFailedError,
    PromptNotFoundError,
)
from style_workbench.domain.prompt.entity import NodeType
from style_workbench.engine.prompt_optimizer import LlmPromptModifier
from style_workbench.infra.repositories.evaluation_repo import SqlAlchemyEvaluationRepository
from style_workbench.infra.repositories.prompt_optimization_repo import (
    SqlAlchemyPromptOptimizationRepo,
)
from style_workbench.services.prompt_service import PromptService
from style_workbench.services.run_service import RunService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


# ---------------------------------------------------------------------------
# GET /api/prompts — list + search
# ---------------------------------------------------------------------------


@router.get("", response_model=PromptListResponse)
async def list_prompts(
    node_type: str | None = None,
    tags: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
    service: PromptService = Depends(get_prompt_service),
) -> PromptListResponse:
    """Search / filter prompts.

    Query params:
        node_type — one of: text | image | video | composition
        tags      — comma-separated list, e.g. "portrait,professional"
        status    — one of: draft | reviewing | approved | deprecated
        q         — keyword match on name (case-insensitive)
        limit     — max items per page (default 20, max 100)
        offset    — pagination offset (default 0)
    """
    effective_limit = min(limit, 100)
    filters = build_filters(
        node_type=node_type,
        tags=tags,
        status=status,
        q=q,
        limit=effective_limit,
        offset=offset,
    )
    prompts = await service.list_prompts(filters)

    # Count total matching rows for pagination metadata.
    # list_prompts returns the page; we run a second count query via filters with
    # limit=0 to get the ceiling.  This is intentionally simple — a dedicated
    # count method can be added to PromptRepo in Phase 3 when N > 100k.
    count_filters = build_filters(
        node_type=node_type,
        tags=tags,
        status=status,
        q=q,
        limit=10_000,  # generous upper bound for the count approximation
        offset=0,
    )
    all_prompts = await service.list_prompts(count_filters)
    total = len(all_prompts)

    return PromptListResponse(
        items=[PromptSummary.from_domain(p) for p in prompts],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/prompts/{id} — detail + ETag
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: str,
    response: Response,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Return the full prompt including current version body and usages ≤20.

    Sets ``ETag: W/"<updated_at>"`` header for optimistic locking (spec §6.4).
    """
    prompt = await service.get(prompt_id)
    usages, usage_count_total = await service.list_usages(prompt_id, limit=20, offset=0)

    # Set ETag header
    etag = compute_etag(prompt.updated_at)
    response.headers["ETag"] = etag

    logger.info("prompt_retrieved", prompt_id=prompt_id, usage_count=len(usages))

    return PromptResponse.from_domain(
        prompt=prompt,
        usages=usages,
        usage_count_total=usage_count_total,
    )


# ---------------------------------------------------------------------------
# POST /api/prompts — create
# ---------------------------------------------------------------------------


@router.post("", response_model=PromptResponse, status_code=201)
async def create_prompt(
    payload: PromptCreate,
    response: Response,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Create a new Prompt with status=draft and version=1.

    Validates that every ``{placeholder}`` in body is listed in declared_variables
    (spec §4 FR-3); raises 422 ``MissingDeclaredVariableError`` otherwise.
    """
    declared = [dv.to_domain() for dv in payload.declared_variables]
    model_default = payload.model_default.to_domain() if payload.model_default else None

    prompt = await service.create(
        name=payload.name,
        node_type=NodeType(payload.node_type),
        body=payload.body,
        declared_variables=declared,
        owner=payload.owner,
        tags=payload.tags,
        model_default=model_default,
        change_note=payload.change_note,
        created_by=payload.created_by,
    )

    # Set ETag on 201 response
    etag = compute_etag(prompt.updated_at)
    response.headers["ETag"] = etag

    logger.info("prompt_created_via_api", prompt_id=prompt.id)
    return PromptResponse.from_domain(prompt=prompt, usages=[], usage_count_total=0)


# ---------------------------------------------------------------------------
# PUT /api/prompts/{id} — update metadata (If-Match required)
# ---------------------------------------------------------------------------


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt_meta(
    prompt_id: str,
    payload: PromptMetaUpdate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Update mutable metadata (name, tags, status, owner).

    Requires ``If-Match`` header with the ETag value from the last GET response.
    Returns 412 ``PreconditionFailedError`` if the header is missing or stale.
    """
    if if_match is None:
        raise PreconditionFailedError(
            "If-Match header is required for PUT /api/prompts/{id}. "
            "Retrieve the current ETag from GET /api/prompts/{id} first."
        )

    # Load current prompt to validate ETag
    prompt = await service.get(prompt_id)
    current_etag = compute_etag(prompt.updated_at)
    provided_tag = if_match.strip()
    if provided_tag != current_etag:
        raise PreconditionFailedError(
            f"ETag mismatch: provided {provided_tag!r}, current {current_etag!r}. "
            "Fetch the latest version and retry."
        )

    from style_workbench.domain.prompt.entity import PromptStatus as _PromptStatus

    updated = await service.update_meta(
        prompt_id=prompt_id,
        name=payload.name,
        tags=payload.tags,
        status=_PromptStatus(payload.status) if payload.status else None,
        owner=payload.owner,
    )

    usages, usage_count_total = await service.list_usages(prompt_id, limit=20, offset=0)
    # Restore current_version on the updated entity (update_meta returns prompt without it)
    updated.current_version = prompt.current_version

    etag = compute_etag(updated.updated_at)
    response.headers["ETag"] = etag

    logger.info("prompt_meta_updated_via_api", prompt_id=prompt_id)
    return PromptResponse.from_domain(
        prompt=updated,
        usages=usages,
        usage_count_total=usage_count_total,
    )


# ---------------------------------------------------------------------------
# POST /api/prompts/{id}/versions — create new version (If-Match required)
# ---------------------------------------------------------------------------


@router.post("/{prompt_id}/versions", response_model=PromptVersionCreateResponse, status_code=201)
async def create_prompt_version(
    prompt_id: str,
    payload: PromptVersionCreate,
    if_match: str | None = Header(default=None, alias="If-Match"),
    service: PromptService = Depends(get_prompt_service),
) -> PromptVersionCreateResponse:
    """Append a new immutable version for the given prompt.

    Requires ``If-Match`` header (spec §6.4).
    Returns 412 if header is missing or stale.
    Returns 422 if declared_variables does not cover all body placeholders.
    Returns 422 if the prompt is deprecated (spec §4 FR-9).

    Emits warnings (not errors) for numeric / format-spec / attribute-access
    placeholders per spec §6.3 (결정 2).
    """
    if if_match is None:
        raise PreconditionFailedError(
            "If-Match header is required for POST /api/prompts/{id}/versions. "
            "Retrieve the current ETag from GET /api/prompts/{id} first."
        )

    # Validate ETag
    prompt = await service.get(prompt_id)
    current_etag = compute_etag(prompt.updated_at)
    provided_tag = if_match.strip()
    if provided_tag != current_etag:
        raise PreconditionFailedError(
            f"ETag mismatch: provided {provided_tag!r}, current {current_etag!r}. "
            "Fetch the latest version and retry."
        )

    # Detect authoring warnings before delegating to service (결정 2)
    warnings = _detect_suspicious_placeholders(payload.body)

    declared = [dv.to_domain() for dv in payload.declared_variables]
    model_default = payload.model_default.to_domain() if payload.model_default else None

    version = await service.create_version(
        prompt_id=prompt_id,
        body=payload.body,
        declared_variables=declared,
        change_note=payload.change_note,
        model_default=model_default,
        created_by=payload.created_by,
    )

    logger.info("prompt_version_created_via_api", prompt_id=prompt_id, version=version.version)
    return PromptVersionCreateResponse(
        version=PromptVersionResponse.from_domain(version),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# GET /api/prompts/{id}/versions — list all versions (paginated, version DESC)
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}/versions", response_model=PromptVersionListResponse)
async def list_prompt_versions(
    prompt_id: str,
    limit: int = 50,
    offset: int = 0,
    service: PromptService = Depends(get_prompt_service),
) -> PromptVersionListResponse:
    """Return paginated versions for a prompt, ordered by version DESC.

    Used by the A/B trigger dialog to populate the from/to version selects.

    Query params:
        limit  — max items per page (default 50, max 100)
        offset — pagination offset (default 0)

    Raises 404 if the prompt does not exist.
    """
    effective_limit = min(limit, 100)
    versions, total = await service.list_versions(prompt_id, limit=effective_limit, offset=offset)
    logger.info(
        "prompt_versions_listed",
        prompt_id=prompt_id,
        total=total,
        limit=effective_limit,
        offset=offset,
    )
    return PromptVersionListResponse(
        items=[PromptVersionResponse.from_domain(v) for v in versions],
        total=total,
        limit=effective_limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /api/prompts/{id}/versions/{v} — get specific version
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}/versions/{version_number}", response_model=PromptVersionResponse)
async def get_prompt_version(
    prompt_id: str,
    version_number: int,
    service: PromptService = Depends(get_prompt_service),
) -> PromptVersionResponse:
    """Return a specific version by its integer version number."""
    version = await service.get_version(prompt_id, version_number)
    return PromptVersionResponse.from_domain(version)


# ---------------------------------------------------------------------------
# POST /api/prompts/{id}/versions/{v}/promote — set as current_version
# ---------------------------------------------------------------------------


@router.post("/{prompt_id}/versions/{version_number}/promote", response_model=PromptResponse)
async def promote_prompt_version(
    prompt_id: str,
    version_number: int,
    service: PromptService = Depends(get_prompt_service),
) -> PromptResponse:
    """Promote the given version to current_version_id.

    Raises 422 if the prompt is deprecated.
    Raises 404 if the version does not belong to this prompt.
    """
    # Resolve version number → version id
    version = await service.get_version(prompt_id, version_number)

    updated_prompt = await service.promote_version(
        prompt_id=prompt_id,
        version_id=version.id,
    )
    usages, usage_count_total = await service.list_usages(prompt_id, limit=20, offset=0)
    logger.info(
        "prompt_version_promoted_via_api",
        prompt_id=prompt_id,
        version=version_number,
    )
    return PromptResponse.from_domain(
        prompt=updated_prompt,
        usages=usages,
        usage_count_total=usage_count_total,
    )


# ---------------------------------------------------------------------------
# GET /api/prompts/{id}/usages — paginated usages
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}/usages")
async def list_prompt_usages(
    prompt_id: str,
    limit: int = 20,
    offset: int = 0,
    service: PromptService = Depends(get_prompt_service),
) -> dict[str, object]:
    """Return a paginated list of style+node usages for the given prompt."""
    effective_limit = min(limit, 100)
    usages, total = await service.list_usages(prompt_id, limit=effective_limit, offset=offset)

    from style_workbench.api.schemas.prompts import PromptUsageResponse

    return {
        "items": [PromptUsageResponse.from_domain(u).model_dump() for u in usages],
        "total": total,
        "limit": effective_limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# POST /api/prompts/{id}/ab — A/B comparison (단계 5 구현)
# ---------------------------------------------------------------------------


@router.post("/{prompt_id}/ab", response_model=PromptAbResponse, status_code=200)
async def ab_compare(
    prompt_id: str,
    payload: PromptAbRequest,
    service: PromptService = Depends(get_prompt_service),
    run_service: RunService = Depends(get_run_service),
) -> PromptAbResponse:
    """Trigger A/B comparison for two prompt versions.

    spec §4 FR-8 / §13 단계 5.

    Resolves from_version / to_version which may be either:
    - PromptVersion id strings (starting with a ULID prefix), OR
    - integer version numbers as strings (e.g. "1", "2").

    Executes both versions serially (F03 미구현 → 직렬 실행) and returns
    the ab_id + from_run_id + to_run_id for the frontend to subscribe to
    the existing SSE channels (GET /api/runs/{run_id}/events).

    Raises:
        404 — prompt_id not found.
        404 — from_version or to_version not found for this prompt.
        422 — from_version == to_version (meaningless A/B).
        422 — style_version_id has no node referencing this prompt.
    """
    # Resolve from_version: integer string → version id
    from_version_id = await _resolve_version_id(service, prompt_id, payload.from_version)
    to_version_id = await _resolve_version_id(service, prompt_id, payload.to_version)

    ab = await service.trigger_ab(
        prompt_id=prompt_id,
        from_version_id=from_version_id,
        to_version_id=to_version_id,
        style_version_id=payload.style_version_id,
        user_input=payload.user_input,
        run_service=run_service,
    )

    logger.info(
        "ab_comparison_triggered_via_api",
        prompt_id=prompt_id,
        ab_id=ab.id,
        from_run_id=ab.from_run_id,
        to_run_id=ab.to_run_id,
    )
    return PromptAbResponse.from_domain(ab)


# ---------------------------------------------------------------------------
# POST /api/prompts/{id}/optimize — F02 수동 트리거 (spec §6.1, FR-7)
# ---------------------------------------------------------------------------


@router.post("/{prompt_id}/optimize", response_model=PromptOptimizeResponse, status_code=200)
async def optimize_prompt(
    prompt_id: str,
    payload: PromptOptimizeRequest,
    service: PromptService = Depends(get_prompt_service),
    modifier: LlmPromptModifier = Depends(get_prompt_optimizer),
    eval_repo: SqlAlchemyEvaluationRepository = Depends(get_evaluation_repo),
    optimization_repo: SqlAlchemyPromptOptimizationRepo = Depends(get_prompt_optimization_repo),
) -> PromptOptimizeResponse:
    """F02 Prompt Optimizer 수동 트리거.

    두 가지 입력 모드:
      1. evaluation_id 모드: 해당 evaluation 의 retry_guidance / failed_dimensions 자동 추출.
      2. 직접 입력 모드: retry_guidance + failed_dimensions + parent_version_id 를 요청 본문에.

    응답: 200 + succeeded 필드로 성공/실패 구분.
    succeeded=false 일 때도 HTTP 200 (F02 호출 자체는 성공, LLM 출력이 부적합).

    Raises:
        404 — prompt_id not found.
        404 — evaluation_id not found (evaluation_id 모드).
        422 — 둘 다 None (PromptOptimizeRequest validator).
    """
    # Prompt 존재 확인
    prompt = await service.get(prompt_id)
    if prompt is None:
        raise PromptNotFoundError(f"Prompt '{prompt_id}' not found")

    # ── 입력 모드 결정 ─────────────────────────────────────────────────────
    retry_guidance: dict[str, Any]
    failed_dimensions: list[str]
    parent_version_id: str | None

    if payload.evaluation_id is not None:
        # evaluation_id 모드: retry_guidance / failed_dimensions 자동 추출
        eval_record = await eval_repo.get_record_by_id(payload.evaluation_id)
        if eval_record is None:
            raise EvaluationNotFoundError(f"Evaluation '{payload.evaluation_id}' not found")
        retry_guidance = (
            dict(eval_record.retry_guidance)
            if eval_record.retry_guidance
            else {"instruction": "이전 evaluation 결과를 바탕으로 prompt 를 개선하라."}
        )
        failed_dimensions = list(eval_record.failed_dimensions)
        # evaluation 의 node_execution → prompt_version_id 를 추적 (best effort)
        # evaluation_record 에 node_execution_id 는 있지만 prompt_version_id 는 없다.
        # prompt 의 current_version_id 를 parent 로 사용한다 (spec §6.2 결정).
        parent_version_id = prompt.current_version_id
    else:
        retry_guidance = (
            dict(payload.retry_guidance)
            if payload.retry_guidance
            else {"instruction": "직접 입력 모드: retry_guidance 없음."}
        )
        failed_dimensions = list(payload.failed_dimensions) if payload.failed_dimensions else []
        parent_version_id = payload.parent_version_id or prompt.current_version_id

    # ── LlmPromptModifier 호출 ────────────────────────────────────────────
    _new_body, new_version_id = await modifier.modify(
        prompt_version_id=parent_version_id,
        retry_guidance=retry_guidance,
        failed_dimensions=failed_dimensions,
    )

    # modify() 는 내부에서 optimization row 를 저장하므로 가장 최근 row 를 조회
    opts, total = await optimization_repo.list_for_prompt(prompt_id, limit=1, offset=0)
    if opts:
        latest_opt = opts[0]
        logger.info(
            "prompt_optimized_via_api",
            prompt_id=prompt_id,
            optimization_id=latest_opt.id,
            succeeded=latest_opt.succeeded,
        )
        return PromptOptimizeResponse.from_domain(latest_opt)

    # fallback: optimization_repo 조회 실패 시 Noop 응답 구성

    from style_workbench.core.ids import new_ulid
    from style_workbench.domain.prompt.optimization import PromptOptimization

    fallback_opt = PromptOptimization(
        id=new_ulid(),
        prompt_id=prompt_id,
        parent_version_id=parent_version_id or "",
        new_version_id=new_version_id,
        retry_guidance=retry_guidance,
        failed_dimensions=failed_dimensions,
        eval_evidence=None,
        change_summary=None,
        cost_won=modifier.last_cost_won,
        latency_ms=None,
        succeeded=new_version_id is not None,
        failure_reason=None if new_version_id is not None else "UnknownError",
    )
    return PromptOptimizeResponse.from_domain(fallback_opt)


# ---------------------------------------------------------------------------
# GET /api/prompts/{id}/optimizations — F02 이력 (spec §6.1)
# ---------------------------------------------------------------------------


@router.get("/{prompt_id}/optimizations", response_model=PromptOptimizationListResponse)
async def list_optimizations(
    prompt_id: str,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    service: PromptService = Depends(get_prompt_service),
    optimization_repo: SqlAlchemyPromptOptimizationRepo = Depends(get_prompt_optimization_repo),
) -> PromptOptimizationListResponse:
    """GET /api/prompts/{id}/optimizations — F02 호출 이력 목록.

    Raises:
        404 — prompt_id not found.
    """
    # prompt 존재 확인
    await service.get(prompt_id)

    items, total = await optimization_repo.list_for_prompt(prompt_id, limit=limit, offset=offset)
    logger.info(
        "prompt_optimizations_listed",
        prompt_id=prompt_id,
        total=total,
        limit=limit,
        offset=offset,
    )
    return PromptOptimizationListResponse(
        items=[PromptOptimizationSummary.from_domain(opt) for opt in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# POST /api/prompts/import-modules — bulk import CLI (단계 4 placeholder)
# ---------------------------------------------------------------------------


@router.post("/import-modules", status_code=501)
async def import_modules() -> dict[str, str]:
    """Bulk import prompt modules from an external directory.

    Not yet implemented — scheduled for 단계 4.
    Returns HTTP 501 Not Implemented.
    """
    return {
        "error": "NotImplemented",
        "detail": "import-modules endpoint will be implemented in 단계 4. "
        "See spec §4 FR-7 and §13 단계 4.",
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _resolve_version_id(service: PromptService, prompt_id: str, version_ref: str) -> str:
    """Resolve a version reference to a PromptVersion id.

    *version_ref* may be either:
    - A PromptVersion id (ULID string that cannot be parsed as an integer).
    - An integer version number as a string (e.g. "1", "2").

    Returns the PromptVersion id string.
    Raises PromptVersionNotFoundError if the version does not exist.
    """
    try:
        version_number = int(version_ref)
    except ValueError:
        # Treat as a direct version id — validate by fetching
        pv = await service._version_repo.get(version_ref)  # noqa: SLF001
        if pv is None or pv.prompt_id != prompt_id:
            from style_workbench.core.errors import PromptVersionNotFoundError

            raise PromptVersionNotFoundError(
                f"PromptVersion '{version_ref}' not found for prompt '{prompt_id}'"
            ) from None
        return pv.id
    else:
        pv = await service.get_version(prompt_id, version_number)
        return pv.id
