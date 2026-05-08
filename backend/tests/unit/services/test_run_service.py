from __future__ import annotations

import pytest

from style_workbench.adapters.base import ModelAdapter, ModelInput, ModelOutput
from style_workbench.adapters.registry import clear_registry, register
from style_workbench.core.errors import DagValidationError
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType
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
