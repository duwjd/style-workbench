from __future__ import annotations

from fastapi import APIRouter, Depends

from style_workbench.api.deps import get_run_service
from style_workbench.api.schemas.runs import NodeExecutionResponse, RunCreateRequest, RunResponse
from style_workbench.infra.repositories.run_repo import RunRecord
from style_workbench.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _to_response(record: RunRecord) -> RunResponse:
    return RunResponse(
        id=record.id,
        style_version_id=record.style_version_id,
        style_id=record.style_id,
        status=record.status,
        total_cost=record.total_cost,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        node_executions=[
            NodeExecutionResponse(
                id=ne.id,
                node_id=ne.node_id,
                node_type=ne.node_type,
                model_provider=ne.model_provider,
                model_id=ne.model_id,
                artifact_url=ne.artifact_url,
                cost=ne.cost,
                status=ne.status,
                started_at=ne.started_at,
                finished_at=ne.finished_at,
            )
            for ne in record.node_executions
        ],
    )


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    payload: RunCreateRequest,
    service: RunService = Depends(get_run_service),
) -> RunResponse:
    record = await service.execute(
        style_version_id=payload.style_version_id,
        user_input=payload.user_input,
    )
    return _to_response(record)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> RunResponse:
    record = await service.get_run(run_id)
    return _to_response(record)
