from __future__ import annotations

from fastapi import APIRouter, Depends

from style_workbench.api.deps import get_style_service
from style_workbench.api.schemas.styles import (
    DagCreateRequest,
    DagResponse,
    NodeInputResponse,
    NodeResponse,
    StyleCreateRequest,
    StyleDetailResponse,
    StyleListItemResponse,
    StyleResponse,
    StyleStatusUpdateRequest,
    StyleVersionResponse,
    VariableMappingPayload,
)
from style_workbench.domain.style.entity import DAG
from style_workbench.domain.style.schema import dag_from_dict
from style_workbench.services.style_service import StyleService

router = APIRouter(prefix="/api/styles", tags=["styles"])


def _dag_to_response(dag: DAG) -> DagResponse:
    return DagResponse(
        nodes=[
            NodeResponse(
                id=n.id,
                type=n.type,
                model={"provider": n.model.provider, "model_id": n.model.model_id},
                prompt_template=n.prompt_template,
                inputs=[NodeInputResponse(source=i.source, role=i.role) for i in n.inputs],
                variable_mapping={
                    k: VariableMappingPayload(
                        source=v.source,
                        role=v.role,
                        node_id=v.node_id,
                        value=v.value,
                    )
                    for k, v in n.variable_mapping.items()
                },
            )
            for n in dag.nodes
        ],
        edges=[{"source": e.source, "target": e.target} for e in dag.edges],
        variables=dag.variables,
    )


@router.post("", response_model=StyleResponse, status_code=201)
async def create_style(
    payload: StyleCreateRequest,
    service: StyleService = Depends(get_style_service),
) -> StyleResponse:
    dag = dag_from_dict(payload.dag.model_dump())
    record = await service.create(
        name=payload.name,
        concept=payload.concept,
        vertical=payload.vertical,
        tags=payload.tags,
        dag=dag,
    )
    return StyleResponse(
        id=record.style.id,
        name=record.style.name,
        concept=record.style.concept,
        vertical=record.style.vertical,
        tags=record.style.tags,
        status=record.style.status,
        current_version=record.style.current_version,
        version_id=record.version_id,
        created_at=record.created_at,
    )


@router.get("", response_model=list[StyleListItemResponse])
async def list_styles(
    limit: int = 50,
    offset: int = 0,
    service: StyleService = Depends(get_style_service),
) -> list[StyleListItemResponse]:
    records = await service.list(limit=limit, offset=offset)
    return [
        StyleListItemResponse(
            id=r.style.id,
            name=r.style.name,
            concept=r.style.concept,
            vertical=r.style.vertical,
            tags=r.style.tags,
            status=r.style.status,
            current_version=r.style.current_version,
            version_id=r.version_id,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/{style_id}", response_model=StyleDetailResponse)
async def get_style(
    style_id: str,
    service: StyleService = Depends(get_style_service),
) -> StyleDetailResponse:
    record = await service.get(style_id)
    return StyleDetailResponse(
        id=record.style.id,
        name=record.style.name,
        concept=record.style.concept,
        vertical=record.style.vertical,
        tags=record.style.tags,
        status=record.style.status,
        current_version=record.style.current_version,
        version_id=record.version_id,
        created_at=record.created_at,
        dag=_dag_to_response(record.style.dag),
    )


@router.post("/{style_id}/versions", response_model=StyleVersionResponse, status_code=201)
async def create_style_version(
    style_id: str,
    payload: DagCreateRequest,
    service: StyleService = Depends(get_style_service),
) -> StyleVersionResponse:
    dag = dag_from_dict(payload.dag.model_dump())
    record = await service.save_dag(
        style_id=style_id,
        dag=dag,
        brief=payload.brief,
    )
    return StyleVersionResponse(
        version_id=record.version_id,
        version=record.version,
        current_version=record.current_version,
        created_at=record.created_at,
    )


@router.patch("/{style_id}/status", response_model=StyleResponse)
async def update_style_status(
    style_id: str,
    payload: StyleStatusUpdateRequest,
    service: StyleService = Depends(get_style_service),
) -> StyleResponse:
    record = await service.update_status(style_id, payload.status)
    return StyleResponse(
        id=record.style.id,
        name=record.style.name,
        concept=record.style.concept,
        vertical=record.style.vertical,
        tags=record.style.tags,
        status=record.style.status,
        current_version=record.style.current_version,
        version_id=record.version_id,
        created_at=record.created_at,
    )
