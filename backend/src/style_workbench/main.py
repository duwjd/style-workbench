from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from style_workbench.api.evaluations import router as evaluations_router
from style_workbench.api.exception_handlers import (
    domain_error_handler,
    prompt_validation_error_handler,
    template_error_handler,
)
from style_workbench.api.prompts import router as prompts_router
from style_workbench.api.runs import router as runs_router
from style_workbench.api.styles import router as styles_router
from style_workbench.api.variants import router as variants_router
from style_workbench.core.errors import StyleWorkbenchError
from style_workbench.domain.prompt.template import TemplateError
from style_workbench.domain.prompt.validation import PromptValidationError

app = FastAPI(title="Style Workbench API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(StyleWorkbenchError, domain_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(TemplateError, template_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(PromptValidationError, prompt_validation_error_handler)  # type: ignore[arg-type]

app.include_router(styles_router)
app.include_router(variants_router)
app.include_router(runs_router)
app.include_router(evaluations_router)
app.include_router(prompts_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
