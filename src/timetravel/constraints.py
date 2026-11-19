"""Contracts for future logical constraints; no satisfiability solver yet."""

from dataclasses import dataclass
from typing import Protocol

import networkx as nx


@dataclass(frozen=True)
class ConstraintViolation:
    rule: str
    event_ids: tuple[str, ...]
    explanation: str


class TimelineConstraint(Protocol):
    def evaluate(self, graph: nx.DiGraph) -> list[ConstraintViolation]:
        """Return violations under the constraint's explicitly defined semantics."""
        ...
