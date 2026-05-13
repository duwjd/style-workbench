"""Shared fixtures for the auto_loop golden test suite.

All external dependencies (DagExecutor, EvaluationService, RetryAttemptRepo,
RunEventBus) are replaced by lightweight mocks.  Zero real LLM calls occur.

Mock contract:
  - MockExecutor.execute_node() always succeeds.  It increments an internal
    call counter and returns a ModelOutput with the scenario's cost.
  - MockEvaluationService.evaluate() checks the current attempt_number for
    the given node and returns PASS when attempt_number == pass_at_attempt,
    otherwise FAIL with the scenario's failed_dimensions.
  - MockRetryAttemptRepo.create() accumulates RetryAttempt records in memory
    so that tests can inspect them.
  - MockRunEventBus captures all RunEvent objects emitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from style_workbench.adapters.base import ModelOutput
from style_workbench.core.ids import new_ulid
from style_workbench.domain.auto_loop.entity import RetryAttempt, RetryAttemptWithEval
from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.engine.run_events import RunEvent
from tests.golden.auto_loop.scenarios import GoldenScenario

# ---------------------------------------------------------------------------
# MockExecutor
# ---------------------------------------------------------------------------


class MockExecutor:
    """Simulates DagExecutor.execute_node() without DB or model calls.

    Tracks per-node call counts so MockEvaluationService can determine the
    current attempt_number independently.
    """

    def __init__(self, scenario: GoldenScenario) -> None:
        self._scenario = scenario
        # node_id -> number of times execute_node has been called
        self._call_counts: dict[str, int] = {}

    async def execute_node(
        self,
        node: Any,
        prompt: str,
        run_id: str,
        upstream_outputs: dict[str, ModelOutput] | None = None,
    ) -> tuple[ModelOutput, str]:
        node_id: str = node.id
        current_count = self._call_counts.get(node_id, 0)
        self._call_counts[node_id] = current_count + 1

        output = ModelOutput(
            text=f"mock output attempt {current_count}",
            input_tokens=10,
            output_tokens=5,
            cost_usd=self._scenario.cost_per_attempt / 1_400.0,  # convert ₩ back to USD
            artifact_url=None,
        )
        return output, new_ulid()


# ---------------------------------------------------------------------------
# MockEvaluationService
# ---------------------------------------------------------------------------


def _make_eval_result(passed: bool, failed_dims: list[str]) -> EvaluationResult:
    """Build a minimal EvaluationResult with the given pass/fail state."""
    # All scored dimensions: for simplicity, fabricate one score per failed_dim
    # plus one passing dimension.
    dims: list[DimensionScore] = []
    for dim in failed_dims:
        dims.append(DimensionScore(name=dim, score=0.4, rationale="mock fail"))
    # Always include at least one dimension; add a passing one if none failing.
    if not failed_dims:
        dims.append(DimensionScore(name="quality", score=1.0, rationale="mock pass"))

    retry_guidance: dict[str, Any] | None = (
        None if passed else {"instruction": f"Fix {', '.join(failed_dims)}"}
    )

    return EvaluationResult(
        id=new_ulid(),
        node_execution_id=new_ulid(),
        evaluator_model="mock-evaluator",
        dimensions=dims,
        notable_issues=[],
        retry_guidance=retry_guidance,
        created_at=datetime.now(UTC),
    )


class MockEvaluationService:
    """Deterministic evaluator driven by GoldenScenario.pass_at_attempt.

    The mock returns PASS exactly when the call count for the given
    node_execution_id matches pass_at_attempt.  Tracks how many times
    evaluate() has been called to simulate attempt_number progression.
    """

    def __init__(self, scenario: GoldenScenario) -> None:
        self._scenario = scenario
        # ne_id -> call count (each ne_id is unique per attempt in auto_loop)
        self._eval_count: int = 0

    async def evaluate(
        self,
        node_execution_id: str,
        brief_summary: str = "",
    ) -> EvaluationResult:
        attempt_number = self._eval_count
        self._eval_count += 1

        passed = self._scenario.pass_at_attempt == attempt_number
        failed_dims = [] if passed else list(self._scenario.failed_dimensions)
        return _make_eval_result(passed=passed, failed_dims=failed_dims)


# ---------------------------------------------------------------------------
# MockRetryAttemptRepo
# ---------------------------------------------------------------------------


class MockRetryAttemptRepo:
    """In-memory RetryAttemptRepo for assertion in tests."""

    def __init__(self) -> None:
        self.attempts: list[RetryAttempt] = []

    async def create(self, retry_attempt: RetryAttempt) -> RetryAttempt:
        self.attempts.append(retry_attempt)
        return retry_attempt

    async def list_by_run(self, run_id: str) -> list[RetryAttempt]:
        return [a for a in self.attempts if a.run_id == run_id]

    async def list_by_node_execution(self, node_execution_id: str) -> list[RetryAttempt]:
        return [a for a in self.attempts if a.node_execution_id == node_execution_id]

    async def list_with_evaluations(self, run_id: str) -> list[RetryAttemptWithEval]:
        return []  # not needed for golden tests


# ---------------------------------------------------------------------------
# MockRunEventBus
# ---------------------------------------------------------------------------


@dataclass
class MockRunEventBus:
    """Captures emitted RunEvents without any real transport."""

    events: list[RunEvent] = field(default_factory=list)
    # Tracks whether close_run was called per run_id
    _closed: dict[str, bool] = field(default_factory=dict)

    async def publish(self, event: RunEvent) -> None:
        self.events.append(event)

    async def close_run(self, run_id: str) -> None:
        # Idempotent (FR-10) — calling twice is safe
        self._closed[run_id] = True

    def events_of_type(self, event_type: str) -> list[RunEvent]:
        return [e for e in self.events if e.event_type == event_type]
