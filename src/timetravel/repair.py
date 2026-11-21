"""Finite, validated timeline repair over the existing temporal operations."""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from time import monotonic

import networkx as nx

from . import operations
from .constraints import DEFAULT_CONSTRAINTS, EventPreconditions, RequiredEvents, TimelineConstraint
from .detection import DetectionReport, detect_paradoxes
from .graph import get_event
from .models import CausalRelation, Event, require_number, require_text

Edge = tuple[str, str]


class EditKind(StrEnum):
    REMOVE_EVENT = "remove_event"
    MODIFY_EVENT = "modify_event"
    RESCHEDULE_EVENT = "reschedule_event"
    REMOVE_RELATION = "remove_relation"
    MODIFY_RELATION = "modify_relation"
    CANCEL_TRAVEL = "cancel_travel"
    PREVENT_TRAVEL = "prevent_travel"


def _require_edge(edge: Edge) -> None:
    if not isinstance(edge, tuple) or len(edge) != 2:
        raise ValueError("A relation requires two endpoint IDs")
    for node in edge:
        require_text(node, "Endpoint ID")


@dataclass(frozen=True)
class RepairEdit:
    """A single-use catalog option. Targets and replacement values are fixed."""

    kind: EditKind
    target: str | Edge
    value: Event | CausalRelation | float | None = None
    cost: float | None = None

    def __post_init__(self) -> None:
        kind = EditKind(self.kind)
        object.__setattr__(self, "kind", kind)
        if kind in (EditKind.REMOVE_RELATION, EditKind.MODIFY_RELATION):
            _require_edge(self.target)
        else:
            require_text(self.target, "Edit target")
        if kind == EditKind.MODIFY_EVENT:
            if not isinstance(self.value, Event) or self.value.id != self.target:
                raise ValueError("An event replacement must preserve the target ID")
        elif kind == EditKind.MODIFY_RELATION:
            if not isinstance(self.value, CausalRelation):
                raise ValueError("A relation replacement must be a CausalRelation")
        elif kind == EditKind.RESCHEDULE_EVENT:
            require_number(self.value, "Replacement time")
        elif self.value is not None:
            raise ValueError(f"{kind} does not take a replacement value")
        if self.cost is not None:
            if kind not in (EditKind.CANCEL_TRAVEL, EditKind.PREVENT_TRAVEL):
                raise ValueError("Only travel edits accept an explicit fee")
            require_number(self.cost, "Travel edit cost", nonnegative=True)

    def apply(self, graph: nx.DiGraph, protected_events: frozenset[str] = frozenset()) -> operations.OperationResult:
        kind = self.kind
        if kind in (EditKind.REMOVE_EVENT, EditKind.MODIFY_EVENT, EditKind.RESCHEDULE_EVENT):
            if self.target in protected_events:
                raise ValueError(f"Event {self.target} is protected")
        match kind:
            case EditKind.REMOVE_EVENT:
                return operations.remove_event(graph, self.target)
            case EditKind.MODIFY_EVENT:
                return operations.modify_event(graph, self.value)
            case EditKind.RESCHEDULE_EVENT:
                return operations.reschedule_event(graph, self.target, self.value)
            case EditKind.REMOVE_RELATION:
                return operations.remove_relation(graph, *self.target)
            case EditKind.MODIFY_RELATION:
                return operations.modify_relation(graph, self.value, previous_endpoints=self.target)
            case EditKind.CANCEL_TRAVEL:
                action = graph.graph.get("travel_actions", {}).get(self.target)
                fee = self.cost
                if fee is None:
                    if action is None or action.status != operations.TravelStatus.ACTIVE:
                        raise ValueError(f"No active travel action: {self.target}")
                    if not graph.has_edge(*action.endpoints):
                        raise ValueError(f"No edge for travel action: {self.target}")
                    fee = graph.edges[action.endpoints]["modification_cost"]
                return operations.cancel_travel(graph, self.target, fee)
            case EditKind.PREVENT_TRAVEL:
                return operations.prevent_travel(graph, self.target, 1.0 if self.cost is None else self.cost)
        raise ValueError(f"Unsupported edit: {kind}")


def default_edits(graph: nx.DiGraph, protected_events: frozenset[str] = frozenset()) -> tuple[RepairEdit, ...]:
    """List event removals, edge removals and cancellations of active named trips."""
    edits = [RepairEdit(EditKind.REMOVE_EVENT, event) for event in graph if event not in protected_events]
    for source, target, data in graph.edges(data=True):
        action = data.get("travel_action_id")
        edit = (RepairEdit(EditKind.CANCEL_TRAVEL, action) if action is not None
                else RepairEdit(EditKind.REMOVE_RELATION, (source, target)))
        edits.append(edit)
    return tuple(edits)


@dataclass(frozen=True)
class SearchLimits:
    max_candidates: int = 5_000
    max_seconds: float = 5.0
    max_alternatives: int = 3

    def __post_init__(self) -> None:
        for value, minimum in ((self.max_candidates, 0), (self.max_alternatives, 1)):
            if type(value) is not int or value < minimum:
                raise ValueError("Candidate limit must be nonnegative and alternative limit positive")
        require_number(self.max_seconds, "Time limit", nonnegative=True)


class RepairStatus(StrEnum):
    ALREADY_CONSISTENT = "already_consistent"
    HEURISTIC = "heuristic"
    OPTIMAL = "optimal"
    NO_IMPROVEMENT = "no_improvement"
    NO_SOLUTION = "no_solution"
    LIMIT_REACHED = "limit_reached"


@dataclass
class SearchMetrics:
    expanded: int = 0
    pruned: int = 0
    candidates_explored: int = 0
    invalid: int = 0
    greedy_candidates: int = 0
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class Alternative:
    id: str
    graph: nx.DiGraph
    edits: tuple[operations.EditRecord, ...]
    total_cost: Fraction
    report: DetectionReport
    changed_events: tuple[str, ...]
    changed_relations: tuple[Edge, ...]
    search_metrics: SearchMetrics


@dataclass(frozen=True)
class RepairResult:
    status: RepairStatus
    alternatives: tuple[Alternative, ...]
    metrics: SearchMetrics
    initial_report: DetectionReport
    limit_reason: str | None

    @property
    def best(self) -> Alternative | None:
        return self.alternatives[0] if self.alternatives else None

    @property
    def optimality_proven(self) -> bool:
        return self.status in (RepairStatus.OPTIMAL, RepairStatus.ALREADY_CONSISTENT)


def _events(graph: nx.DiGraph) -> dict:
    return {node: get_event(graph, node) for node in graph}


def _relations(graph: nx.DiGraph) -> dict:
    return {(source, target): (data.get("kind"), data.get("modification_cost", 1.0), data.get("travel_action_id"))
            for source, target, data in graph.edges(data=True)}


def _timeline_key(graph: nx.DiGraph) -> tuple:
    return (frozenset(_events(graph).items()), frozenset(_relations(graph).items()),
            frozenset(graph.graph.get("travel_actions", {}).items()))


@dataclass(frozen=True)
class SearchState:
    graph: nx.DiGraph
    report: DetectionReport
    remaining: int
    key: tuple
    path: tuple[int, ...] = ()
    edits: tuple[operations.EditRecord, ...] = ()
    cost: Fraction = Fraction(0)

    @property
    def rank(self) -> tuple:
        return self.cost, len(self.path), self.path

    def choices(self):
        remaining = self.remaining
        while remaining:
            bit = remaining & -remaining
            yield bit.bit_length() - 1
            remaining ^= bit


@dataclass
class SearchContext:
    catalog: tuple[RepairEdit, ...]
    constraints: tuple[TimelineConstraint, ...] | None
    protected: frozenset[str]
    limits: SearchLimits
    metrics: SearchMetrics = field(default_factory=SearchMetrics)
    started: float = field(default_factory=lambda: monotonic())
    limit_reason: str | None = None

    @property
    def state_only(self) -> bool:
        builtins = (*map(type, DEFAULT_CONSTRAINTS), EventPreconditions, RequiredEvents)
        return self.constraints is None or all(type(rule) in builtins for rule in self.constraints)

    def time_available(self) -> bool:
        if monotonic() - self.started >= self.limits.max_seconds:
            self.limit_reason = "time"
            return False
        return True

    def can_attempt(self) -> bool:
        if not self.time_available():
            return False
        if self.metrics.candidates_explored >= self.limits.max_candidates:
            self.limit_reason = "candidates"
            return False
        return True

    def transition(self, state: SearchState, index: int) -> SearchState | None:
        self.metrics.candidates_explored += 1
        try:
            result = self.catalog[index].apply(state.graph, self.protected)
        except ValueError:
            self.metrics.invalid += 1
            return None
        key = _timeline_key(result.graph)
        if self.state_only and key == state.key:
            self.metrics.pruned += 1
            return None
        cost = Fraction(result.cost) if isinstance(result.cost, int) else Fraction(str(result.cost))
        return SearchState(result.graph, detect_paradoxes(result.graph, self.constraints),
                           state.remaining ^ (1 << index), key, (*state.path, index),
                           (*state.edits, result.record), state.cost + cost)


def _changed(before: dict, after: dict) -> tuple:
    return tuple(sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key)))


def repair_timeline(graph: nx.DiGraph, constraints: Sequence[TimelineConstraint] | None = None,
                    *, edits: Sequence[RepairEdit] | None = None, protected_events: Sequence[str] = (),
                    method: str = "branch_and_bound", limits: SearchLimits = SearchLimits(),
                    use_greedy_bound: bool = True) -> RepairResult:
    """Search single-use edits and keep up to K distinct, validated timelines."""
    from .algorithms.branch_bound import branch_and_bound
    from .algorithms.greedy import greedy

    if method not in ("greedy", "branch_and_bound"):
        raise ValueError(f"Unknown repair method: {method}")
    rules = None if constraints is None else tuple(constraints)
    report = detect_paradoxes(graph, rules)
    protected = frozenset(protected_events)
    for event in protected:
        require_text(event, "Protected event ID")
        if event not in graph:
            raise ValueError(f"Unknown protected event: {event}")
    catalog = default_edits(graph, protected) if edits is None else tuple(dict.fromkeys(edits))
    context = SearchContext(catalog, rules, protected, limits)
    original = SearchState(graph, report, (1 << len(catalog)) - 1, _timeline_key(graph))
    if report.consistent:
        states, status = (original,), RepairStatus.ALREADY_CONSISTENT
    elif method == "greedy":
        best = greedy(context, original)
        states = () if best is None else (best,)
        status = RepairStatus.HEURISTIC if best is not None else RepairStatus.NO_IMPROVEMENT
    else:
        states = branch_and_bound(context, original, use_greedy_bound)
        status = RepairStatus.OPTIMAL if states else RepairStatus.NO_SOLUTION
    if context.limit_reason:
        status = RepairStatus.LIMIT_REACHED
    context.metrics.elapsed_seconds = monotonic() - context.started
    alternatives = tuple(
        Alternative(f"timeline-{index}", deepcopy(state.graph), state.edits, state.cost, state.report,
                    _changed(_events(graph), _events(state.graph)), _changed(_relations(graph), _relations(state.graph)),
                    context.metrics)
        for index, state in enumerate(states, 1)
    )
    return RepairResult(status, alternatives, context.metrics, report, context.limit_reason)
