from __future__ import annotations

from collections import defaultdict, deque

from style_workbench.core.errors import DagCycleError
from style_workbench.domain.style.entity import DAG


def topological_sort(dag: DAG) -> list[str]:
    """Return node IDs in topological order. Raises DagCycleError if cycle found."""
    node_ids = {n.id for n in dag.nodes}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in dag.edges:
        adjacency[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue: deque[str] = deque(nid for nid in node_ids if in_degree[nid] == 0)
    result: list[str] = []

    while queue:
        current = queue.popleft()
        result.append(current)
        for neighbour in adjacency[current]:
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(result) != len(node_ids):
        raise DagCycleError("DAG contains a directed cycle")

    return result
