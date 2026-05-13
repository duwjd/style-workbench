"""AutoLoopOrchestrator — node-level eval+retry orchestration (F01 §FR-7).

Extracted from services/run_service.py execute() eval+retry block.
RunService.execute() now delegates the eval+retry cycle here and keeps
only the transaction boundary and repo calls.

Design invariants (enforced by static check and tests):
  - NO imports from anthropic / openai / replicate (FR-9 / AC-8).
  - NO calls to style_repo.update_status(..., 'approved', ...) (FR-6 / AC-7).
  - Style.status auto-transition is strictly forbidden here.
  - Budget guard fires BEFORE the evaluator call (FR-2, W1 preserved).
  - RetryAttempt row saved for every attempt including the first (FR-4, AC-5).

Event Bus (FR-10 / AC-11):
  - close_run() is the caller's (RunService) responsibility.
  - AutoLoopOrchestrator does NOT call close_run().
  - SSE event responsibility split (단계 3):
      engine layer: node_retry, run_budget_exceeded  ← emitted here
      service layer: run_completed, run_failed        ← RunService.execute() only
  - node_started / node_completed / node_failed flow via DagExecutor.execute_node().

attempt_number convention:
  - 0  = first (original) execution.
  - 1  = first retry (after FAIL on attempt 0).
  - max_retry  = last allowed attempt before abort.
  i.e. total attempts = max_retry + 1.  For max_retry=3 → attempts 0,1,2,3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import structlog

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.errors import RunAbortedError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.auto_loop.entity import RetryAttempt
from style_workbench.domain.auto_loop.repo import RetryAttemptRepo
from style_workbench.domain.prompt.modifier import NoopPromptModifier, PromptModifier
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG
from style_workbench.engine.retry import RetryPolicy, RetryState
from style_workbench.engine.run_events import RunEvent, RunEventBus

if TYPE_CHECKING:
    from style_workbench.engine.executor import DagExecutor
    from style_workbench.services.evaluation_service import EvaluationService

logger = structlog.get_logger(__name__)

# 1 USD ≈ 1,400 KRW — mirrors run_service._USD_TO_WON
_USD_TO_WON = 1_400.0


@dataclass
class AutoLoopResult:
    """Summary returned by AutoLoopOrchestrator.run() on full success.

    outputs:           final ModelOutput per node_id.
    total_cost:        cumulative cost across all attempts (including retries).
    attempts_per_node: number of attempts made per node_id (1 = first try PASS).
    """

    outputs: dict[str, ModelOutput] = field(default_factory=dict)
    total_cost: Decimal = field(default_factory=lambda: Decimal("0"))
    attempts_per_node: dict[str, int] = field(default_factory=dict)


class AutoLoopOrchestrator:
    """Executes a DAG node-by-node with evaluation and retry.

    For each node (in topological order):
      1. Execute the node via DagExecutor.execute_node().
      2. Apply budget guard (raises RunAbortedError if exceeded).
      3. Evaluate the output via EvaluationService.evaluate().
      4. Save a RetryAttempt row.
      5. If PASS → proceed to next node.
      6. If FAIL and attempt < max_retry → call PromptModifier, increment attempt.
      7. If FAIL and attempt == max_retry → raise RunAbortedError (RunService emits run_failed).

    Caller (RunService) owns the transaction boundary and repo commit.
    This class does NOT commit; it only flushes via repo.create().
    """

    def __init__(
        self,
        executor: DagExecutor,
        eval_service: EvaluationService,
        retry_repo: RetryAttemptRepo,
        prompt_modifier: PromptModifier | None = None,
        max_retry: int = 3,
        cost_budget_won: float = 100_000.0,
        usd_to_won: float = _USD_TO_WON,
        event_bus: RunEventBus | None = None,
    ) -> None:
        self._executor = executor
        self._eval_service = eval_service
        self._retry_repo = retry_repo
        self._modifier: PromptModifier = (
            prompt_modifier if prompt_modifier is not None else NoopPromptModifier()
        )
        self._max_retry = max_retry
        self._budget_won = cost_budget_won
        self._usd_to_won = usd_to_won
        self._event_bus = event_bus

    async def run(
        self,
        dag: DAG,
        user_input: dict[str, Any],
        run_id: str,
        brief_summary: str = "",
    ) -> AutoLoopResult:
        """Execute all DAG nodes with eval+retry.

        Returns AutoLoopResult on complete success.
        Raises RunAbortedError on budget exceeded or max_retry exceeded.

        Caller must:
          - Publish run_failed SSE event after catching RunAbortedError.
          - Call event_bus.close_run() in the finally block.
          - Commit the transaction after this method returns.
        """
        node_map = {n.id: n for n in dag.nodes}
        order = topological_sort(dag)

        result = AutoLoopResult()

        for node_id in order:
            node = node_map[node_id]
            # Resolve the initial prompt for this node using upstream outputs
            from style_workbench.engine.executor import DagExecutor

            prompt = DagExecutor._resolve_prompt(node, user_input, result.outputs)

            retry_state = RetryState(node_id=node_id)
            # prompt_version_id_used: None for inline-prompt nodes (F05 not yet linked)
            current_prompt_version_id: str | None = None
            # retry_guidance carried from previous failed attempt (None for attempt 0)
            previous_guidance: dict[str, Any] | None = None

            while True:
                attempt_number = retry_state.attempt
                started_at = datetime.now(UTC)

                output, ne_id = await self._executor.execute_node(
                    node, prompt, run_id, result.outputs
                )

                finished_at = datetime.now(UTC)
                cost_won = Decimal(str(round(output.cost_usd * self._usd_to_won, 2)))
                result.total_cost += Decimal(str(round(output.cost_usd, 8)))

                # FR-2 / W1: budget guard fires BEFORE evaluator call
                total_cost_won = float(result.total_cost) * self._usd_to_won
                if total_cost_won > self._budget_won:
                    # Save the attempt row (no evaluation_id yet — budget fired first)
                    await self._save_attempt(
                        run_id=run_id,
                        node_id=node_id,
                        ne_id=ne_id,
                        attempt_number=attempt_number,
                        prompt_version_id=current_prompt_version_id,
                        retry_guidance=previous_guidance,
                        evaluation_id=None,
                        cost_won=cost_won,
                        started_at=started_at,
                        finished_at=finished_at,
                    )
                    logger.warning(
                        "auto_loop_budget_exceeded",
                        run_id=run_id,
                        node_id=node_id,
                        total_cost_won=round(total_cost_won, 2),
                        budget_won=self._budget_won,
                    )
                    # run_budget_exceeded SSE event — engine layer (per-node event)
                    if self._event_bus is not None:
                        await self._event_bus.publish(
                            RunEvent(
                                run_id=run_id,
                                event_type="run_budget_exceeded",
                                payload={
                                    "node_id": node_id,
                                    "total_cost_won": round(total_cost_won, 2),
                                    "budget_won": self._budget_won,
                                },
                            )
                        )
                    raise RunAbortedError(
                        f"Budget exceeded after node '{node_id}': "
                        f"{total_cost_won:.0f}₩ > {self._budget_won:.0f}₩"
                    )

                # Evaluate the output
                eval_result = await self._eval_service.evaluate(ne_id, brief_summary)

                # retry_guidance is already dict[str, Any] | None from EvaluationResult
                # previous_guidance carries the guidance dict from the prior failed attempt.
                await self._save_attempt(
                    run_id=run_id,
                    node_id=node_id,
                    ne_id=ne_id,
                    attempt_number=attempt_number,
                    prompt_version_id=current_prompt_version_id,
                    retry_guidance=previous_guidance,
                    evaluation_id=eval_result.id,
                    cost_won=cost_won,
                    started_at=started_at,
                    finished_at=finished_at,
                )

                if eval_result.overall_passed:
                    result.outputs[node_id] = output
                    result.attempts_per_node[node_id] = attempt_number + 1
                    logger.info(
                        "auto_loop_node_passed",
                        run_id=run_id,
                        node_id=node_id,
                        attempt=attempt_number,
                    )
                    break

                # FAIL path
                if not RetryPolicy.should_retry(retry_state):
                    # max_retry exhausted — raise only; RunService.execute() emits run_failed
                    logger.warning(
                        "auto_loop_max_retry_exceeded",
                        run_id=run_id,
                        node_id=node_id,
                        attempt=attempt_number,
                        failed_dims=eval_result.failed_dimensions,
                    )
                    raise RunAbortedError(
                        f"Node '{node_id}' failed after "
                        f"{attempt_number} retries. "
                        f"Failed dimensions: {eval_result.failed_dimensions}"
                    )

                # node_retry SSE event — engine layer (per-node event)
                # Published AFTER FAIL evaluation and BEFORE modifier/next attempt.
                # attempt_number+1 is the next attempt that is about to start.
                if self._event_bus is not None:
                    await self._event_bus.publish(
                        RunEvent(
                            run_id=run_id,
                            event_type="node_retry",
                            payload={
                                "node_id": node_id,
                                "attempt_number": attempt_number + 1,
                                "retry_guidance": eval_result.retry_guidance or {},
                                "failed_dimensions": list(eval_result.failed_dimensions),
                            },
                        )
                    )

                # Prepare next attempt via PromptModifier.
                # eval_result.retry_guidance is already dict[str, Any] | None.
                guidance_dict: dict[str, Any] = eval_result.retry_guidance or {}

                _new_text, new_version_id = await self._modifier.modify(
                    prompt_version_id=current_prompt_version_id,
                    retry_guidance=guidance_dict,
                    failed_dimensions=eval_result.failed_dimensions,
                )

                if new_version_id is not None and new_version_id != current_prompt_version_id:
                    # F02 created a new version — use new text
                    current_prompt_version_id = new_version_id
                    prompt = _new_text
                else:
                    # NoopPromptModifier or same version: apply RetryPolicy string modifiers
                    prompt, retry_state = RetryPolicy.apply_modifiers(
                        prompt,
                        eval_result.retry_guidance,
                        eval_result.failed_dimensions,
                        retry_state,
                    )
                    # Store the guidance dict for the next attempt's retry_attempts row.
                    previous_guidance = eval_result.retry_guidance
                    # retry_state.attempt was already incremented by apply_modifiers
                    continue

                # F02 path: increment retry_state manually
                retry_state = RetryState(node_id=node_id, attempt=retry_state.attempt + 1)
                previous_guidance = eval_result.retry_guidance

        # All nodes passed
        if self._event_bus is not None:
            await self._event_bus.publish(
                RunEvent(run_id=run_id, event_type="run_completed", payload={})
            )

        logger.info(
            "auto_loop_completed",
            run_id=run_id,
            nodes=len(order),
            total_cost_usd=round(float(result.total_cost), 6),
        )
        return result

    async def _save_attempt(
        self,
        *,
        run_id: str,
        node_id: str,
        ne_id: str,
        attempt_number: int,
        prompt_version_id: str | None,
        retry_guidance: dict[str, Any] | None,
        evaluation_id: str | None,
        cost_won: Decimal,
        started_at: datetime,
        finished_at: datetime | None,
    ) -> None:
        """Persist one RetryAttempt row via the repo."""
        attempt = RetryAttempt(
            id=new_ulid(),
            run_id=run_id,
            node_execution_id=ne_id,
            node_id=node_id,
            attempt_number=attempt_number,
            prompt_version_id_used=prompt_version_id,
            retry_guidance=retry_guidance,
            evaluation_id=evaluation_id,
            cost_won=cost_won,
            started_at=started_at,
            finished_at=finished_at,
        )
        await self._retry_repo.create(attempt)
