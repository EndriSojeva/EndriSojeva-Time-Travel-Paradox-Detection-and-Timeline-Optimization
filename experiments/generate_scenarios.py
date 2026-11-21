"""Deterministic synthetic timeline families and a JSON scenario export."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random

import networkx as nx

from timetravel.graph import build_graph
from timetravel.models import CausalRelation, Event, StateChange
from timetravel.operations import travel_to_past


@dataclass(frozen=True)
class ScenarioSpec:
    size: int
    edge_probability: float
    seed: int
    conflicts: int = 0
    trips: int = 0
    protected: int = 0
    random_back_edges: int = 0

    def __post_init__(self):
        values = (self.size, self.seed, self.conflicts, self.trips, self.protected, self.random_back_edges)
        if any(type(value) is not int for value in values) or self.size < 1 or self.protected > self.size:
            raise ValueError("Invalid scenario counts or seed")
        if not 0 <= self.edge_probability <= 1 or min(values[2:]) < 0:
            raise ValueError("Invalid scenario density or counts")
        if 2 * (self.conflicts + self.trips) > self.size:
            raise ValueError("Conflict and travel pairs require distinct events")


@dataclass(frozen=True)
class GeneratedScenario:
    graph: nx.DiGraph
    protected_events: tuple[str, ...]
    conflict_events: tuple[str, ...]
    expected_cycles: int | None
    expected_violations: int
    events: tuple[Event, ...]
    relations: tuple[CausalRelation, ...]
    travel: tuple[tuple[str, str, str, int], ...]


def generate_scenario(spec: ScenarioSpec) -> GeneratedScenario:
    rng = Random(spec.seed)
    events = []
    for i in range(spec.size):
        group = i // 2
        entity = f"signal-{group}"
        is_conflict = i < 2 * spec.conflicts
        changes = (StateChange(entity, "mode", "on" if i % 2 == 0 else "off"),) if is_conflict else ()
        events.append(Event(f"e{i}", f"Event {i}", i - 1 if is_conflict and i % 2 else i,
                            entities=(entity,) if is_conflict else (), state_changes=changes,
                            modification_cost=rng.randint(1, 9)))
    trip_starts = range(2 * spec.conflicts, 2 * (spec.conflicts + spec.trips), 2)
    required_edges = {(i, i + 1) for i in trip_starts}
    relations = []
    for i in range(spec.size):
        for j in range(i + 1, spec.size):
            if rng.random() < spec.edge_probability or (i, j) in required_edges:
                relations.append(CausalRelation(f"e{i}", f"e{j}", rng.randint(1, 9)))
    if spec.random_back_edges:
        reserved = {(i + 1, i) for i in trip_starts}
        pairs = [(i, j) for i in range(spec.size) for j in range(i)
                 if (i, j) not in reserved and events[i].time > events[j].time]
        if spec.random_back_edges > len(pairs):
            raise ValueError("Too many random backward edges for this scenario")
        for i, j in rng.sample(pairs, spec.random_back_edges):
            relations.append(CausalRelation(f"e{i}", f"e{j}", rng.randint(1, 9), "time_travel"))
    graph = build_graph(events, relations)
    travel = []
    for i in trip_starts:
        trip = (f"trip-{i}", f"e{i + 1}", f"e{i}", rng.randint(1, 9))
        travel.append(trip)
        graph = travel_to_past(graph, *trip).graph
    # Protect non-conflicting context first, then conflicting events if requested.
    protected = tuple(event.id for event in reversed(events))[:spec.protected]
    return GeneratedScenario(graph, protected, tuple(f"e{i}" for i in range(2 * spec.conflicts)),
                             None if spec.random_back_edges else spec.trips, spec.conflicts,
                             tuple(events), tuple(relations), tuple(travel))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default, kind in (("size", 10, int), ("edge-probability", 0.1, float), ("seed", 42, int),
                                ("conflicts", 0, int), ("trips", 0, int), ("protected", 0, int),
                                ("random-back-edges", 0, int)):
        parser.add_argument(f"--{name}", default=default, type=kind)
    parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop("output")
    spec = ScenarioSpec(**args)
    scenario = generate_scenario(spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": 1, "description": "Seeded benchmark scenario", "parameters": asdict(spec),
        "events": [asdict(event) for event in scenario.events],
        "relations": [asdict(relation) for relation in scenario.relations],
        "travel_actions": scenario.travel, "protected_events": scenario.protected_events,
        "expected_cyclic_components": scenario.expected_cycles, "expected_violations": scenario.expected_violations,
    }, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
