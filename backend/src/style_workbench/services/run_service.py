from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from style_workbench.adapters.base import ModelInput, ModelOutput
from style_workbench.adapters.registry import get_adapter
from style_workbench.core.errors import (
    DagValidationError,
    RunAbortedError,
    RunNotFoundError,
    VersionNotFoundError,
)
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG, Node
from style_workbench.domain.style.validation import validate_dag
from style_workbench.domain.style.variables import validate_variables

logger = structlog.get_logger(__name__)

# 1 USD ≈ 1,400 KRW (rough constant; production should read from config)
_USD_TO_WON = 1_400.0


@dataclass
class NodeResult:
    node_id: str
    output: ModelOutput


@dataclass
class RunResult:
    style_id: str
    node_results: list[NodeResult] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.output.cost_usd for r in self.node_results)

    @property
    def total_cost_won(self) -> float:
        return self.total_cost_usd * _USD_TO_WON


class RunService:
    """Execute a Style DAG node-by-node in topological order."""

    def __init__(
        self,
        cost_budget_won: float = 100_000.0,
        style_repo: Any | None = None,
        run_repo: Any | None = None,
        session: AsyncSession | None = None,
        eval_service: Any | None = None,
        brief_summary: str = "",
    ) -> None:
        self._budget_won = cost_budget_won
        self._style_repo = style_repo
        self._run_repo = run_repo
        self._session = session
        self._eval_service = eval_service
        self._brief_summary = brief_summary

    async def run(
        self,
        style_id: str,
        dag: DAG,
        variables: dict[str, str],
    ) -> RunResult:
        """Validate and execute all nodes in topological order.

        Args:
            style_id:  Identifier for logging/tracing.
            dag:       The DAG to execute.
            variables: Runtime values keyed by placeholder name.

        Raises:
            DagValidationError: If DAG fails structural checks.
            RunAbortedError:    If budget exceeded or a node fails.
        """
        validate_dag(dag)
        self._check_variables(dag, variables)

        node_map = {n.id: n for n in dag.nodes}
        order = topological_sort(dag)

        result = RunResult(style_id=style_id)

        for node_id in order:
            node = node_map[node_id]
            output = await self._run_node(node, variables, result)
            result.node_results.append(NodeResult(node_id=node_id, output=output))

            if result.total_cost_won > self._budget_won:
                raise RunAbortedError(
                    f"Budget exceeded after node '{node_id}': "
                    f"{result.total_cost_won:.0f}₩ > {self._budget_won:.0f}₩"
                )

        logger.info(
            "run_complete",
            style_id=style_id,
            nodes=len(result.node_results),
            cost_usd=round(result.total_cost_usd, 6),
        )
        return result

    async def execute(
        self,
        style_version_id: str,
        user_input: dict[str, Any],
    ) -> Any:
        """DB-aware run: DAG 로드 -> Run 생성 -> 노드별 실행(+평가+재시도) -> Run 완료.

        eval_service가 None이면 평가 없이 기존 단순 실행 경로를 따른다.
        """
        from style_workbench.engine.executor import DagExecutor
        from style_workbench.engine.retry import RetryPolicy, RetryState

        assert self._style_repo is not None, "style_repo required for execute()"
        assert self._run_repo is not None, "run_repo required for execute()"
        assert self._session is not None, "session required for execute()"

        version_result = await self._style_repo.get_version(style_version_id)
        if version_result is None:
            raise VersionNotFoundError(f"StyleVersion '{style_version_id}' not found")
        _style_id, dag = version_result
        validate_dag(dag)

        run_record = await self._run_repo.create(style_version_id, dict(user_input))

        executor = DagExecutor(self._session)
        run_failed = False
        try:
            if self._eval_service is None:
                # 평가 없이 기존 경로 실행
                exec_result = await executor.execute(dag, dict(user_input), run_record.id)
                total_cost = Decimal(
                    str(round(sum(o.cost_usd for o in exec_result.outputs.values()), 8))
                )
            else:
                # 노드별 실행 + 평가 + retry 루프
                node_map = {n.id: n for n in dag.nodes}
                order = topological_sort(dag)
                outputs: dict[str, ModelOutput] = {}
                total_cost = Decimal("0")

                for node_id in order:
                    node = node_map[node_id]
                    prompt = DagExecutor._resolve_prompt(node, dict(user_input), outputs)
                    retry_state = RetryState(node_id=node_id)
                    last_eval_result = None

                    while True:
                        output, ne_id = await executor.execute_node(
                            node, prompt, run_record.id, outputs
                        )
                        outputs[node_id] = output
                        total_cost += Decimal(str(round(output.cost_usd, 8)))

                        last_eval_result = await self._eval_service.evaluate(
                            ne_id, self._brief_summary
                        )
                        if last_eval_result.overall_passed:
                            break

                        if not RetryPolicy.should_retry(retry_state):
                            # 최대 재시도 초과 — run을 failed로 마킹 후 abort
                            run_failed = True
                            await self._run_repo.update_status(
                                run_record.id,
                                "failed",
                                finished_at=datetime.now(UTC),
                            )
                            raise RunAbortedError(
                                f"Node '{node_id}' failed after "
                                f"{retry_state.attempt} retries. "
                                f"Failed dimensions: {last_eval_result.failed_dimensions}"
                            )

                        prompt, retry_state = RetryPolicy.apply_modifiers(
                            prompt,
                            last_eval_result.retry_guidance,
                            last_eval_result.failed_dimensions,
                            retry_state,
                        )

            await self._run_repo.update_status(
                run_record.id,
                "succeeded",
                total_cost=total_cost,
                finished_at=datetime.now(UTC),
            )
        except RunAbortedError:
            if not run_failed:
                # eval retry abort 이외의 실패(노드 실행 자체 오류 등)를 처리
                await self._run_repo.update_status(
                    run_record.id, "failed", finished_at=datetime.now(UTC)
                )
            raise

        final = await self._run_repo.get(run_record.id)
        assert final is not None
        return final

    async def get_run(self, run_id: str) -> Any:
        assert self._run_repo is not None, "run_repo required for get_run()"
        record = await self._run_repo.get(run_id)
        if record is None:
            raise RunNotFoundError(f"Run '{run_id}' not found")
        return record

    # ------------------------------------------------------------------
    async def _run_node(
        self,
        node: Node,
        variables: dict[str, str],
        run_result: RunResult,
    ) -> ModelOutput:
        prompt = node.prompt_template.format_map(variables)
        adapter = get_adapter(node.model.provider)
        inp = ModelInput(model_id=node.model.model_id, prompt=prompt)

        logger.info("node_start", node_id=node.id, model=node.model.model_id)
        try:
            output = await adapter.generate(inp)
        except Exception as exc:
            raise RunAbortedError(f"Node '{node.id}' failed: {exc}") from exc

        logger.info(
            "node_done",
            node_id=node.id,
            cost_usd=round(output.cost_usd, 6),
        )
        return output

    @staticmethod
    def _check_variables(dag: DAG, provided: dict[str, str]) -> None:
        for node in dag.nodes:
            missing = validate_variables(node.prompt_template, set(provided))
            if missing:
                raise DagValidationError(
                    f"Node '{node.id}' missing variables at runtime: {missing}"
                )
