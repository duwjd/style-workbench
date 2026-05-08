from __future__ import annotations

import pytest

from style_workbench.core.errors import DagCycleError
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType


def _node(nid: str) -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="openai", model_id="gpt-4o"),
        prompt_template="test",
    )


def test_acyclic_dag_topological_sort() -> None:
    # A → B → C
    dag = DAG(
        nodes=[_node("A"), _node("B"), _node("C")],
        edges=[Edge("A", "B"), Edge("B", "C")],
    )
    order = topological_sort(dag)
    assert order.index("A") < order.index("B") < order.index("C")


def test_cyclic_dag_raises_error() -> None:
    # A → B → A
    dag = DAG(
        nodes=[_node("A"), _node("B")],
        edges=[Edge("A", "B"), Edge("B", "A")],
    )
    with pytest.raises(DagCycleError):
        topological_sort(dag)


def test_empty_dag() -> None:
    dag = DAG(nodes=[], edges=[])
    assert topological_sort(dag) == []


def test_single_node() -> None:
    dag = DAG(nodes=[_node("X")], edges=[])
    assert topological_sort(dag) == ["X"]
