from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.errors import RunAbortedError
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG, Node
from style_workbench.engine.node_runners.base import NodeRunner
from style_workbench.infra.db.models.run import NodeExecution

logger = structlog.get_logger(__name__)


@dataclass
class RunResult:
    run_id: str
    outputs: dict[str, ModelOutput] = field(default_factory=dict)
    # node_id -> ne_id 매핑 (retry 루프에서 EvaluationService에 전달)
    ne_ids: dict[str, str] = field(default_factory=dict)


class DagExecutor:
    """Execute a Style DAG in topological order, persisting each node result to DB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(
        self,
        dag: DAG,
        user_input: dict[str, Any],
        run_id: str,
    ) -> RunResult:
        node_map = {n.id: n for n in dag.nodes}
        order = topological_sort(dag)
        result = RunResult(run_id=run_id)

        for node_id in order:
            node = node_map[node_id]
            prompt = self._resolve_prompt(node, user_input, result.outputs)
            output, ne_id = await self.execute_node(node, prompt, run_id, result.outputs)
            result.outputs[node_id] = output
            result.ne_ids[node_id] = ne_id

        return result

    async def execute_node(
        self,
        node: Node,
        prompt: str,
        run_id: str,
        upstream_outputs: dict[str, ModelOutput] | None = None,
    ) -> tuple[ModelOutput, str]:
        """단일 노드 실행 + DB persist.

        RunService retry 루프에서도 직접 호출된다.

        Returns:
            (ModelOutput, ne_id) 튜플. ne_id는 EvaluationService에 전달한다.
        """
        started_at = datetime.now(UTC)
        logger.info("node_start", run_id=run_id, node_id=node.id, model=node.model.model_id)
        try:
            runner = NodeRunner.for_type(node.type)
            output = await runner.run(node, prompt)
        except Exception as exc:
            raise RunAbortedError(f"Node '{node.id}' failed: {exc}") from exc

        finished_at = datetime.now(UTC)
        ne_id = await self._persist_node_execution(
            run_id, node, prompt, output, started_at, finished_at
        )
        logger.info(
            "node_done",
            run_id=run_id,
            node_id=node.id,
            cost_usd=round(output.cost_usd, 6),
        )
        return output, ne_id

    @staticmethod
    def _resolve_prompt(
        node: Node,
        user_input: dict[str, Any],
        outputs: dict[str, ModelOutput],
    ) -> str:
        context: dict[str, str] = {k: str(v) for k, v in user_input.items()}
        for node_input in node.inputs:
            if node_input.source.startswith("node_output:"):
                src_id = node_input.source.removeprefix("node_output:")
                prev = outputs.get(src_id)
                if prev is not None:
                    context[node_input.role] = prev.text or prev.artifact_url or ""
        return node.prompt_template.format_map(context)

    async def _persist_node_execution(
        self,
        run_id: str,
        node: Node,
        prompt: str,
        output: ModelOutput,
        started_at: datetime,
        finished_at: datetime,
    ) -> str:
        """NodeExecution을 DB에 저장하고 생성된 id를 반환한다."""
        ne = NodeExecution(
            run_id=run_id,
            node_id=node.id,
            node_type=str(node.type),
            model_provider=node.model.provider,
            model_id=node.model.model_id,
            prompt_resolved=prompt,
            artifact_url=output.artifact_url,
            raw_response={"text": output.text} if output.text else None,
            cost=Decimal(str(round(output.cost_usd, 8))),
            status="succeeded",
            started_at=started_at,
            finished_at=finished_at,
        )
        self._session.add(ne)
        await self._session.flush()
        await self._session.refresh(ne)
        return str(ne.id)
