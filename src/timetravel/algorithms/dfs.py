"""Iterative depth-first search for one directed cycle witness."""

from collections.abc import Hashable, Sequence

import networkx as nx


def find_cycle(graph: nx.DiGraph, nodes: Sequence[Hashable] | None = None) -> tuple[Hashable, ...] | None:
    """Return a closed walk with no repeated interior node, in traversal order."""
    if not isinstance(graph, nx.DiGraph) or graph.is_multigraph():
        raise TypeError("Expected a simple directed graph")
    roots = graph if nodes is None else nodes
    allowed = None if nodes is None else set(nodes)
    visited = set()
    active = {}
    for root in roots:
        if root in visited:
            continue
        visited.add(root)
        active[root] = 0
        stack = [(root, iter(graph.successors(root)))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:  # NetworkX disallows None as a node.
                stack.pop()
                del active[node]
            elif allowed is not None and child not in allowed:
                continue
            elif child in active:
                start = active[child]
                return (*[node for node, _ in stack[start:]], child)
            elif child not in visited:
                visited.add(child)
                active[child] = len(stack)
                stack.append((child, iter(graph.successors(child))))
    return None
