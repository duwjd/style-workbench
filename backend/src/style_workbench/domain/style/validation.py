from __future__ import annotations

from style_workbench.core.errors import DagCycleError, DagValidationError
from style_workbench.domain.style.dag import topological_sort
from style_workbench.domain.style.entity import DAG
from style_workbench.domain.style.variables import extract_variables


def validate_dag(dag: DAG) -> None:
    """Validate DAG structure. Raises DagValidationError on any violation."""
    # 0. Must have at least one node
    if not dag.nodes:
        raise DagValidationError("DAG must contain at least one node")

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

    # 3. DAG-level variables must cover all placeholders in every node template.
    #    A placeholder is resolved if it appears in dag.variables OR in the node's
    #    variable_mapping keys. The latter takes precedence for per-node overrides.
    dag_vars = set(dag.variables)
    for node in dag.nodes:
        node_mapped_keys = set(node.variable_mapping.keys())
        for placeholder in extract_variables(node.prompt_template):
            if placeholder not in dag_vars and placeholder not in node_mapped_keys:
                raise DagValidationError(
                    f"Node '{node.id}' references undefined variable '{placeholder}'"
                )

    # 4. variable_mapping integrity checks
    for node in dag.nodes:
        for key, mapping in node.variable_mapping.items():
            # source="node_output" → referenced node_id must exist in the DAG
            if mapping.source == "node_output":
                if mapping.node_id not in node_ids:
                    raise DagValidationError(
                        f"Node '{node.id}' variable_mapping['{key}'] references "
                        f"unknown node_id '{mapping.node_id}'"
                    )
            # source="user_input" → role must be non-empty (domain enforces this in
            # VariableMapping.__post_init__ already, but we guard here too so that
            # dicts deserialized from JSONB also pass through the same check)
            elif mapping.source == "user_input" and not mapping.role:
                raise DagValidationError(
                    f"Node '{node.id}' variable_mapping['{key}'] has "
                    "source='user_input' but missing 'role'"
                )
