"""Iterative Tarjan algorithm for strongly connected components."""

from collections.abc import Hashable

import networkx as nx


def strongly_connected_components(graph: nx.DiGraph) -> tuple[tuple[Hashable, ...], ...]:
    """Return SCCs in traversal completion order and members in stack pop order."""
    if not isinstance(graph, nx.DiGraph) or graph.is_multigraph():
        raise TypeError("Expected a simple directed graph")
    index = {}
    low = {}
    open_nodes = []
    on_stack = set()
    components = []
    frames = []

    def discover(node):
        index[node] = low[node] = len(index)
        open_nodes.append(node)
        on_stack.add(node)
        frames.append((node, iter(graph.successors(node))))

    for root in graph:
        if root in index:
            continue
        discover(root)
        while frames:
            node, children = frames[-1]
            child = next(children, None)
            if child is not None:
                if child not in index:
                    discover(child)
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
                continue

            frames.pop()
            if low[node] == index[node]:
                component = []
                while True:
                    member = open_nodes.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(tuple(component))
            if frames:
                parent = frames[-1][0]
                low[parent] = min(low[parent], low[node])

    return tuple(components)
