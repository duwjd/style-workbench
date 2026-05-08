from __future__ import annotations

from fastapi import APIRouter, Depends

from style_workbench.api.deps import get_variant_service
from style_workbench.api.schemas.variants import StyleSummaryResponse, VariantGenerateRequest
from style_workbench.services.variant_service import VariantBrief, VariantService

router = APIRouter(prefix="/api/variants", tags=["variants"])


@router.post("", response_model=list[StyleSummaryResponse], status_code=201)
async def generate_variants(
    payload: VariantGenerateRequest,
    service: VariantService = Depends(get_variant_service),
) -> list[StyleSummaryResponse]:
    brief = VariantBrief(
        concept=payload.concept,
        vertical=payload.vertical,
        tone=payload.tone,
        step_composition=payload.step_composition,
        input_kinds=payload.input_kinds,
        n=payload.n,
    )
    records = await service.generate(brief, save=True)
    return [
        StyleSummaryResponse(
            id=r.style.id,
            name=r.style.name,
            version_id=r.version_id,
            tags=r.style.tags,
            created_at=r.created_at,
        )
        for r in records
    ]
