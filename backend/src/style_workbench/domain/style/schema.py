from __future__ import annotations

from typing import TYPE_CHECKING, Any

from style_workbench.domain.style.entity import DAG, Edge, ModelRef, Node, NodeInput, NodeType

if TYPE_CHECKING:
    from style_workbench.domain.style.entity import Style


def node_input_from_dict(d: dict[str, Any]) -> NodeInput:
    return NodeInput(source=str(d["source"]), role=str(d["role"]))


def node_from_dict(d: dict[str, Any]) -> Node:
    return Node(
        id=str(d["id"]),
        type=NodeType(str(d["type"])),
        model=ModelRef(
            provider=str(d["model"]["provider"]),
            model_id=str(d["model"]["model_id"]),
        ),
        prompt_template=str(d["prompt_template"]),
        inputs=[node_input_from_dict(i) for i in d.get("inputs", [])],
    )


def dag_from_dict(d: dict[str, Any]) -> DAG:
    return DAG(
        nodes=[node_from_dict(n) for n in d.get("nodes", [])],
        edges=[Edge(source=str(e["source"]), target=str(e["target"])) for e in d.get("edges", [])],
        variables=[str(v) for v in d.get("variables", [])],
    )


def dag_to_dict(dag: DAG) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": n.id,
                "type": str(n.type),
                "model": {"provider": n.model.provider, "model_id": n.model.model_id},
                "prompt_template": n.prompt_template,
                "inputs": [{"source": i.source, "role": i.role} for i in n.inputs],
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
