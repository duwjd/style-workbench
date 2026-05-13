"""Unit tests for AutoLoopOrchestrator (F01 §10.1 / §10.5).

All external dependencies (executor, eval_service, retry_repo) are mocked.
No DB access.

Test cases:
  test_auto_loop_pass_first_attempt         — attempt 0 PASS, 1 row saved
  test_auto_loop_pass_after_retry           — attempt 0 FAIL, attempt 1 PASS, 2 rows
  test_auto_loop_max_retry_exceeded         — all attempts FAIL → RunAbortedError, 4 rows
  test_auto_loop_budget_exceeded_before_evaluator — budget guard fires before eval
  test_auto_loop_noop_modifier_keeps_same_prompt_version_id
  test_event_bus_close_run_idempotent       — FR-10 invariant
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.errors import RunAbortedError
from style_workbench.domain.auto_loop.entity import RetryAttempt
from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.domain.prompt.modifier import NoopPromptModifier
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType
from style_workbench.engine.auto_loop import AutoLoopOrchestrator
from style_workbench.engine.run_events import RunEventBus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(nid: str) -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="fake", model_id="fake-model"),
        prompt_template="test prompt",
    )


def _fake_output(cost_usd: float = 0.001) -> ModelOutput:
    return ModelOutput(text="ok", input_tokens=5, output_tokens=5, cost_usd=cost_usd)


def _eval_result(passed: bool, guidance: dict[str, object] | None = None) -> EvaluationResult:
    score = 1.0 if passed else 0.0
    return EvaluationResult(
        id=f"eval-{passed}-{id(object())}",
        node_execution_id="ne-stub",
        evaluator_model="stub",
        dimensions=[DimensionScore(name="quality", score=score, rationale="stub")],
        notable_issues=[],
        retry_guidance=guidance,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@dataclass
class _FakeRetryRepo:
    """In-memory RetryAttemptRepo stub."""

    saved: list[RetryAttempt] = field(default_factory=list)

    async def create(self, retry_attempt: RetryAttempt) -> RetryAttempt:
        self.saved.append(retry_attempt)
        return retry_attempt

    async def list_by_run(self, run_id: str) -> list[RetryAttempt]:
        return [r for r in self.saved if r.run_id == run_id]

    async def list_by_node_execution(self, node_execution_id: str) -> list[RetryAttempt]:
        return [r for r in self.saved if r.node_execution_id == node_execution_id]


def _make_executor(output: ModelOutput, ne_id: str = "ne-1") -> MagicMock:
    """Return a mock DagExecutor whose execute_node always returns (output, ne_id)."""
    executor = MagicMock()
    executor.execute_node = AsyncMock(return_value=(output, ne_id))
    return executor


def _make_eval_service(*results: EvaluationResult) -> MagicMock:
    """Return a mock EvaluationService with queued evaluate() return values."""
    svc = MagicMock()
    svc.evaluate = AsyncMock(side_effect=list(results))
    return svc


def _make_orchestrator(
    executor: MagicMock,
    eval_service: MagicMock,
    retry_repo: _FakeRetryRepo,
    *,
    max_retry: int = 3,
    budget_won: float = 100_000.0,
    event_bus: RunEventBus | None = None,
) -> AutoLoopOrchestrator:
    return AutoLoopOrchestrator(
        executor=executor,
        eval_service=eval_service,
        retry_repo=retry_repo,  # type: ignore[arg-type]
        prompt_modifier=NoopPromptModifier(),
        max_retry=max_retry,
        cost_budget_won=budget_won,
        event_bus=event_bus,
    )


_SINGLE_NODE_DAG = DAG(nodes=[_node("A")], edges=[], variables=[])
_TWO_NODE_DAG = DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B")], variables=[])

# ---------------------------------------------------------------------------
# Test: first attempt PASS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_pass_first_attempt() -> None:
    """Single node PASS on attempt 0 → 1 RetryAttempt row, attempt_number=0."""
    output = _fake_output()
    executor = _make_executor(output)
    eval_svc = _make_eval_service(_eval_result(passed=True))
    repo = _FakeRetryRepo()

    orch = _make_orchestrator(executor, eval_svc, repo)
    result = await orch.run(_SINGLE_NODE_DAG, {}, "run-1")

    assert result.outputs["A"] is output
    assert result.attempts_per_node["A"] == 1  # 1 attempt = attempt_number 0

    assert len(repo.saved) == 1
    saved = repo.saved[0]
    assert saved.attempt_number == 0
    assert saved.retry_guidance is None  # first attempt → no guidance
    assert saved.evaluation_id is not None
    assert saved.run_id == "run-1"


# ---------------------------------------------------------------------------
# Test: FAIL then PASS (retry once)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_pass_after_retry() -> None:
    """Node FAIL on attempt 0, PASS on attempt 1 → 2 RetryAttempt rows."""
    output = _fake_output()
    executor = _make_executor(output)
    eval_svc = _make_eval_service(
        _eval_result(passed=False, guidance={"instruction": "fix composition"}),
        _eval_result(passed=True),
    )
    repo = _FakeRetryRepo()

    orch = _make_orchestrator(executor, eval_svc, repo)
    result = await orch.run(_SINGLE_NODE_DAG, {}, "run-2")

    assert result.attempts_per_node["A"] == 2

    assert len(repo.saved) == 2
    attempt_0 = repo.saved[0]
    attempt_1 = repo.saved[1]

    assert attempt_0.attempt_number == 0
    assert attempt_0.retry_guidance is None  # first attempt has no prior guidance

    assert attempt_1.attempt_number == 1
    # attempt 1 retry_guidance comes from the eval of attempt 0 — must be dict
    assert attempt_1.retry_guidance is not None
    assert isinstance(attempt_1.retry_guidance, dict)
    assert "instruction" in attempt_1.retry_guidance


# ---------------------------------------------------------------------------
# Test: max_retry exceeded → RunAbortedError + 4 rows (attempts 0,1,2,3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_max_retry_exceeded() -> None:
    """All attempts FAIL with max_retry=3 → RunAbortedError, 4 rows."""
    output = _fake_output()
    executor = _make_executor(output)
    # 4 FAILs: attempt 0 + retry 1 + retry 2 + retry 3 (abort)
    eval_svc = _make_eval_service(
        _eval_result(passed=False, guidance={"instruction": "g1"}),
        _eval_result(passed=False, guidance={"instruction": "g2"}),
        _eval_result(passed=False, guidance={"instruction": "g3"}),
        _eval_result(passed=False, guidance={"instruction": "g4"}),
    )
    repo = _FakeRetryRepo()

    orch = _make_orchestrator(executor, eval_svc, repo, max_retry=3)

    with pytest.raises(RunAbortedError):
        await orch.run(_SINGLE_NODE_DAG, {}, "run-3")

    # 4 attempts (0, 1, 2, 3)
    assert len(repo.saved) == 4
    assert [r.attempt_number for r in repo.saved] == [0, 1, 2, 3]
    # all rows have evaluation_id (budget guard did not fire)
    assert all(r.evaluation_id is not None for r in repo.saved)


# ---------------------------------------------------------------------------
# Test: budget guard fires BEFORE evaluator — W1 regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_budget_exceeded_before_evaluator() -> None:
    """Budget guard fires before the evaluator is called.

    Setup: 1 node, cost = 0.8 USD = 1,120 ₩, budget = 1,000 ₩.
    The guard must fire before eval_service.evaluate() is awaited.
    """
    expensive_output = _fake_output(cost_usd=0.8)  # 0.8 * 1400 = 1120 ₩
    executor = _make_executor(expensive_output)
    eval_svc = _make_eval_service()  # no results queued — should not be called
    repo = _FakeRetryRepo()

    orch = _make_orchestrator(executor, eval_svc, repo, budget_won=1_000.0)

    with pytest.raises(RunAbortedError, match="Budget exceeded"):
        await orch.run(_SINGLE_NODE_DAG, {}, "run-4")

    # Evaluator must NOT have been called
    eval_svc.evaluate.assert_not_awaited()

    # One row is still saved (with evaluation_id=None, budget fired first)
    assert len(repo.saved) == 1
    assert repo.saved[0].evaluation_id is None


# ---------------------------------------------------------------------------
# Test: NoopPromptModifier keeps the same prompt_version_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_loop_noop_modifier_keeps_same_prompt_version_id() -> None:
    """NoopPromptModifier must not change prompt_version_id across retries.

    The retry_attempt rows for attempt 0 and attempt 1 must both have
    prompt_version_id_used == None (inline-prompt nodes have no version id).
    """
    output = _fake_output()
    executor = _make_executor(output)
    eval_svc = _make_eval_service(
        _eval_result(passed=False, guidance={"instruction": "fix it"}),
        _eval_result(passed=True),
    )
    repo = _FakeRetryRepo()

    orch = _make_orchestrator(executor, eval_svc, repo)
    await orch.run(_SINGLE_NODE_DAG, {}, "run-5")

    assert len(repo.saved) == 2
    # Both attempts must have the same (None) prompt_version_id_used
    assert repo.saved[0].prompt_version_id_used is None
    assert repo.saved[1].prompt_version_id_used is None


# ---------------------------------------------------------------------------
# Test: node_retry SSE event published on FAIL → retry (단계 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_node_retry_event_published() -> None:
    """FAIL on attempt 0 → node_retry event published with attempt_number=1.

    Validates spec §6.3 node_retry payload:
      run_id, node_id, attempt_number (next), retry_guidance, failed_dimensions.
    """
    output = _fake_output()
    executor = _make_executor(output)
    # attempt 0 FAIL, attempt 1 PASS
    eval_svc = _make_eval_service(
        _eval_result(
            passed=False,
            guidance={"instruction": "fix lighting", "confidence": 0.82},
        ),
        _eval_result(passed=True),
    )
    repo = _FakeRetryRepo()
    bus = RunEventBus()
    published: list[object] = []

    # Subscribe before the run to capture all events
    import asyncio

    async def _collect() -> None:
        async for event in bus.subscribe("run-retry-evt"):
            published.append(event)

    collect_task = asyncio.create_task(_collect())
    await asyncio.sleep(0)  # yield so subscriber is registered

    orch = _make_orchestrator(executor, eval_svc, repo, event_bus=bus)
    await orch.run(_SINGLE_NODE_DAG, {}, "run-retry-evt")

    # Close bus so subscriber task can finish
    bus.close_run("run-retry-evt")
    await asyncio.wait_for(collect_task, timeout=2.0)

    # Filter node_retry events
    from style_workbench.engine.run_events import RunEvent

    node_retry_events = [
        e for e in published if isinstance(e, RunEvent) and e.event_type == "node_retry"
    ]
    assert len(node_retry_events) == 1, f"Expected 1 node_retry event, got {len(node_retry_events)}"

    evt = node_retry_events[0]
    assert evt.run_id == "run-retry-evt"
    assert evt.payload["node_id"] == "A"
    assert evt.payload["attempt_number"] == 1  # next attempt = 0+1
    guidance = evt.payload["retry_guidance"]
    assert isinstance(guidance, dict)
    assert guidance.get("instruction") == "fix lighting"
    failed_dims = evt.payload["failed_dimensions"]
    assert isinstance(failed_dims, list)


# ---------------------------------------------------------------------------
# Test: run_budget_exceeded SSE event published when budget guard triggers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_budget_exceeded_event_published() -> None:
    """Budget guard triggers → run_budget_exceeded event published before RunAbortedError.

    Validates spec §6.3 run_budget_exceeded payload:
      run_id, node_id, total_cost_won, budget_won.
    """
    expensive_output = _fake_output(cost_usd=0.8)  # 0.8 * 1400 = 1120 ₩
    executor = _make_executor(expensive_output)
    eval_svc = _make_eval_service()  # evaluator must NOT be called
    repo = _FakeRetryRepo()
    bus = RunEventBus()
    published: list[object] = []

    import asyncio

    async def _collect() -> None:
        async for event in bus.subscribe("run-budget-evt"):
            published.append(event)

    collect_task = asyncio.create_task(_collect())
    await asyncio.sleep(0)

    orch = _make_orchestrator(executor, eval_svc, repo, budget_won=1_000.0, event_bus=bus)

    with pytest.raises(RunAbortedError, match="Budget exceeded"):
        await orch.run(_SINGLE_NODE_DAG, {}, "run-budget-evt")

    bus.close_run("run-budget-evt")
    await asyncio.wait_for(collect_task, timeout=2.0)

    from style_workbench.engine.run_events import RunEvent

    budget_events = [
        e for e in published if isinstance(e, RunEvent) and e.event_type == "run_budget_exceeded"
    ]
    assert len(budget_events) == 1, f"Expected 1 run_budget_exceeded, got {len(budget_events)}"

    evt = budget_events[0]
    assert evt.run_id == "run-budget-evt"
    assert evt.payload["node_id"] == "A"
    total_cost_won = evt.payload["total_cost_won"]
    budget_won = evt.payload["budget_won"]
    assert isinstance(total_cost_won, float)
    assert isinstance(budget_won, float)
    assert total_cost_won > budget_won


# ---------------------------------------------------------------------------
# Test: run_failed NOT published by AutoLoopOrchestrator (단계 2 결정)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_failed_not_published_by_orchestrator() -> None:
    """AutoLoopOrchestrator must NOT emit run_failed on max_retry exceeded.

    run_failed is RunService.execute()'s responsibility (service layer).
    This invariant prevents double-publishing (spec §단계 3 §2).
    """
    output = _fake_output()
    executor = _make_executor(output)
    # 4 FAILs → max_retry=3 exhausted
    eval_svc = _make_eval_service(
        _eval_result(passed=False, guidance={"instruction": "g1"}),
        _eval_result(passed=False, guidance={"instruction": "g2"}),
        _eval_result(passed=False, guidance={"instruction": "g3"}),
        _eval_result(passed=False, guidance={"instruction": "g4"}),
    )
    repo = _FakeRetryRepo()
    bus = RunEventBus()
    published: list[object] = []

    import asyncio

    async def _collect() -> None:
        async for event in bus.subscribe("run-no-failed-evt"):
            published.append(event)

    collect_task = asyncio.create_task(_collect())
    await asyncio.sleep(0)

    orch = _make_orchestrator(executor, eval_svc, repo, max_retry=3, event_bus=bus)

    with pytest.raises(RunAbortedError):
        await orch.run(_SINGLE_NODE_DAG, {}, "run-no-failed-evt")

    bus.close_run("run-no-failed-evt")
    await asyncio.wait_for(collect_task, timeout=2.0)

    from style_workbench.engine.run_events import RunEvent

    run_failed_events = [
        e for e in published if isinstance(e, RunEvent) and e.event_type == "run_failed"
    ]
    assert len(run_failed_events) == 0, (
        f"AutoLoopOrchestrator must NOT publish run_failed; got {len(run_failed_events)} events"
    )


# ---------------------------------------------------------------------------
# Test: FR-10 — close_run idempotency invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_bus_close_run_idempotent() -> None:
    """RunEventBus.close_run() called twice must not raise any exception.

    This guards FR-10: RunService.execute()'s finally block and the
    except RunAbortedError block can both call close_run().
    """
    bus = RunEventBus()

    # Calling close_run on a run with no subscribers must be safe
    bus.close_run("run-ghost")
    bus.close_run("run-ghost")  # second call — must not raise

    # Calling close_run after subscriber has already received sentinel
    import asyncio

    async def _consumer() -> None:
        async for _ in bus.subscribe("run-x"):
            pass

    task = asyncio.create_task(_consumer())
    await asyncio.sleep(0)

    bus.close_run("run-x")
    await asyncio.wait_for(task, timeout=2.0)

    # Second call after the subscriber has already exited
    bus.close_run("run-x")  # must not raise
