"""Read the project scenario format and its declared rule parameters."""

import json
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from .constraints import DEFAULT_CONSTRAINTS, EventPreconditions, EventPrerequisite, RequiredEvents, TimelineConstraint
from .graph import build_graph
from .models import CausalRelation, Event


@dataclass(frozen=True)
class Scenario:
    description: str
    graph: nx.DiGraph
    constraints: tuple[TimelineConstraint, ...]
    data: dict


def load_scenario(path: Path) -> Scenario:
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = build_graph((Event(**event) for event in data["events"]),
                        (CausalRelation(**relation) for relation in data["relations"]))
    prerequisites = tuple(EventPrerequisite(**item) for item in data.get("prerequisites", ()))
    required = tuple(data.get("required_events", ()))
    return Scenario(data["description"], graph,
                    (*DEFAULT_CONSTRAINTS, EventPreconditions(prerequisites), RequiredEvents(required)), data)
