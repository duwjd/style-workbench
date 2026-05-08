from __future__ import annotations

from style_workbench.core.errors import DagCycleError, DagValidationError
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG
from style_workbench.domain.style.variables import extract_variables


def validate_dag(dag: DAG) -> None:
    """Validate DAG structure. Raises DagValidationError on any violation."""
    node_ids = {n.id for n in dag.nodes}

    # 1. Edge endpoints must reference existing nodes (must precede topological_sort,
    #    which assumes all edge targets are present in node_ids).
    for edge in dag.edges:
        if edge.source not in node_ids:
            raise DagValidationError(f"Edge source '{edge.source}' not in nodes")
        if edge.target not in node_ids:
            raise DagValidationError(f"Edge target '{edge.target}' not in nodes")

    # 2. Cycle check — reuse existing topological_sort
    try:
        topological_sort(dag)
    except DagCycleError as exc:
        raise DagValidationError(str(exc)) from exc

    # 3. DAG-level variables must cover all placeholders in every node template
    dag_vars = set(dag.variables)
    for node in dag.nodes:
        for placeholder in extract_variables(node.prompt_template):
            if placeholder not in dag_vars:
                raise DagValidationError(
                    f"Node '{node.id}' references undefined variable '{placeholder}'"
                )
