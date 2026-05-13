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
    ConflictError,
    DagValidationError,
    RunAbortedError,
    RunNotFoundError,
    VersionNotFoundError,
)
from style_workbench.domain.prompt.modifier import NoopPromptModifier, PromptModifier
from style_workbench.domain.prompt.template import safe_substitute
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG, Node
from style_workbench.domain.style.validation import validate_dag
from style_workbench.domain.style.variables import validate_variables
from style_workbench.engine.run_events import RunEvent, RunEventBus

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
        event_bus: RunEventBus | None = None,
        retry_repo: Any | None = None,
        prompt_modifier: PromptModifier | None = None,
        max_retry: int = 3,
    ) -> None:
        self._budget_won = cost_budget_won
        self._style_repo = style_repo
        self._run_repo = run_repo
        self._session = session
        self._eval_service = eval_service
        self._brief_summary = brief_summary
        self._event_bus = event_bus
        self._retry_repo = retry_repo
        self._prompt_modifier: PromptModifier = (
            prompt_modifier if prompt_modifier is not None else NoopPromptModifier()
        )
        self._max_retry = max_retry

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
        prompt_override: dict[str, str] | None = None,
    ) -> Any:
        """DB-aware run: DAG 로드 -> Run 생성 -> 노드별 실행(+평가+재시도) -> Run 완료.

        eval_service가 None이면 평가 없이 기존 단순 실행 경로를 따른다.
        eval+retry 오케스트레이션은 AutoLoopOrchestrator에 위임한다.

        Args:
            style_version_id: StyleVersion to execute.
            user_input:       Runtime placeholder values.
            prompt_override:  Optional mapping of {node_id: prompt_body}.
                              When provided, the node's prompt_template is replaced
                              with the given body before execution.  Used by A/B
                              comparison (spec §4 FR-8) without mutating the DB.
        """
        from style_workbench.engine.auto_loop import AutoLoopOrchestrator
        from style_workbench.engine.executor import DagExecutor

        assert self._style_repo is not None, "style_repo required for execute()"
        assert self._run_repo is not None, "run_repo required for execute()"
        assert self._session is not None, "session required for execute()"

        version_result = await self._style_repo.get_version(style_version_id)
        if version_result is None:
            raise VersionNotFoundError(f"StyleVersion '{style_version_id}' not found")
        _style_id, dag = version_result

        # Apply prompt_override: patch the node's prompt_template in-memory only.
        # This does NOT mutate the DB — it is used solely for A/B comparison.
        if prompt_override:
            import dataclasses

            patched_nodes = []
            for node in dag.nodes:
                if node.id in prompt_override:
                    patched_nodes.append(
                        dataclasses.replace(node, prompt_template=prompt_override[node.id])
                    )
                else:
                    patched_nodes.append(node)
            dag = dataclasses.replace(dag, nodes=patched_nodes)

        validate_dag(dag)

        run_record = await self._run_repo.create(style_version_id, dict(user_input))

        executor = DagExecutor(self._session, event_bus=self._event_bus)
        run_failed = False
        try:
            if self._eval_service is None:
                # 평가 없이 기존 경로 실행
                exec_result = await executor.execute(dag, dict(user_input), run_record.id)
                total_cost = Decimal(
                    str(round(sum(o.cost_usd for o in exec_result.outputs.values()), 8))
                )
            else:
                # eval+retry 루프를 AutoLoopOrchestrator에 위임
                # retry_repo가 없으면 임시 noop repo를 사용 (테스트 호환)
                retry_repo = self._retry_repo
                if retry_repo is None:
                    from style_workbench.infra.repositories.retry_attempt_repo import (
                        SqlAlchemyRetryAttemptRepo,
                    )

                    retry_repo = SqlAlchemyRetryAttemptRepo(self._session)

                orchestrator = AutoLoopOrchestrator(
                    executor=executor,
                    eval_service=self._eval_service,
                    retry_repo=retry_repo,
                    prompt_modifier=self._prompt_modifier,
                    max_retry=self._max_retry,
                    cost_budget_won=self._budget_won,
                    usd_to_won=_USD_TO_WON,
                    event_bus=self._event_bus,
                )
                loop_result = await orchestrator.run(
                    dag=dag,
                    user_input=dict(user_input),
                    run_id=run_record.id,
                    brief_summary=self._brief_summary,
                )
                total_cost = loop_result.total_cost

            await self._run_repo.update_status(
                run_record.id,
                "succeeded",
                total_cost=total_cost,
                finished_at=datetime.now(UTC),
            )
        except RunAbortedError:
            if not run_failed:
                # budget guard or node failure → mark run failed
                await self._run_repo.update_status(
                    run_record.id, "failed", finished_at=datetime.now(UTC)
                )
                if self._event_bus is not None:
                    await self._event_bus.publish(
                        RunEvent(run_id=run_record.id, event_type="run_failed", payload={})
                    )
            raise
        finally:
            # 어떤 경로를 통해 종료하든 반드시 구독 스트림을 닫는다 (FR-10 멱등 invariant)
            if self._event_bus is not None:
                self._event_bus.close_run(run_record.id)

        final = await self._run_repo.get(run_record.id)
        assert final is not None
        return final

    async def get_run(self, run_id: str) -> Any:
        assert self._run_repo is not None, "run_repo required for get_run()"
        record = await self._run_repo.get(run_id)
        if record is None:
            raise RunNotFoundError(f"Run '{run_id}' not found")
        return record

    async def abort(self, run_id: str, reason: str | None = None) -> Any:
        """Abort a run that is currently in-progress.

        Steps:
        1. Load the run (RunNotFoundError → 404 if absent).
        2. Reject if already in a terminal state (ConflictError → 409).
        3. Set run.status='aborted', finished_at=now().
        4. Bulk-abort any running node_executions.
        5. Return the refreshed RunRecord.
        """
        assert self._run_repo is not None, "run_repo required for abort()"

        record = await self._run_repo.get(run_id)
        if record is None:
            raise RunNotFoundError(f"Run '{run_id}' not found")

        _TERMINAL_STATUSES = frozenset({"succeeded", "failed", "aborted"})
        if record.status in _TERMINAL_STATUSES:
            raise ConflictError(f"Run '{run_id}' is already in terminal state '{record.status}'")

        now = datetime.now(UTC)
        if reason:
            logger.info("run_abort_requested", run_id=run_id, reason_hash=hash(reason))
        else:
            logger.info("run_abort_requested", run_id=run_id)

        await self._run_repo.abort_run(run_id, finished_at=now)

        refreshed = await self._run_repo.get(run_id)
        assert refreshed is not None
        return refreshed

    # ------------------------------------------------------------------
    async def _run_node(
        self,
        node: Node,
        variables: dict[str, str],
        run_result: RunResult,
    ) -> ModelOutput:
        prompt = safe_substitute(node.prompt_template, variables)
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
