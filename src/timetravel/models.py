"""Immutable input records for directed causal timelines."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class EventStatus(StrEnum):
    PLANNED = "planned"
    OCCURRED = "occurred"
    PREVENTED = "prevented"


class RelationKind(StrEnum):
    CAUSAL = "causal"
    TIME_TRAVEL = "time_travel"


def require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")


def require_number(value: float, field: str, *, nonnegative: bool = False) -> None:
    finite = isinstance(value, int) or isinstance(value, float) and isfinite(value)
    if isinstance(value, bool) or not finite or (nonnegative and value < 0):
        qualifier = " and nonnegative" if nonnegative else ""
        raise ValueError(f"{field} must be finite{qualifier}")


@dataclass(frozen=True)
class StateChange:
    """An event's assertion about an entity attribute after the event."""

    entity: str
    attribute: str
    value: str

    def __post_init__(self) -> None:
        require_text(self.entity, "State change entity")
        require_text(self.attribute, "State change attribute")
        require_text(self.value, "State change value")


@dataclass(frozen=True)
class Event:
    id: str
    label: str
    time: float
    location: str | None = None
    entities: tuple[str, ...] = ()
    state_changes: tuple[StateChange, ...] = ()
    importance: float = 1.0
    modification_cost: float = 1.0
    status: EventStatus = EventStatus.OCCURRED

    def __post_init__(self) -> None:
        require_text(self.id, "Event ID")
        require_text(self.label, "Event label")
        require_number(self.time, "Event time")
        require_number(self.importance, "Event importance", nonnegative=True)
        require_number(self.modification_cost, "Event modification costs", nonnegative=True)
        if self.location is not None:
            require_text(self.location, "Event location")
        if not isinstance(self.entities, (list, tuple)):
            raise ValueError("Event entities must be a list or tuple")
        for entity in self.entities:
            require_text(entity, "Affected entity")
        if len(self.entities) != len(set(self.entities)):
            raise ValueError("Affected entities must be unique")
        if not isinstance(self.state_changes, (list, tuple)):
            raise ValueError("Event state changes must be a list or tuple")
        changes = []
        for change in self.state_changes:
            if isinstance(change, dict) and change.keys() == {"entity", "attribute", "value"}:
                change = StateChange(**change)
            if not isinstance(change, StateChange) or change.entity not in self.entities:
                raise ValueError("Each state change must refer to an affected entity")
            changes.append(change)
        object.__setattr__(self, "entities", tuple(self.entities))
        object.__setattr__(self, "state_changes", tuple(changes))
        object.__setattr__(self, "status", EventStatus(self.status))


@dataclass(frozen=True)
class CausalRelation:
    source: str
    target: str
    modification_cost: float = 1.0
    kind: RelationKind | None = None

    def __post_init__(self) -> None:
        require_text(self.source, "Source event ID")
        require_text(self.target, "Target event ID")
        require_number(self.modification_cost, "Relation modification costs", nonnegative=True)
        if self.kind is not None:
            object.__setattr__(self, "kind", RelationKind(self.kind))
