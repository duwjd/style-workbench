from __future__ import annotations

import pytest

from style_workbench.core.errors import DagValidationError
from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeType, VariableMapping
from style_workbench.domain.style.validation import validate_dag


def _node(
    nid: str,
    template: str = "hello",
    variable_mapping: dict[str, VariableMapping] | None = None,
) -> Node:
    return Node(
        id=nid,
        type=NodeType.TEXT_GENERATION,
        model=ModelRef(provider="openai", model_id="gpt-4o"),
        prompt_template=template,
        variable_mapping=variable_mapping or {},
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
        variables=[],  # username not declared anywhere
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


# ---------------------------------------------------------------------------
# variable_mapping: placeholder resolution
# ---------------------------------------------------------------------------


def test_placeholder_resolved_by_variable_mapping_user_input() -> None:
    """Placeholder only in variable_mapping (not in dag.variables) should pass."""
    vm = VariableMapping(source="user_input", role="name")
    dag = DAG(
        nodes=[_node("A", template="{username} hello", variable_mapping={"username": vm})],
        edges=[],
        variables=[],  # NOT in dag.variables — mapping alone is sufficient
    )
    validate_dag(dag)  # no exception


def test_placeholder_resolved_by_variable_mapping_node_output() -> None:
    """node_output mapping with a valid node_id should resolve the placeholder."""
    vm = VariableMapping(source="node_output", node_id="B")
    dag = DAG(
        nodes=[
            _node("B", template="source node"),
            _node("A", template="{result}", variable_mapping={"result": vm}),
        ],
        edges=[Edge("B", "A")],
        variables=[],
    )
    validate_dag(dag)  # no exception


def test_placeholder_resolved_by_variable_mapping_constant() -> None:
    """constant mapping should resolve the placeholder."""
    vm = VariableMapping(source="constant", value="gemgem")
    dag = DAG(
        nodes=[_node("A", template="Welcome to {brand}", variable_mapping={"brand": vm})],
        edges=[],
        variables=[],
    )
    validate_dag(dag)  # no exception


def test_placeholder_needs_neither_variable_nor_mapping_raises() -> None:
    """If placeholder is in neither dag.variables nor variable_mapping, must raise."""
    dag = DAG(
        nodes=[_node("A", template="{missing} text")],
        edges=[],
        variables=[],
    )
    with pytest.raises(DagValidationError, match="undefined variable"):
        validate_dag(dag)


# ---------------------------------------------------------------------------
# variable_mapping integrity: node_id existence
# ---------------------------------------------------------------------------


def test_variable_mapping_node_output_unknown_node_raises() -> None:
    vm = VariableMapping(source="node_output", node_id="GHOST")
    dag = DAG(
        nodes=[_node("A", template="{img}", variable_mapping={"img": vm})],
        edges=[],
        variables=[],
    )
    with pytest.raises(DagValidationError, match="unknown node_id"):
        validate_dag(dag)


def test_variable_mapping_node_output_known_node_passes() -> None:
    vm = VariableMapping(source="node_output", node_id="B")
    dag = DAG(
        nodes=[
            _node("B"),
            _node("A", template="{img}", variable_mapping={"img": vm}),
        ],
        edges=[Edge("B", "A")],
        variables=[],
    )
    validate_dag(dag)  # no exception


# ---------------------------------------------------------------------------
# variable_mapping integrity: user_input role
# ---------------------------------------------------------------------------


def test_variable_mapping_user_input_missing_role_raises() -> None:
    """VariableMapping domain object itself raises on construction — double-check."""
    with pytest.raises(ValueError, match="role"):
        VariableMapping(source="user_input", role=None)


# ---------------------------------------------------------------------------
# VariableMapping domain object construction guards
# ---------------------------------------------------------------------------


def test_variable_mapping_node_output_missing_node_id_raises() -> None:
    with pytest.raises(ValueError, match="node_id"):
        VariableMapping(source="node_output", node_id=None)


def test_variable_mapping_constant_missing_value_raises() -> None:
    with pytest.raises(ValueError, match="value"):
        VariableMapping(source="constant", value=None)
