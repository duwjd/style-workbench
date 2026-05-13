from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput
from style_workbench.adapters.registry import clear_registry, register
from style_workbench.core.errors import ConflictError, DagValidationError, RunNotFoundError
from style_workbench.domain.evaluation.entity import DimensionScore, EvaluationResult
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType
from style_workbench.infra.repositories.run_repo import RunRecord, RunRepository
from style_workbench.services.run_service import RunAbortedError, RunService


def _node(nid: str, template: str = "hello") -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="fake", model_id="fake-model"),
        prompt_template=template,
    )


def _fake_output(text: str = "ok", cost: float = 0.001) -> ModelOutput:
    return ModelOutput(text=text, input_tokens=10, output_tokens=5, cost_usd=cost)


class _FakeAdapter(ModelAdapter):
    def __init__(self, output: ModelOutput) -> None:
        self._output = output

    async def generate(self, input: ModelInput) -> ModelOutput:
        return self._output

    def cost_estimate(self, model_id: str, input: ModelInput) -> float:
        return self._output.cost_usd


@pytest.fixture(autouse=True)
def fake_registry() -> None:  # type: ignore[misc]
    clear_registry()
    register("fake", _FakeAdapter(_fake_output()))
    yield  # type: ignore[misc]
    clear_registry()


@pytest.mark.asyncio
async def test_run_linear_dag_returns_all_nodes() -> None:
    dag = DAG(
        nodes=[_node("A"), _node("B")],
        edges=[Edge("A", "B")],
        variables=[],
    )
    svc = RunService()
    result = await svc.run("style-1", dag, {})
    assert len(result.node_results) == 2
    assert result.node_results[0].node_id == "A"
    assert result.node_results[1].node_id == "B"


@pytest.mark.asyncio
async def test_run_accumulates_cost() -> None:
    register("fake", _FakeAdapter(_fake_output(cost=0.01)))
    dag = DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B")], variables=[])
    svc = RunService()
    result = await svc.run("style-1", dag, {})
    assert abs(result.total_cost_usd - 0.02) < 1e-9


@pytest.mark.asyncio
async def test_run_budget_exceeded_aborts() -> None:
    # Each node costs 1 USD = 1,400 won; budget = 1,000 won → aborts after node 1
    register("fake", _FakeAdapter(_fake_output(cost=1.0)))
    dag = DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B")], variables=[])
    svc = RunService(cost_budget_won=1_000.0)
    with pytest.raises(RunAbortedError, match="Budget exceeded"):
        await svc.run("style-1", dag, {})


@pytest.mark.asyncio
async def test_run_cyclic_dag_raises_validation_error() -> None:
    dag = DAG(
        nodes=[_node("A"), _node("B")],
        edges=[Edge("A", "B"), Edge("B", "A")],
        variables=[],
    )
    svc = RunService()
    with pytest.raises(DagValidationError):
        await svc.run("style-1", dag, {})


# ---------------------------------------------------------------------------
# abort() tests
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, 0, 0, 0)


def _make_run_record(status: str) -> RunRecord:
    return RunRecord(
        id="run-1",
        style_version_id="ver-1",
        style_id="style-1",
        status=status,
        total_cost=None,
        created_at=_NOW,
        started_at=_NOW,
        finished_at=None,
        node_executions=[],
    )


def _make_run_repo(record: RunRecord | None) -> RunRepository:
    repo = AsyncMock(spec=RunRepository)
    repo.get = AsyncMock(return_value=record)
    repo.abort_run = AsyncMock(return_value=None)
    return repo  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_abort_run_not_found_raises() -> None:
    repo = _make_run_repo(record=None)
    svc = RunService(run_repo=repo)
    with pytest.raises(RunNotFoundError):
        await svc.abort("ghost-run")


@pytest.mark.asyncio
async def test_abort_already_succeeded_raises_conflict() -> None:
    repo = _make_run_repo(_make_run_record("succeeded"))
    svc = RunService(run_repo=repo)
    with pytest.raises(ConflictError):
        await svc.abort("run-1")


@pytest.mark.asyncio
async def test_abort_already_failed_raises_conflict() -> None:
    repo = _make_run_repo(_make_run_record("failed"))
    svc = RunService(run_repo=repo)
    with pytest.raises(ConflictError):
        await svc.abort("run-1")


@pytest.mark.asyncio
async def test_abort_already_aborted_raises_conflict() -> None:
    repo = _make_run_repo(_make_run_record("aborted"))
    svc = RunService(run_repo=repo)
    with pytest.raises(ConflictError):
        await svc.abort("run-1")


@pytest.mark.asyncio
async def test_abort_running_calls_abort_repo() -> None:
    running_record = _make_run_record("running")
    aborted_record = _make_run_record("aborted")
    repo = _make_run_repo(running_record)
    # Second call to get() returns the refreshed aborted record
    repo.get = AsyncMock(side_effect=[running_record, aborted_record])  # type: ignore[attr-defined]

    svc = RunService(run_repo=repo)
    result = await svc.abort("run-1")

    repo.abort_run.assert_awaited_once()  # type: ignore[attr-defined]
    assert result.status == "aborted"


@pytest.mark.asyncio
async def test_run_substitutes_variables() -> None:
    captured: list[ModelInput] = []

    class _CapturingAdapter(ModelAdapter):
        async def generate(self, input: ModelInput) -> ModelOutput:
            captured.append(input)
            return _fake_output()

        def cost_estimate(self, model_id: str, input: ModelInput) -> float:
            return 0.0

    register("fake", _CapturingAdapter())
    dag = DAG(
        nodes=[_node("A", template="Hello {name}!")],
        edges=[],
        variables=["name"],
    )
    svc = RunService()
    await svc.run("style-1", dag, {"name": "World"})
    assert captured[0].prompt == "Hello World!"


# ---------------------------------------------------------------------------
# W1 — execute() budget guard (eval+retry branch)
# ---------------------------------------------------------------------------


def _make_eval_result(passed: bool) -> EvaluationResult:
    """Minimal EvaluationResult stub for the eval+retry branch."""
    score = 1.0 if passed else 0.0
    return EvaluationResult(
        id="eval-1",
        node_execution_id="ne-1",
        evaluator_model="stub",
        dimensions=[DimensionScore(name="quality", score=score, rationale="stub")],
        notable_issues=[],
        retry_guidance=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_run_record_running() -> RunRecord:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return RunRecord(
        id="run-x",
        style_version_id="ver-x",
        style_id="style-x",
        status="running",
        total_cost=None,
        created_at=now,
        started_at=now,
        finished_at=None,
        node_executions=[],
    )


@pytest.mark.asyncio
async def test_execute_budget_exceeded_aborts() -> None:
    """execute() eval+retry branch aborts when cumulative cost exceeds budget.

    Setup: two-node linear DAG (A → B); each node costs 0.8 USD = 1,120 ₩.
    Budget = 1,000 ₩. After node A the guard fires before the evaluator is
    called for node A, so RunAbortedError is raised and the run is marked failed.
    """
    dag = DAG(
        nodes=[_node("A"), _node("B")],
        edges=[Edge("A", "B")],
        variables=[],
    )
    # version_id → (style_id, dag)
    style_repo = AsyncMock()
    style_repo.get_version = AsyncMock(return_value=("style-x", dag))

    run_record = _make_run_record_running()
    run_repo = AsyncMock(spec=RunRepository)
    run_repo.create = AsyncMock(return_value=run_record)
    run_repo.update_status = AsyncMock(return_value=None)
    run_repo.get = AsyncMock(return_value=run_record)

    eval_service = AsyncMock()
    # The evaluator should NOT be called — budget guard fires first.
    eval_service.evaluate = AsyncMock(return_value=_make_eval_result(passed=True))

    # Each fake node costs 0.8 USD = 1,120 ₩ which exceeds the 1,000 ₩ budget.
    expensive_output = ModelOutput(text="ok", input_tokens=10, output_tokens=5, cost_usd=0.8)

    session = AsyncMock()

    with patch("style_workbench.engine.executor.DagExecutor") as MockExecutor:
        executor_instance = MockExecutor.return_value
        executor_instance.execute_node = AsyncMock(return_value=(expensive_output, "ne-1"))

        svc = RunService(
            cost_budget_won=1_000.0,
            style_repo=style_repo,
            run_repo=run_repo,
            session=session,
            eval_service=eval_service,
        )

        with pytest.raises(RunAbortedError, match="Budget exceeded"):
            await svc.execute("ver-x", {})

    # The run must have been marked failed
    run_repo.update_status.assert_awaited()
    call_args_list = run_repo.update_status.call_args_list
    statuses = [c.args[1] if c.args else c.kwargs.get("status") for c in call_args_list]
    assert "failed" in statuses, f"Expected 'failed' in update_status calls, got: {statuses}"

    # The run should have a finished_at set (passed via keyword or positional)
    failed_call = next(
        c for c in call_args_list if ((c.args[1] if c.args else c.kwargs.get("status")) == "failed")
    )
    finished = failed_call.kwargs.get("finished_at") or (
        failed_call.args[2] if len(failed_call.args) > 2 else None
    )
    assert finished is not None, "finished_at must be set when run is marked failed"

    # Evaluator must NOT have been called (budget fired before eval round-trip)
    eval_service.evaluate.assert_not_awaited()
