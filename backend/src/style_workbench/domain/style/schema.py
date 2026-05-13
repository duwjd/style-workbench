from __future__ import annotations

from typing import TYPE_CHECKING, Any

from style_workbench.domain.style.entity import (
    DAG,
    Edge,
    ModelRef,
    Node,
    NodeInput,
    NodeType,
    VariableMapping,
)

if TYPE_CHECKING:
    from style_workbench.domain.style.entity import Style


def node_input_from_dict(d: dict[str, Any]) -> NodeInput:
    return NodeInput(source=str(d["source"]), role=str(d["role"]))


def variable_mapping_from_dict(d: dict[str, Any]) -> VariableMapping:
    return VariableMapping(
        source=d["source"],
        role=d.get("role"),
        node_id=d.get("node_id"),
        value=d.get("value"),
    )


def node_from_dict(d: dict[str, Any]) -> Node:
    raw_mapping: dict[str, Any] = d.get("variable_mapping") or {}
    variable_mapping: dict[str, VariableMapping] = {
        k: variable_mapping_from_dict(v) for k, v in raw_mapping.items()
    }
    return Node(
        id=str(d["id"]),
        type=NodeType(str(d["type"])),
        model=ModelRef(
            provider=str(d["model"]["provider"]),
            model_id=str(d["model"]["model_id"]),
        ),
        prompt_template=str(d["prompt_template"]),
        inputs=[node_input_from_dict(i) for i in d.get("inputs", [])],
        variable_mapping=variable_mapping,
    )


def dag_from_dict(d: dict[str, Any]) -> DAG:
    return DAG(
        nodes=[node_from_dict(n) for n in d.get("nodes", [])],
        edges=[Edge(source=str(e["source"]), target=str(e["target"])) for e in d.get("edges", [])],
        variables=[str(v) for v in d.get("variables", [])],
    )


def _variable_mapping_to_dict(vm: VariableMapping) -> dict[str, Any]:
    d: dict[str, Any] = {"source": vm.source}
    if vm.role is not None:
        d["role"] = vm.role
    if vm.node_id is not None:
        d["node_id"] = vm.node_id
    if vm.value is not None:
        d["value"] = vm.value
    return d


def dag_to_dict(dag: DAG) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": n.id,
                "type": str(n.type),
                "model": {"provider": n.model.provider, "model_id": n.model.model_id},
                "prompt_template": n.prompt_template,
                "inputs": [{"source": i.source, "role": i.role} for i in n.inputs],
                "variable_mapping": {
                    k: _variable_mapping_to_dict(v) for k, v in n.variable_mapping.items()
                },
            }
            for n in dag.nodes
        ],
        "edges": [{"source": e.source, "target": e.target} for e in dag.edges],
        "variables": dag.variables,
    }


def style_from_dict(d: dict[str, Any], concept: str, vertical: str) -> Style:
    from style_workbench.core.ids import new_ulid
    from style_workbench.domain.style.entity import Style

    name = str(d["name"])
    tags: list[str] = [str(t) for t in d.get("tags", [])]
    dag = dag_from_dict(d["dag"])
    return Style(
        id=new_ulid(),
        name=name,
        concept=concept,
        vertical=vertical,
        tags=tags,
        status="draft",
        current_version=1,
        dag=dag,
        created_by=None,
    )
