"""Explicit consistency rules over event assertions and required dependencies."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import networkx as nx

from .graph import get_event
from .models import EventStatus, require_text
from .operations import TravelStatus


class ConstraintKind(StrEnum):
    CAUSAL = "causal"
    LOGICAL = "logical"


@dataclass(frozen=True)
class ConstraintViolation:
    rule: str
    event_ids: tuple[str, ...]
    explanation: str
    kind: ConstraintKind = ConstraintKind.LOGICAL
    relations: tuple[tuple[str, str], ...] = ()


class TimelineConstraint(Protocol):
    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        """Return violations under the constraint's explicitly defined semantics."""
        ...


def _status(graph: nx.DiGraph, event: str) -> str:
    if event not in graph:
        return "missing"
    return EventStatus(graph.nodes[event].get("status", EventStatus.OCCURRED)).value


class ExclusiveState:
    """An entity attribute has one asserted value at a given instant."""

    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        assertions = {}
        for node in graph:
            event = get_event(graph, node)
            if event.status != EventStatus.OCCURRED:
                continue
            for change in event.state_changes:
                key = (event.time, change.entity, change.attribute)
                values, events = assertions.setdefault(key, ({}, {}))
                values[change.value] = None
                events[event.id] = None

        return [
            ConstraintViolation("exclusive_state", tuple(events),
                                f"At {time}, {entity}.{attribute} has incompatible values: {', '.join(values)}.")
            for (time, entity, attribute), (values, events) in assertions.items() if len(values) > 1
        ]


class CausalPrerequisites:
    """An occurred effect requires its declared causes to have occurred."""

    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        statuses = {event: _status(graph, event) for event in graph}
        return [
            ConstraintViolation("causal_prerequisite", (source, target),
                                f"{target} occurred, but its declared cause {source} is {statuses[source]}.",
                                ConstraintKind.CAUSAL, ((source, target),))
            for source, target in graph.edges
            if statuses[target] == EventStatus.OCCURRED and statuses[source] != EventStatus.OCCURRED
        ]


@dataclass(frozen=True)
class EventPrerequisite:
    event_id: str
    required_event_id: str

    def __post_init__(self) -> None:
        require_text(self.event_id, "Dependent event ID")
        require_text(self.required_event_id, "Prerequisite event ID")


@dataclass(frozen=True)
class EventPreconditions:
    """Explicit prerequisites, including for events no longer present as nodes."""

    prerequisites: tuple[EventPrerequisite, ...]

    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        violations = []
        for rule in self.prerequisites:
            if _status(graph, rule.event_id) != EventStatus.OCCURRED:
                continue
            state = _status(graph, rule.required_event_id)
            if state != EventStatus.OCCURRED:
                violations.append(ConstraintViolation(
                    "event_precondition", (rule.event_id, rule.required_event_id),
                    f"{rule.event_id} occurred, but requires {rule.required_event_id}, which is {state}.",
                ))
        return violations


@dataclass(frozen=True)
class RequiredEvents:
    """Events the scenario requires unconditionally to exist and have occurred."""

    event_ids: tuple[str, ...]

    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        violations = []
        for event in self.event_ids:
            require_text(event, "Required event ID")
            state = _status(graph, event)
            if state != EventStatus.OCCURRED:
                violations.append(ConstraintViolation("required_event", (event,),
                                                      f"Required event {event} is {state}."))
        return violations


class ActiveTravelEndpoints:
    """An active named trip requires two occurred events and its recorded edge."""

    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        violations = []
        for action in graph.graph.get("travel_actions", {}).values():
            if action.status != TravelStatus.ACTIVE:
                continue
            source, target = action.endpoints
            unavailable = [f"{event} ({_status(graph, event)})" for event in (source, target)
                           if _status(graph, event) != EventStatus.OCCURRED]
            edge = graph.get_edge_data(source, target)
            if unavailable or edge is None or edge.get("travel_action_id") != action.id:
                reason = (f"unavailable endpoints: {', '.join(unavailable)}" if unavailable
                          else "its recorded travel edge is missing")
                violations.append(ConstraintViolation("active_travel", (source, target),
                                                      f"Active trip {action.id} has {reason}.",
                                                      relations=((source, target),)))
        return violations


DEFAULT_CONSTRAINTS: tuple[TimelineConstraint, ...] = (
    ExclusiveState(), CausalPrerequisites(), ActiveTravelEndpoints(),
)
