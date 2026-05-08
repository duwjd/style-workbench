from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from style_workbench.core.errors import (
    DagCycleError,
    DagValidationError,
    RunAbortedError,
    RunNotFoundError,
    StyleNotFoundError,
    StyleWorkbenchError,
    VersionNotFoundError,
)

_STATUS_MAP: dict[type[StyleWorkbenchError], int] = {
    DagCycleError: 422,
    DagValidationError: 422,
    StyleNotFoundError: 404,
    VersionNotFoundError: 404,
    RunNotFoundError: 404,
    RunAbortedError: 400,
}


async def domain_error_handler(request: Request, exc: StyleWorkbenchError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )
