from __future__ import annotations

import pytest

from style_workbench.core.errors import DagValidationError
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType
from style_workbench.domain.style.validation import validate_dag


def _node(nid: str, template: str = "hello") -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="openai", model_id="gpt-4o"),
        prompt_template=template,
    )


def test_valid_dag_passes() -> None:
    dag = DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B")])
    validate_dag(dag)  # no exception


def test_cyclic_dag_raises() -> None:
    dag = DAG(nodes=[_node("A"), _node("B")], edges=[Edge("A", "B"), Edge("B", "A")])
    with pytest.raises(DagValidationError):
        validate_dag(dag)


def test_dangling_edge_raises() -> None:
    dag = DAG(nodes=[_node("A")], edges=[Edge("A", "GHOST")])
    with pytest.raises(DagValidationError):
        validate_dag(dag)


def test_undefined_variable_raises() -> None:
    dag = DAG(
        nodes=[_node("A", template="{username} hello")],
        edges=[],
        variables=[],  # username not declared
    )
    with pytest.raises(DagValidationError):
        validate_dag(dag)


def test_declared_variable_passes() -> None:
    dag = DAG(
        nodes=[_node("A", template="{username} hello")],
        edges=[],
        variables=["username"],
    )
    validate_dag(dag)  # no exception
