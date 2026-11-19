"""Immutable input records for directed causal timelines."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    id: str
    label: str
    time: float


@dataclass(frozen=True)
class CausalRelation:
    source: str
    target: str
    modification_cost: float = 1.0
