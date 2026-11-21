"""Combine structural cycle evidence with a configurable consistency report."""

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from itertools import pairwise

import networkx as nx

from .algorithms.dfs import find_cycle
from .algorithms.tarjan import strongly_connected_components
from .constraints import DEFAULT_CONSTRAINTS, ConstraintKind, ConstraintViolation, TimelineConstraint
from .graph import get_event, relation_kind
from .models import CausalRelation


@dataclass(frozen=True)
class CycleWitness:
    event_ids: tuple[Hashable, ...]  # Closed path: the first event is repeated at the end.

    @property
    def relations(self) -> tuple[tuple[Hashable, Hashable], ...]:
        return tuple(pairwise(self.event_ids))


@dataclass(frozen=True)
class DetectionReport:
    components: tuple[tuple[Hashable, ...], ...]
    cyclic_components: tuple[tuple[Hashable, ...], ...]
    cycles: tuple[CycleWitness, ...]
    violations: tuple[ConstraintViolation, ...]

    @property
    def consistent(self) -> bool:
        return not self.violations

    @property
    def logical_violations(self) -> tuple[ConstraintViolation, ...]:
        return tuple(item for item in self.violations if item.kind == ConstraintKind.LOGICAL)

    @property
    def causal_violations(self) -> tuple[ConstraintViolation, ...]:
        return tuple(item for item in self.violations if item.kind == ConstraintKind.CAUSAL)


def detect_paradoxes(graph: nx.DiGraph,
                      constraints: Sequence[TimelineConstraint] | None = None) -> DetectionReport:
    """Report one witness per cyclic SCC and all violations under the selected rules.

    Omit constraints for the defaults. An explicit empty sequence requests only
    structural analysis. The input graph is never modified by the built-in rules.
    """
    if not isinstance(graph, nx.DiGraph) or graph.is_multigraph():
        raise TypeError("Expected a simple directed graph")
    for node in graph:
        if not {"time", "label"} <= graph.nodes[node].keys():
            raise ValueError(f"Timeline event {node!r} needs a time and label")
        get_event(graph, node)
    for source, target, data in graph.edges(data=True):
        relation_kind(graph, CausalRelation(source, target, data.get("modification_cost", 1.0), data.get("kind")))

    components = strongly_connected_components(graph)
    cyclic_components = tuple(component for component in components
                              if len(component) > 1 or graph.has_edge(component[0], component[0]))
    cycles = []
    for component in cyclic_components:
        path = find_cycle(graph, component)
        if path is None:
            raise RuntimeError("A cyclic component did not yield a cycle witness")
        cycles.append(CycleWitness(path))
    rules = DEFAULT_CONSTRAINTS if constraints is None else constraints
    violations = tuple(violation for rule in rules for violation in rule.evaluate(graph))
    return DetectionReport(components, cyclic_components, tuple(cycles), violations)
