"""Contracts for future logical constraints; no satisfiability solver yet."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import networkx as nx


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
