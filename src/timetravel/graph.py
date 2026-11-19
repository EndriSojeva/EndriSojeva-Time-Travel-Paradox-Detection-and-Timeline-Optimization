"""Directed graph construction, independent of paradox semantics."""

from dataclasses import fields
from typing import Iterable

import networkx as nx

from .models import CausalRelation, Event, RelationKind


def event_attributes(event: Event) -> dict:
    return {field.name: getattr(event, field.name) for field in fields(Event) if field.name != "id"}


def get_event(graph: nx.DiGraph, event_id: str) -> Event:
    if event_id not in graph:
        raise ValueError(f"Unknown event: {event_id}")
    data = graph.nodes[event_id]
    return Event(event_id, **{field.name: data[field.name] for field in fields(Event) if field.name in data and field.name != "id"})


def relation_kind(graph: nx.DiGraph, relation: CausalRelation) -> RelationKind:
    if relation.source not in graph or relation.target not in graph:
        raise ValueError("Relation endpoints must reference existing events")
    backward = graph.nodes[relation.target]["time"] < graph.nodes[relation.source]["time"]
    kind = relation.kind or (RelationKind.TIME_TRAVEL if backward else RelationKind.CAUSAL)
    if kind == RelationKind.TIME_TRAVEL and not backward:
        raise ValueError("Time travel requires an earlier target")
    if kind == RelationKind.CAUSAL and backward:
        raise ValueError("A backward relation must be time travel")
    return kind


def insert_relation(graph: nx.DiGraph, relation: CausalRelation) -> None:
    kind = relation_kind(graph, relation)
    if graph.has_edge(relation.source, relation.target):
        raise ValueError("Duplicate causal relations are not supported")
    graph.add_edge(relation.source, relation.target, modification_cost=relation.modification_cost, kind=kind)


def build_graph(events: Iterable[Event], relations: Iterable[CausalRelation]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for event in events:
        if event.id in graph:
            raise ValueError("Event IDs must be nonempty and unique")
        graph.add_node(event.id, **event_attributes(event))
    for relation in relations:
        insert_relation(graph, relation)
    return graph
