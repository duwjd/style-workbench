"""AC-1 golden test — retry_attempt 1~3 안에 PASS 비율 ≥60%.

Spec reference: F01_auto_evaluation_loop.md §9 AC-1, §10.3 Golden Test Plan.

Measurement scope:
  - 50 pre-defined GoldenScenario fixtures.
  - Mock evaluator returns PASS/FAIL deterministically per scenario.
  - AutoLoopOrchestrator is invoked for real — retry orchestration,
    attempt counter, NoopPromptModifier integration, RetryAttempt repo
    writes, and SSE event emission are all exercised.
  - Zero real LLM calls.

Pass-rate formula:
  pass_within_3_retries / total_scenarios ≥ 0.60

A scenario "passes within 3 retries" when pass_at_attempt ∈ {0, 1, 2, 3}.
pass_at_attempt == None means all 4 attempts (0,1,2,3) FAIL → abort.
"""

from __future__ import annotations

import contextlib

import pytest

from style_workbench.core.errors import RunAbortedError
from style_workbench.core.ids import new_ulid
from style_workbench.domain.prompt.modifier import NoopPromptModifier
from style_workbench.domain.style.entity import DAG, ModelRef, Node, NodeType
from style_workbench.engine.auto_loop import AutoLoopOrchestrator
from tests.golden.auto_loop.conftest import (
    MockEvaluationService,
    MockExecutor,
    MockRetryAttemptRepo,
    MockRunEventBus,
)
from tests.golden.auto_loop.scenarios import GOLDEN_SCENARIOS, GoldenScenario

# ---------------------------------------------------------------------------
# Node-type mapping: scenario string → domain NodeType
# ---------------------------------------------------------------------------

_NODE_TYPE_MAP: dict[str, NodeType] = {
    "text": NodeType.TEXT_GENERATION,
    "image": NodeType.IMAGE_GENERATION,
    "video": NodeType.VIDEO_GENERATION,
    "composition": NodeType.COMPOSITION,
}

# Per-node-type model references (dummy — mock executor ignores them).
_MODEL_REF: dict[str, ModelRef] = {
    "text": ModelRef(provider="mock", model_id="mock-text"),
    "image": ModelRef(provider="mock", model_id="mock-image"),
    "video": ModelRef(provider="mock", model_id="mock-video"),
    "composition": ModelRef(provider="mock", model_id="mock-composition"),
}


def _build_single_node_dag(scenario: GoldenScenario) -> tuple[DAG, Node]:
    """Return a one-node DAG and the node for the given scenario."""
    node_id = f"node_{scenario.name}"
    node = Node(
        id=node_id,
        type=_NODE_TYPE_MAP[scenario.node_type],
        model=_MODEL_REF[scenario.node_type],
        prompt_template="Mock prompt for {run_id}",
    )
    dag = DAG(nodes=[node], edges=[], variables=["run_id"])
    return dag, node


async def _run_scenario(scenario: GoldenScenario) -> bool:
    """Execute AutoLoopOrchestrator for one scenario.

    Returns True if the loop completed without RunAbortedError
    (i.e., the node passed within max_retry attempts).
    """
    dag, _node = _build_single_node_dag(scenario)
    run_id = new_ulid()

    mock_executor = MockExecutor(scenario)
    mock_eval_svc = MockEvaluationService(scenario)
    mock_repo = MockRetryAttemptRepo()
    mock_event_bus = MockRunEventBus()

    orchestrator = AutoLoopOrchestrator(
        executor=mock_executor,  # type: ignore[arg-type]
        eval_service=mock_eval_svc,  # type: ignore[arg-type]
        retry_repo=mock_repo,
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        # Use a very large budget so cost never triggers abort in these tests.
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    try:
        await orchestrator.run(
            dag=dag,
            user_input={"run_id": run_id},
            run_id=run_id,
            brief_summary="Golden test brief",
        )
        return True
    except RunAbortedError:
        return False


# ---------------------------------------------------------------------------
# AC-1: pass-rate measurement
# ---------------------------------------------------------------------------


@pytest.mark.golden
async def test_auto_loop_pass_rate_meets_w4_threshold() -> None:
    """AC-1: PASS rate within 3 retries must be ≥60% across 50 golden scenarios.

    Spec: F01_auto_evaluation_loop.md §9 AC-1, §2.1 Goals.
    Marker: @pytest.mark.golden — run with `pytest -m golden`.
    """
    scenarios = GOLDEN_SCENARIOS
    assert len(scenarios) == 50, f"Expected 50 scenarios, got {len(scenarios)}"

    pass_count = 0
    results: list[tuple[str, bool]] = []

    for scenario in scenarios:
        passed = await _run_scenario(scenario)
        results.append((scenario.name, passed))
        if passed:
            pass_count += 1

    pass_rate = pass_count / len(scenarios)

    # Emit a breakdown for debugging if the assertion fails.
    failed_scenarios = [name for name, ok in results if not ok]
    passed_scenarios = [name for name, ok in results if ok]

    assert pass_rate >= 0.60, (
        f"AC-1 FAIL: pass rate {pass_rate:.1%} < 60%\n"
        f"  Passed ({len(passed_scenarios)}): {passed_scenarios}\n"
        f"  Failed ({len(failed_scenarios)}): {failed_scenarios}"
    )


# ---------------------------------------------------------------------------
# Per-scenario parametrised test: verify orchestration mechanics
# ---------------------------------------------------------------------------


@pytest.mark.golden
@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS, ids=lambda s: s.name)
async def test_scenario_attempt_count_correct(scenario: GoldenScenario) -> None:
    """For each scenario, verify that the number of retry_attempts rows
    persisted equals the expected attempt count.

    expected_attempts:
      pass_at_attempt == 0    → 1 row  (attempt 0 succeeds)
      pass_at_attempt == 1    → 2 rows (attempt 0 fails, attempt 1 passes)
      pass_at_attempt == 2    → 3 rows
      pass_at_attempt == 3    → 4 rows
      pass_at_attempt == None → 4 rows (attempts 0,1,2,3 all fail → abort)
    """
    dag, _node = _build_single_node_dag(scenario)
    run_id = new_ulid()

    mock_executor = MockExecutor(scenario)
    mock_eval_svc = MockEvaluationService(scenario)
    mock_repo = MockRetryAttemptRepo()
    mock_event_bus = MockRunEventBus()

    orchestrator = AutoLoopOrchestrator(
        executor=mock_executor,  # type: ignore[arg-type]
        eval_service=mock_eval_svc,  # type: ignore[arg-type]
        retry_repo=mock_repo,
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    with contextlib.suppress(RunAbortedError):
        await orchestrator.run(
            dag=dag,
            user_input={"run_id": run_id},
            run_id=run_id,
        )

    # Determine expected attempt count
    # pass_at_attempt == None → 4 rows (all fail); N → N+1 rows (0 through N)
    expected_attempts = 4 if scenario.pass_at_attempt is None else scenario.pass_at_attempt + 1

    actual_attempts = len(mock_repo.attempts)
    assert actual_attempts == expected_attempts, (
        f"Scenario '{scenario.name}': expected {expected_attempts} attempt rows, "
        f"got {actual_attempts}"
    )


@pytest.mark.golden
@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS, ids=lambda s: s.name)
async def test_scenario_node_retry_events_emitted(scenario: GoldenScenario) -> None:
    """For each scenario that has retries, verify node_retry SSE events are emitted
    exactly (expected_retries) times.

    expected_retries:
      pass_at_attempt == 0    → 0 node_retry events
      pass_at_attempt == 1    → 1 node_retry event  (after attempt 0 fails)
      pass_at_attempt == 2    → 2 node_retry events
      pass_at_attempt == 3    → 3 node_retry events
      pass_at_attempt == None → 3 node_retry events (after attempts 0,1,2 fail)
                                  (attempt 3 → abort, no further retry event)
    """
    dag, _node = _build_single_node_dag(scenario)
    run_id = new_ulid()

    mock_executor = MockExecutor(scenario)
    mock_eval_svc = MockEvaluationService(scenario)
    mock_repo = MockRetryAttemptRepo()
    mock_event_bus = MockRunEventBus()

    orchestrator = AutoLoopOrchestrator(
        executor=mock_executor,  # type: ignore[arg-type]
        eval_service=mock_eval_svc,  # type: ignore[arg-type]
        retry_repo=mock_repo,
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    with contextlib.suppress(RunAbortedError):
        await orchestrator.run(
            dag=dag,
            user_input={"run_id": run_id},
            run_id=run_id,
        )

    retry_events = mock_event_bus.events_of_type("node_retry")

    if scenario.pass_at_attempt == 0:
        expected_retries = 0
    elif scenario.pass_at_attempt is None:
        # Retries are emitted before each re-attempt; after attempt 2 fails
        # a retry event is emitted before attempt 3 starts; after attempt 3
        # fails the loop aborts without emitting another retry.
        expected_retries = 3
    else:
        expected_retries = scenario.pass_at_attempt

    assert len(retry_events) == expected_retries, (
        f"Scenario '{scenario.name}': expected {expected_retries} node_retry events, "
        f"got {len(retry_events)}"
    )


@pytest.mark.golden
async def test_run_completed_event_emitted_on_pass() -> None:
    """run_completed SSE event is emitted when all nodes pass."""
    # Use the simplest pass-at-attempt-0 scenario
    scenario = next(s for s in GOLDEN_SCENARIOS if s.pass_at_attempt == 0)
    dag, _node = _build_single_node_dag(scenario)
    run_id = new_ulid()

    mock_event_bus = MockRunEventBus()
    orchestrator = AutoLoopOrchestrator(
        executor=MockExecutor(scenario),  # type: ignore[arg-type]
        eval_service=MockEvaluationService(scenario),  # type: ignore[arg-type]
        retry_repo=MockRetryAttemptRepo(),
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        cost_budget_won=1_000_000_000.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    await orchestrator.run(dag=dag, user_input={"run_id": run_id}, run_id=run_id)

    completed_events = mock_event_bus.events_of_type("run_completed")
    assert len(completed_events) == 1


@pytest.mark.golden
async def test_budget_guard_aborts_before_evaluator() -> None:
    """Budget guard fires before evaluator when cumulative cost exceeds limit."""
    # Use a scenario with moderate per-attempt cost (image: ₩200 per attempt)
    scenario = next(s for s in GOLDEN_SCENARIOS if s.node_type == "image")
    dag, _node = _build_single_node_dag(scenario)
    run_id = new_ulid()

    mock_eval_svc = MockEvaluationService(scenario)
    mock_event_bus = MockRunEventBus()

    orchestrator = AutoLoopOrchestrator(
        executor=MockExecutor(scenario),  # type: ignore[arg-type]
        eval_service=mock_eval_svc,  # type: ignore[arg-type]
        retry_repo=MockRetryAttemptRepo(),
        prompt_modifier=NoopPromptModifier(),
        max_retry=3,
        # Budget is 1 ₩ — any execution exceeds it immediately
        cost_budget_won=1.0,
        event_bus=mock_event_bus,  # type: ignore[arg-type]
    )

    with pytest.raises(RunAbortedError, match="Budget exceeded"):
        await orchestrator.run(dag=dag, user_input={"run_id": run_id}, run_id=run_id)

    # Evaluator must NOT have been called (budget guard fires first)
    assert mock_eval_svc._eval_count == 0, (
        "Evaluator was called but budget guard should have fired before it"
    )

    # run_budget_exceeded event must have been emitted
    budget_events = mock_event_bus.events_of_type("run_budget_exceeded")
    assert len(budget_events) == 1
