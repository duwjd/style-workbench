from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from style_workbench.core.errors import (
    ConflictError,
    DagCycleError,
    DagValidationError,
    EvaluationNotFoundError,
    InvalidPromptStatusTransitionError,
    MissingDeclaredVariableError,
    PreconditionFailedError,
    PromptAbComparisonNotFoundError,
    PromptAbSameVersionError,
    PromptDeprecatedError,
    PromptNotFoundError,
    PromptOptimizationNotFoundError,
    PromptOptimizerInvalidOutputError,
    PromptUsageNotFoundError,
    PromptVersionNotFoundError,
    RunAbortedError,
    RunNotFoundError,
    StyleNotFoundError,
    StyleVersionHasNoPromptNodeError,
    StyleWorkbenchError,
    VersionNotFoundError,
)
from style_workbench.domain.prompt.template import TemplateError
from style_workbench.domain.prompt.validation import PromptValidationError

_STATUS_MAP: dict[type[Exception], int] = {
    DagCycleError: 422,
    DagValidationError: 422,
    StyleNotFoundError: 404,
    VersionNotFoundError: 404,
    RunNotFoundError: 404,
    EvaluationNotFoundError: 404,
    RunAbortedError: 400,
    ConflictError: 409,
    # TemplateError: placeholder 치환 실패 — 요청 데이터 오류이므로 422
    TemplateError: 422,
    # F05 Prompt Library errors
    PromptNotFoundError: 404,
    PromptVersionNotFoundError: 404,
    PromptUsageNotFoundError: 404,
    PromptAbComparisonNotFoundError: 404,
    InvalidPromptStatusTransitionError: 422,
    PromptDeprecatedError: 422,
    MissingDeclaredVariableError: 422,
    PromptAbSameVersionError: 422,
    StyleVersionHasNoPromptNodeError: 422,
    PreconditionFailedError: 412,
    # F02 Prompt Optimizer errors
    # PromptOptimizerInvalidOutputError → 내부 catch 후 succeeded=false row 저장.
    # 외부로 노출될 경우 500 (예상치 못한 버블업).
    PromptOptimizerInvalidOutputError: 500,
    PromptOptimizationNotFoundError: 404,
}


async def domain_error_handler(request: Request, exc: StyleWorkbenchError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )


async def template_error_handler(request: Request, exc: TemplateError) -> JSONResponse:
    """Handle TemplateError separately since it does not inherit StyleWorkbenchError."""
    return JSONResponse(
        status_code=422,
        content={"error": "TemplateError", "detail": str(exc)},
    )


async def prompt_validation_error_handler(
    request: Request, exc: PromptValidationError
) -> JSONResponse:
    """Handle PromptValidationError (undeclared placeholders — spec §4 FR-3)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "PromptValidationError",
            "detail": str(exc),
            "undeclared": sorted(exc.undeclared),
        },
    )
