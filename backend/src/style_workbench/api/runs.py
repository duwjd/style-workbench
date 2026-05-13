from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from style_workbench.api.deps import (
    get_evaluation_service,
    get_event_bus,
    get_retry_attempt_repo,
    get_run_service,
)
from style_workbench.api.schemas.evaluations import EvaluationResponse
from style_workbench.api.schemas.runs import (
    NodeExecutionResponse,
    RetryAttemptListResponse,
    RetryAttemptResponse,
    RunAbortRequest,
    RunCreateRequest,
    RunResponse,
)
from style_workbench.engine.run_events import RunEventBus
from style_workbench.infra.repositories.evaluation_repo import EvaluationRecord
from style_workbench.infra.repositories.retry_attempt_repo import SqlAlchemyRetryAttemptRepo
from style_workbench.infra.repositories.run_repo import RunRecord
from style_workbench.services.evaluation_service import EvaluationService
from style_workbench.services.run_service import RunService

router = APIRouter(prefix="/api/runs", tags=["runs"])

_TERMINAL_EVENT_TYPES = frozenset({"run_completed", "run_failed", "run_aborted"})


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


@router.post("/{run_id}/abort", response_model=RunResponse, status_code=200)
async def abort_run(
    run_id: str,
    payload: RunAbortRequest = RunAbortRequest(),
    service: RunService = Depends(get_run_service),
) -> RunResponse:
    record = await service.abort(run_id, reason=payload.reason)
    return _to_response(record)


@router.get("/{run_id}/evaluations", response_model=list[EvaluationResponse])
async def list_run_evaluations(
    run_id: str,
    eval_service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationResponse]:
    records = await eval_service.list_by_run(run_id)
    return [_eval_record_to_response(r) for r in records]


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    service: RunService = Depends(get_run_service),
    bus: RunEventBus = Depends(get_event_bus),
) -> EventSourceResponse:
    """Run 진행 이벤트를 SSE 스트림으로 반환한다.

    - 스트림 시작 시 현재 Run 상태를 `snapshot` 이벤트로 1회 emit한다 (재연결 동기화).
    - 이후 `node_started`, `node_completed`, `node_failed`,
      `run_completed`, `run_failed`, `run_aborted` 이벤트를 순서대로 emit한다.
    - terminal 이벤트(`run_completed`, `run_failed`, `run_aborted`) 수신 후 스트림을 닫는다.
    - run_id가 존재하지 않으면 RunNotFoundError → 404로 매핑된다.
    """
    # run 존재 확인 (없으면 RunNotFoundError → 404)
    current = await service.get_run(run_id)

    async def _event_generator() -> AsyncGenerator[dict[str, Any], None]:
        # 현재 상태 snapshot (재연결 시 동기화용)
        snapshot_data = json.dumps(
            {
                "id": current.id,
                "status": current.status,
                "total_cost": str(current.total_cost) if current.total_cost is not None else None,
            }
        )
        yield {"event": "snapshot", "data": snapshot_data}

        # run이 이미 terminal 상태면 스트림을 즉시 닫는다
        if current.status in ("succeeded", "failed", "aborted"):
            return

        async for event in bus.subscribe(run_id):
            # 클라이언트 disconnection 감지
            if await request.is_disconnected():
                break

            yield {
                "event": event.event_type,
                "data": json.dumps({"type": event.event_type, "payload": event.payload}),
            }

            if event.event_type in _TERMINAL_EVENT_TYPES:
                break

    return EventSourceResponse(_event_generator())


@router.get("/{run_id}/retry-attempts", response_model=RetryAttemptListResponse)
async def list_retry_attempts(
    run_id: str,
    service: RunService = Depends(get_run_service),
    retry_repo: SqlAlchemyRetryAttemptRepo = Depends(get_retry_attempt_repo),
) -> RetryAttemptListResponse:
    """Return all retry attempts for a run, enriched with evaluation outcome.

    Spec §6.1 / §6.2 — read-only, no ETag required.
    Raises RunNotFoundError (→ 404) if run_id does not exist.
    """
    # Verify run exists; raises RunNotFoundError → 404 via exception handler
    await service.get_run(run_id)

    with_evals = await retry_repo.list_with_evaluations(run_id)

    attempts = [
        RetryAttemptResponse(
            id=row.attempt.id,
            node_id=row.attempt.node_id,
            attempt_number=row.attempt.attempt_number,
            prompt_version_id_used=row.attempt.prompt_version_id_used,
            retry_guidance=row.attempt.retry_guidance,
            evaluation_id=row.attempt.evaluation_id,
            cost_won=row.attempt.cost_won,
            passed=row.passed,
            failed_dimensions=row.failed_dimensions,
            started_at=row.attempt.started_at,
            finished_at=row.attempt.finished_at,
        )
        for row in with_evals
    ]

    # succeeded: last attempt's passed field (None if no attempts or no eval yet)
    succeeded: bool | None = None
    if attempts:
        succeeded = attempts[-1].passed

    return RetryAttemptListResponse(
        run_id=run_id,
        attempts=attempts,
        total_attempts=len(attempts),
        succeeded=succeeded,
    )


def _eval_record_to_response(record: EvaluationRecord) -> EvaluationResponse:
    return EvaluationResponse(
        id=record.id,
        node_execution_id=record.node_execution_id,
        node_id=record.node_id,
        node_type=record.node_type,
        evaluator_model=record.evaluator_model,
        overall_result=record.overall_result,
        dimensions=record.dimensions,
        retry_guidance=record.retry_guidance,
        failed_dimensions=record.failed_dimensions,
        human_verdict=record.human_verdict,
        human_comment=record.human_comment,
        created_at=record.created_at,
    )
