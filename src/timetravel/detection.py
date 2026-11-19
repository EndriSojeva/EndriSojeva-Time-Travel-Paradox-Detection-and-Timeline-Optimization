"""Paradox analysis interface, deliberately not implemented in Phase 1."""

from collections.abc import Sequence

import networkx as nx

from .constraints import TimelineConstraint


def detect_paradoxes(graph: nx.DiGraph, constraints: Sequence[TimelineConstraint]):
    """Combine structural evidence with explicit logical rules in Phase 2."""
    raise NotImplementedError("Logical paradox detection is planned for Phase 2")
