from __future__ import annotations

from fastapi import APIRouter, Depends

from style_workbench.api.deps import get_evaluation_service
from style_workbench.api.schemas.evaluations import EvaluationResponse, VerdictRequest
from style_workbench.infra.repositories.evaluation_repo import EvaluationRecord
from style_workbench.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


def _record_to_response(record: EvaluationRecord) -> EvaluationResponse:
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


@router.post("/{evaluation_id}/verdict", response_model=EvaluationResponse, status_code=200)
async def submit_verdict(
    evaluation_id: str,
    payload: VerdictRequest,
    eval_service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResponse:
    """디자이너가 평가 결과에 채택/기각 verdict 를 기록한다.

    Raises:
        EvaluationNotFoundError → 404 (exception_handlers 에서 변환).
    """
    record = await eval_service.update_human_verdict(
        evaluation_id=evaluation_id,
        verdict=payload.verdict,
        comment=payload.comment,
    )
    return _record_to_response(record)
