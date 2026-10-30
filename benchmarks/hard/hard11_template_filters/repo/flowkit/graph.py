"""Dependency ordering for pipeline steps."""

from __future__ import annotations

import bisect
from typing import Iterable, Mapping


class CycleError(ValueError):
    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__("dependency cycle: " + " -> ".join(cycle))


def topo_order(deps: Mapping[str, Iterable[str]]) -> list[str]:
    """Order steps so that every step comes after all of its dependencies.

    `deps` maps step name -> names it depends on. Ties are broken alphabetically,
    so the result is deterministic. Raises ValueError for unknown dependencies and
    CycleError (with the offending cycle) when no valid order exists.
    """
    graph = {node: sorted(set(ds)) for node, ds in deps.items()}
    for node, ds in graph.items():
        for d in ds:
            if d not in graph:
                raise ValueError(f"step {node!r} depends on unknown step {d!r}")

    indegree = {node: len(ds) for node, ds in graph.items()}
    dependents: dict[str, list[str]] = {node: [] for node in graph}
    for node, ds in graph.items():
        for d in ds:
            dependents[d].append(node)

    ready = sorted(node for node, n in indegree.items() if n == 0)
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for m in sorted(dependents[node]):
            indegree[m] -= 1
            if indegree[m] == 0:
                bisect.insort(ready, m)

    if len(order) < len(graph):
        raise CycleError(_find_cycle(graph, set(graph) - set(order)))
    return order


def _find_cycle(graph: dict[str, list[str]], remaining: set[str]) -> list[str]:
    """Walk dependencies inside the unresolved set until a node repeats."""
    node = min(remaining)
    path = [node]
    seen = {node: 0}
    while True:
        node = next(d for d in graph[node] if d in remaining)
        if node in seen:
            return path[seen[node] :] + [node]
        seen[node] = len(path)
        path.append(node)
