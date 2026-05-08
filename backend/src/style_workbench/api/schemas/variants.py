from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class VariantGenerateRequest(BaseModel):
    concept: str
    vertical: str
    tone: str
    step_composition: list[str] = []
    input_kinds: list[str] = []
    n: int = 5


class StyleSummaryResponse(BaseModel):
    id: str
    name: str
    version_id: str
    tags: list[str]
    created_at: datetime
