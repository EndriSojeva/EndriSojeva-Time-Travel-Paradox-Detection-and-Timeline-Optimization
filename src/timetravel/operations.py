"""Atomic, copy-on-write operations on graphs constructed by build_graph."""

from copy import deepcopy
from dataclasses import dataclass, replace
from enum import StrEnum

import networkx as nx

from .graph import event_attributes, get_event, insert_relation, relation_kind
from .models import CausalRelation, Event, RelationKind, require_number, require_text


class TravelStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PREVENTED = "prevented"


@dataclass(frozen=True)
class TravelAction:
    id: str
    status: TravelStatus
    endpoints: tuple[str, str] | None = None


TimelineValue = Event | CausalRelation | TravelAction


@dataclass(frozen=True)
class EditRecord:
    operation: str
    cost: float
    before: TimelineValue | None = None
    after: TimelineValue | None = None
    removed_relations: tuple[CausalRelation, ...] = ()


@dataclass(frozen=True)
class OperationResult:
    graph: nx.DiGraph
    record: EditRecord

    @property
    def cost(self) -> float:
        return self.record.cost


def _result(graph: nx.DiGraph, record: EditRecord) -> OperationResult:
    graph.graph["timeline_history"] = (*graph.graph.get("timeline_history", ()), record)
    return OperationResult(graph, record)


def _get_relation(graph: nx.DiGraph, source: str, target: str) -> CausalRelation:
    if not graph.has_edge(source, target):
        raise ValueError(f"Unknown relation: {source} -> {target}")
    data = graph[source][target]
    return CausalRelation(source, target, data["modification_cost"], data["kind"])


def _incident_edges(graph: nx.DiGraph, event_id: str) -> tuple[tuple[str, str], ...]:
    return tuple(dict.fromkeys((*graph.in_edges(event_id), *graph.out_edges(event_id))))


def _cancel_edge_action(graph: nx.DiGraph, source: str, target: str) -> None:
    action_id = graph[source][target].get("travel_action_id")
    if action_id is not None:
        actions = graph.graph["travel_actions"]
        actions[action_id] = replace(actions[action_id], status=TravelStatus.CANCELLED)


def add_event(graph: nx.DiGraph, event: Event) -> OperationResult:
    if event.id in graph:
        raise ValueError(f"Duplicate event ID: {event.id}")
    candidate = deepcopy(graph)
    candidate.add_node(event.id, **event_attributes(event))
    return _result(candidate, EditRecord("add_event", event.modification_cost, after=event))


def _change_event(graph: nx.DiGraph, event: Event, operation: str) -> OperationResult:
    previous = get_event(graph, event.id)
    candidate = deepcopy(graph)
    candidate.nodes[event.id].update(event_attributes(event))
    for source, target in _incident_edges(candidate, event.id):
        relation_kind(candidate, _get_relation(candidate, source, target))
    return _result(candidate, EditRecord(operation, previous.modification_cost, previous, event))


def modify_event(graph: nx.DiGraph, event: Event) -> OperationResult:
    """Replace the record for an existing ID and revalidate all incident edges."""
    return _change_event(graph, event, "modify_event")


def reschedule_event(graph: nx.DiGraph, event_id: str, time: float) -> OperationResult:
    event = replace(get_event(graph, event_id), time=time)
    return _change_event(graph, event, "reschedule_event")


def remove_event(graph: nx.DiGraph, event_id: str) -> OperationResult:
    event = get_event(graph, event_id)
    candidate = deepcopy(graph)
    removed_relations = []
    for source, target in _incident_edges(candidate, event_id):
        removed_relations.append(_get_relation(candidate, source, target))
        _cancel_edge_action(candidate, source, target)
    candidate.remove_node(event_id)
    return _result(candidate, EditRecord("remove_event", event.modification_cost, event,
                                         removed_relations=tuple(removed_relations)))


def add_relation(graph: nx.DiGraph, relation: CausalRelation) -> OperationResult:
    candidate = deepcopy(graph)
    insert_relation(candidate, relation)
    added = _get_relation(candidate, relation.source, relation.target)
    return _result(candidate, EditRecord("add_relation", added.modification_cost, after=added))


def modify_relation(graph: nx.DiGraph, relation: CausalRelation, *,
                    previous_endpoints: tuple[str, str] | None = None) -> OperationResult:
    """Replace an edge; optionally identify a different pair of original endpoints."""
    endpoints = (relation.source, relation.target)
    original = endpoints if previous_endpoints is None else previous_endpoints
    previous = _get_relation(graph, *original)
    if relation.kind is None:
        relation = replace(relation, kind=previous.kind)
    kind = relation_kind(graph, relation)
    if original != endpoints and graph.has_edge(*endpoints):
        raise ValueError("Duplicate causal relations are not supported")
    candidate = deepcopy(graph)
    attributes = dict(candidate.edges[original])
    action_id = attributes.get("travel_action_id")
    if action_id is not None:
        if kind != RelationKind.TIME_TRAVEL:
            raise ValueError("A named travel action must keep its travel relation")
        actions = candidate.graph["travel_actions"]
        actions[action_id] = replace(actions[action_id], endpoints=endpoints)
    if original != endpoints:
        candidate.remove_edge(*original)
        candidate.add_edge(*endpoints)
    candidate.edges[endpoints].update(attributes, kind=kind, modification_cost=relation.modification_cost)
    return _result(candidate, EditRecord("modify_relation", previous.modification_cost, previous, relation))


def remove_relation(graph: nx.DiGraph, source: str, target: str) -> OperationResult:
    previous = _get_relation(graph, source, target)
    candidate = deepcopy(graph)
    _cancel_edge_action(candidate, source, target)
    candidate.remove_edge(source, target)
    return _result(candidate, EditRecord("remove_relation", previous.modification_cost, previous))


def travel_to_past(graph: nx.DiGraph, action_id: str, source: str, target: str,
                   cost: float = 1.0) -> OperationResult:
    """Create one named travel edge between existing departure and arrival events."""
    require_text(action_id, "Travel action ID")
    if action_id in graph.graph.get("travel_actions", {}):
        raise ValueError(f"Travel action is already registered: {action_id}")
    relation = CausalRelation(source, target, cost, RelationKind.TIME_TRAVEL)
    candidate = deepcopy(graph)
    insert_relation(candidate, relation)
    action = TravelAction(action_id, TravelStatus.ACTIVE, (source, target))
    candidate.graph.setdefault("travel_actions", {})[action_id] = action
    candidate[source][target]["travel_action_id"] = action_id
    return _result(candidate, EditRecord("travel_to_past", cost, after=action))


def cancel_travel(graph: nx.DiGraph, action_id: str, cost: float = 1.0) -> OperationResult:
    require_text(action_id, "Travel action ID")
    require_number(cost, "Cancellation costs", nonnegative=True)
    action = graph.graph.get("travel_actions", {}).get(action_id)
    if action is None or action.status != TravelStatus.ACTIVE or action.endpoints is None:
        raise ValueError(f"No active travel action: {action_id}")
    candidate = deepcopy(graph)
    source, target = action.endpoints
    previous = _get_relation(candidate, source, target)
    _cancel_edge_action(candidate, source, target)
    candidate.remove_edge(source, target)
    cancelled = candidate.graph["travel_actions"][action_id]
    return _result(candidate, EditRecord("cancel_travel", cost, action, cancelled, (previous,)))


def prevent_travel(graph: nx.DiGraph, action_id: str, cost: float = 1.0) -> OperationResult:
    require_text(action_id, "Travel action ID")
    require_number(cost, "Prevention costs", nonnegative=True)
    if action_id in graph.graph.get("travel_actions", {}):
        raise ValueError(f"Travel action is already registered: {action_id}")
    candidate = deepcopy(graph)
    action = TravelAction(action_id, TravelStatus.PREVENTED)
    candidate.graph.setdefault("travel_actions", {})[action_id] = action
    return _result(candidate, EditRecord("prevent_travel", cost, after=action))
