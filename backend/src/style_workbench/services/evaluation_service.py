from __future__ import annotations

from datetime import UTC, datetime

import structlog

from style_workbench.adapters.base import ModelInput, ModelOutput
from style_workbench.adapters.claude import ClaudeAdapter
from style_workbench.core.errors import RunNotFoundError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.evaluation.criteria import PASS_THRESHOLD, dimensions_for
from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.domain.style.entity import NodeType
from style_workbench.engine.retry import RETRY_MODIFIERS
from style_workbench.infra.repositories.evaluation_repo import SqlAlchemyEvaluationRepository
from style_workbench.infra.repositories.run_repo import NodeExecutionRecord, SqlAlchemyRunRepository
from style_workbench.prompts.evaluator_composition import build_composition_eval_input
from style_workbench.prompts.evaluator_image import build_image_eval_input
from style_workbench.prompts.evaluator_text import (
    EVALUATOR_MODEL,
    build_text_eval_input,
)
from style_workbench.prompts.evaluator_video import build_video_eval_input
from style_workbench.prompts.shared.format_brief import summarize_for_evaluator
from style_workbench.prompts.shared.output_schema import parse_eval_output

logger = structlog.get_logger(__name__)


def _build_retry_guidance(failed_dims: list[str]) -> str | None:
    """실패한 차원별 modifier 문구를 이어붙여 retry_guidance를 생성한다."""
    parts = [RETRY_MODIFIERS[d] for d in failed_dims if d in RETRY_MODIFIERS]
    return "\n".join(parts) if parts else None


class EvaluationService:
    """Step Evaluator 유스케이스.

    NodeExecution의 결과물을 ClaudeAdapter(vision)를 통해 평가하고,
    EvaluationResult를 DB에 저장한다.
    """

    def __init__(
        self,
        run_repo: SqlAlchemyRunRepository,
        eval_repo: SqlAlchemyEvaluationRepository,
        claude_adapter: ClaudeAdapter,
    ) -> None:
        self._run_repo = run_repo
        self._eval_repo = eval_repo
        self._claude = claude_adapter

    async def evaluate(
        self,
        node_execution_id: str,
        brief_summary: str = "",
    ) -> EvaluationResult:
        """단일 NodeExecution을 평가하고 결과를 DB에 저장한다.

        Args:
            node_execution_id: 평가 대상 NodeExecution.id.
            brief_summary: RunService가 제공하는 brief 요약 (원본 prompt 아님).

        Raises:
            RunNotFoundError: NodeExecution이 존재하지 않을 때.
        """
        ne = await self._run_repo.get_node_execution(node_execution_id)
        if ne is None:
            raise RunNotFoundError(f"NodeExecution '{node_execution_id}' not found")

        node_type = NodeType(ne.node_type)
        brief_ctx = summarize_for_evaluator(node_type, brief_summary)
        dims = sorted(dimensions_for(node_type))  # 안정적인 순서 보장

        model_input = self._build_eval_input(node_type, ne, brief_ctx, dims)

        logger.info("eval_start", ne_id=node_execution_id, node_type=ne.node_type)
        raw_output: ModelOutput = await self._claude.generate(model_input)
        logger.info(
            "eval_done",
            ne_id=node_execution_id,
            cost_usd=round(raw_output.cost_usd, 6),
        )

        eval_out = parse_eval_output(raw_output.text)

        dimension_scores = [
            DimensionScore(
                name=k,
                score=eval_out.scores.get(k, 0.0),
                rationale=eval_out.rationale.get(k, ""),
            )
            for k in dims
        ]

        failed_dims = [d.name for d in dimension_scores if d.score < PASS_THRESHOLD]
        retry_guidance = _build_retry_guidance(failed_dims)

        result = EvaluationResult(
            id=new_ulid(),
            node_execution_id=node_execution_id,
            evaluator_model=EVALUATOR_MODEL,
            dimensions=dimension_scores,
            notable_issues=eval_out.notable_issues,
            retry_guidance=retry_guidance,
            created_at=datetime.now(UTC),
        )

        await self._eval_repo.save(result)
        logger.info(
            "eval_saved",
            ne_id=node_execution_id,
            passed=result.overall_passed,
            failed_dims=failed_dims,
        )
        return result

    def _build_eval_input(
        self,
        node_type: NodeType,
        ne: NodeExecutionRecord,
        brief_ctx: str,
        dims: list[str],
    ) -> ModelInput:
        if node_type == NodeType.TEXT_GENERATION:
            text = (ne.raw_response or {}).get("text", "")
            return build_text_eval_input(brief_ctx, str(text), dims)
        elif node_type == NodeType.IMAGE_GENERATION:
            return build_image_eval_input(brief_ctx, ne.artifact_url or "", dims)
        elif node_type == NodeType.VIDEO_GENERATION:
            frame_urls: list[str] = [ne.artifact_url] if ne.artifact_url else []
            return build_video_eval_input(brief_ctx, frame_urls, dims)
        else:
            # COMPOSITION
            return build_composition_eval_input(brief_ctx, ne.artifact_url, dims)
