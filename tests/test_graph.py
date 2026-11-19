import json
from copy import deepcopy
from pathlib import Path

import networkx as nx
import pytest

from timetravel.graph import build_graph, get_event
from timetravel.models import CausalRelation, Event, EventStatus, RelationKind, StateChange
from timetravel.operations import (
    TravelStatus, add_event, add_relation, cancel_travel, modify_event, modify_relation,
    prevent_travel, remove_event, remove_relation, reschedule_event, travel_to_past,
)


def test_directed_graph_preserves_metadata():
    graph = build_graph([Event("a", "First", 0), Event("b", "Second", 1)], [CausalRelation("a", "b", 2)])
    assert graph.is_directed() and not graph.has_edge("b", "a")
    assert graph.nodes["a"]["label"] == "First"
    assert graph["a"]["b"]["modification_cost"] == 2


def test_missing_endpoint_rejected():
    with pytest.raises(ValueError, match="endpoints"):
        build_graph([Event("a", "First", 0)], [CausalRelation("a", "missing")])


def test_duplicate_event_rejected():
    with pytest.raises(ValueError, match="unique"):
        build_graph([Event("a", "First", 0)] * 2, [])


@pytest.mark.parametrize("cost", [-1, float("inf"), float("nan")])
def test_invalid_cost_rejected(cost):
    with pytest.raises(ValueError, match="costs"):
        build_graph([Event("a", "First", 0)], [CausalRelation("a", "a", cost)])


def test_event_accepts_immutable_metadata_from_json_values():
    entities = ["chart"]
    changes = [{"entity": "chart", "attribute": "revision", "value": "A"}]
    event = Event("b", "Record", 1900, "Archive", entities, changes, 2, 3, "planned")
    changes[0]["value"] = "B"
    entities.clear()
    graph = build_graph([event], [])
    assert get_event(graph, "b") == Event(
        "b", "Record", 1900, "Archive", ("chart",), (StateChange("chart", "revision", "A"),),
        2, 3, EventStatus.PLANNED,
    )


@pytest.mark.parametrize("time", [None, "1900", True, float("nan"), float("inf")])
def test_invalid_event_timestamp(time):
    with pytest.raises(ValueError, match="Event time"):
        Event("a", "Event", time)


@pytest.mark.parametrize("updates", [
    {"id": " "}, {"modification_cost": -1}, {"importance": float("inf")},
    {"status": "unknown"}, {"entities": ["a", "a"]},
    {"state_changes": [StateChange("missing", "mode", "on")]},
])
def test_invalid_event_metadata(updates):
    with pytest.raises(ValueError):
        Event(**({"id": "a", "label": "Event", "time": 1900} | updates))


@pytest.fixture
def timeline():
    return build_graph([Event("a", "Arrival", 1890), Event("b", "Departure", 1900, modification_cost=4)],
                       [CausalRelation("a", "b", 2)])


def test_alternatives_are_independent_and_track_edits(timeline):
    timeline.nodes["a"]["custom"] = {"entries": []}
    added = add_event(timeline, Event("c", "Added", 1910, modification_cost=5))
    edited = modify_event(added.graph, Event("b", "Revised", 1900, status=EventStatus.PLANNED))
    moved = reschedule_event(edited.graph, "b", 1905)
    moved.graph.nodes["a"]["custom"]["entries"].append("branch only")
    assert "c" not in timeline and added.cost == 5 and edited.cost == 4
    assert added.graph.nodes["b"]["label"] == "Departure"
    assert edited.graph.nodes["b"]["time"] == 1900
    assert get_event(moved.graph, "b").time == 1905
    assert timeline.nodes["a"]["custom"] == edited.graph.nodes["a"]["custom"] == {"entries": []}
    assert [r.operation for r in moved.graph.graph["timeline_history"]] == [
        "add_event", "modify_event", "reschedule_event",
    ]
    assert edited.record.before.label == "Departure" and edited.record.after.label == "Revised"


def test_backward_travel_and_cancellation(timeline):
    result = travel_to_past(timeline, "trip-1", "b", "a", cost=3)
    assert not timeline.has_edge("b", "a")
    assert result.cost == 3 and result.graph["b"]["a"]["kind"] == RelationKind.TIME_TRAVEL
    assert not nx.is_directed_acyclic_graph(result.graph)
    cancelled = cancel_travel(result.graph, "trip-1", cost=2)
    assert cancelled.cost == 2 and not cancelled.graph.has_edge("b", "a")
    assert cancelled.record.after.status == TravelStatus.CANCELLED
    assert result.graph.graph["travel_actions"]["trip-1"].status == TravelStatus.ACTIVE
    assert result.graph.has_edge("b", "a")


def test_same_travel_inputs_produce_equal_independent_results(timeline):
    first = travel_to_past(timeline, "trip-1", "b", "a", cost=3)
    second = travel_to_past(timeline, "trip-1", "b", "a", cost=3)
    assert first.record == second.record
    assert nx.utils.graphs_equal(first.graph, second.graph)
    first.graph.remove_edge("b", "a")
    assert second.graph.has_edge("b", "a")


def test_prevention_is_local_to_one_alternative(timeline):
    blocked = prevent_travel(timeline, "trip-1", cost=0)
    assert blocked.cost == 0 and blocked.record.after.status == TravelStatus.PREVENTED
    with pytest.raises(ValueError, match="already registered"):
        travel_to_past(blocked.graph, "trip-1", "b", "a")
    assert travel_to_past(timeline, "trip-1", "b", "a").graph.has_edge("b", "a")


def test_relation_edit_remove_and_rewire(timeline):
    source = add_event(timeline, Event("c", "Later", 1910)).graph
    source = add_relation(source, CausalRelation("b", "c", 7)).graph
    rewired = modify_relation(source, CausalRelation("a", "c", 9), previous_endpoints=("b", "c"))
    assert rewired.cost == 7 and not rewired.graph.has_edge("b", "c")
    assert source.has_edge("b", "c") and rewired.graph.edges["a", "c"]["modification_cost"] == 9
    removed = remove_relation(rewired.graph, "a", "c")
    assert removed.cost == 9 and not removed.graph.has_edge("a", "c")
    assert rewired.graph.has_edge("a", "c")


def test_rewire_travel_updates_where_cancellation_applies(timeline):
    extended = add_event(timeline, Event("c", "Earlier", 1880)).graph
    travelled = travel_to_past(extended, "trip", "b", "a").graph
    rerouted = modify_relation(travelled, CausalRelation("b", "c"), previous_endpoints=("b", "a")).graph
    assert rerouted.graph["travel_actions"]["trip"].endpoints == ("b", "c")
    assert not cancel_travel(rerouted, "trip").graph.has_edge("b", "c")
    assert travelled.has_edge("b", "a")


def test_remove_event_cascades_and_cancels_incident_travel(timeline):
    travelled = travel_to_past(timeline, "trip-1", "b", "a").graph
    removed = remove_event(travelled, "b")
    assert removed.cost == 4 and "b" not in removed.graph and not removed.graph.edges
    assert len(removed.record.removed_relations) == 2
    assert removed.graph.graph["travel_actions"]["trip-1"].status == TravelStatus.CANCELLED
    assert "b" in travelled and travelled.number_of_edges() == 2


@pytest.mark.parametrize("operation,message", [
    (lambda g: add_event(g, Event("a", "Duplicate", 0)), "Duplicate event"),
    (lambda g: reschedule_event(g, "b", 1880), "backward relation"),
    (lambda g: add_relation(g, CausalRelation("b", "a", kind=RelationKind.CAUSAL)), "backward relation"),
    (lambda g: add_relation(g, CausalRelation("a", "b")), "Duplicate causal"),
    (lambda g: travel_to_past(g, "trip", "a", "b"), "earlier target"),
    (lambda g: travel_to_past(g, "trip", "b", "b"), "earlier target"),
    (lambda g: travel_to_past(g, "trip", "missing", "a"), "endpoints"),
    (lambda g: remove_event(g, "missing"), "Unknown event"),
    (lambda g: remove_relation(g, "b", "a"), "Unknown relation"),
    (lambda g: cancel_travel(g, "missing"), "No active travel"),
    (lambda g: prevent_travel(g, "trip", cost=-1), "Prevention costs"),
])
def test_invalid_operations_leave_original_unchanged(timeline, operation, message):
    original = deepcopy(timeline)
    with pytest.raises(ValueError, match=message):
        operation(timeline)
    assert nx.utils.graphs_equal(timeline, original)


EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


@pytest.mark.parametrize("name", [
    "valid_timeline", "grandfather_paradox", "multiple_paradoxes", "complex_timeline",
    "consistent_loop", "contradictory_timeline",
])
def test_examples_load_and_infer_legacy_relation_kind(name):
    data = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    graph = build_graph(map(lambda event: Event(**event), data["events"]),
                        map(lambda relation: CausalRelation(**relation), data["relations"]))
    assert graph.number_of_nodes() == len(data["events"])
    assert graph.number_of_edges() == len(data["relations"])
    for source, target, attributes in graph.edges(data=True):
        backward = graph.nodes[target]["time"] < graph.nodes[source]["time"]
        expected = RelationKind.TIME_TRAVEL if backward else RelationKind.CAUSAL
        assert attributes["kind"] == expected
    if name == "consistent_loop":
        assert not nx.is_directed_acyclic_graph(graph)
        assert {c.value for event in graph for c in get_event(graph, event).state_changes} == {"A"}
    if name == "contradictory_timeline":
        assert nx.is_directed_acyclic_graph(graph)
        assert {c.value for event in graph for c in get_event(graph, event).state_changes} == {"on", "off"}
