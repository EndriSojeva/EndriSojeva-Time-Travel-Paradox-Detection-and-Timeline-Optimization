"""Directed graph construction, independent of paradox semantics."""

from math import isfinite
from typing import Iterable

import networkx as nx

from .models import CausalRelation, Event


def build_graph(events: Iterable[Event], relations: Iterable[CausalRelation]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for event in events:
        if not event.id or event.id in graph:
            raise ValueError("Event IDs must be nonempty and unique")
        if not isfinite(event.time):
            raise ValueError("Event times must be finite")
        graph.add_node(event.id, label=event.label, time=event.time)
    for relation in relations:
        if relation.source not in graph or relation.target not in graph:
            raise ValueError("Relation endpoints must reference existing events")
        if not isfinite(relation.modification_cost) or relation.modification_cost < 0:
            raise ValueError("Modification costs must be finite and nonnegative")
        if graph.has_edge(relation.source, relation.target):
            raise ValueError("Duplicate causal relations are not supported")
        graph.add_edge(relation.source, relation.target, modification_cost=relation.modification_cost)
    return graph
