from pathlib import Path

import networkx as nx
import pytest

from timetravel.algorithms.dfs import find_cycle
from timetravel.algorithms.tarjan import strongly_connected_components
from timetravel.constraints import DEFAULT_CONSTRAINTS, EventPreconditions, EventPrerequisite, RequiredEvents
from timetravel.detection import detect_paradoxes
from timetravel.graph import build_graph
from timetravel.models import CausalRelation, Event, EventStatus, StateChange
from timetravel.operations import cancel_travel, prevent_travel, remove_event, travel_to_past
from timetravel.scenarios import load_scenario


EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


@pytest.mark.parametrize("name,consistent,cycles,logical,causal", [
    ("valid_timeline", True, 0, 0, 0),
    ("consistent_loop", True, 1, 0, 0),
    ("contradictory_timeline", False, 0, 1, 0),
    ("grandfather_paradox", False, 1, 1, 1),
    ("multiple_paradoxes", True, 2, 0, 0),
    ("complex_timeline", True, 2, 0, 0),
])
def test_scenarios_distinguish_cycles_and_violations(name, consistent, cycles, logical, causal):
    scenario = load_scenario(EXAMPLES / f"{name}.json")
    report = detect_paradoxes(scenario.graph, scenario.constraints)
    assert report == detect_paradoxes(scenario.graph, scenario.constraints)
    assert report.consistent is consistent
    assert len(report.cycles) == len(report.cyclic_components) == cycles
    assert len(report.logical_violations) == logical
    assert len(report.causal_violations) == causal
    for witness, component in zip(report.cycles, report.cyclic_components, strict=True):
        assert witness.event_ids[0] == witness.event_ids[-1]
        assert len(set(witness.event_ids[:-1])) == len(witness.event_ids) - 1
        assert set(witness.event_ids) <= set(component)
        assert all(scenario.graph.has_edge(*edge) for edge in witness.relations)


def test_grandfather_reports_cause_and_explicit_existence_dependency():
    scenario = load_scenario(EXAMPLES / "grandfather_paradox.json")
    report = detect_paradoxes(scenario.graph, scenario.constraints)
    assert report.causal_violations[0].event_ids == ("e0", "e1")
    assert report.causal_violations[0].relations == (("e0", "e1"),)
    assert report.logical_violations[0].rule == "event_precondition"
    assert report.logical_violations[0].event_ids == ("e2", "e0")
    assert "prevented" in report.logical_violations[0].explanation
    assert detect_paradoxes(scenario.graph, []).consistent


def test_self_loop_with_disconnected_node_is_a_single_edge_witness():
    graph = build_graph([Event("x", "Loop", 0), Event("y", "Isolated", 0)], [CausalRelation("x", "x")])
    report = detect_paradoxes(graph)
    assert report.components == (("x",), ("y",))
    assert report.cyclic_components == (("x",),)
    assert report.cycles[0].relations == (("x", "x"),)
    assert report.consistent


@pytest.mark.parametrize("seed", range(18))
def test_custom_algorithms_match_networkx_on_generated_graphs(seed):
    graph = nx.gnp_random_graph(25 + seed, (0.01, 0.04, 0.16)[seed % 3], seed=seed, directed=True)
    components = strongly_connected_components(graph)
    assert {frozenset(c) for c in components} == {frozenset(c) for c in nx.strongly_connected_components(graph)}
    assert components == strongly_connected_components(graph.copy())
    cycle = find_cycle(graph)
    assert (cycle is None) == nx.is_directed_acyclic_graph(graph)
    if cycle is not None:
        assert cycle[0] == cycle[-1]
        assert all(graph.has_edge(u, v) for u, v in zip(cycle, cycle[1:]))


def test_long_generated_chain_and_cycle_do_not_require_python_recursion():
    graph = nx.path_graph(2_500, create_using=nx.DiGraph)
    assert find_cycle(graph) is None
    assert len(strongly_connected_components(graph)) == 2_500
    graph.add_edge(2499, 0)
    assert len(find_cycle(graph)) == 2_501
    assert len(strongly_connected_components(graph)) == 1


def test_missing_precondition_and_required_event_are_reported_after_deletion():
    graph = build_graph([Event("a", "A", 0), Event("b", "B", 1)], [CausalRelation("a", "b")])
    constraints = (*DEFAULT_CONSTRAINTS, EventPreconditions((EventPrerequisite("b", "a"),)), RequiredEvents(("a",)))
    assert detect_paradoxes(graph, constraints).consistent
    report = detect_paradoxes(remove_event(graph, "a").graph, constraints)
    assert [(item.rule, item.event_ids) for item in report.violations] == [
        ("event_precondition", ("b", "a")), ("required_event", ("a",)),
    ]


def test_two_trips_can_leave_incompatible_assertions_without_a_cycle():
    graph = build_graph([
        Event("one", "First arrival", 1900, entities=("beacon",), state_changes=(StateChange("beacon", "power", "on"),)),
        Event("two", "Second arrival", 1900, entities=("beacon",), state_changes=(StateChange("beacon", "power", "off"),)),
        Event("later", "Departure", 2000),
    ], [])
    graph = travel_to_past(graph, "a", "later", "one").graph
    graph = travel_to_past(graph, "b", "later", "two").graph
    graph = prevent_travel(graph, "c").graph
    source = graph.copy()
    report = detect_paradoxes(graph)
    assert not report.cycles and not report.consistent
    assert [(item.rule, item.event_ids) for item in report.violations] == [("exclusive_state", ("one", "two"))]
    assert nx.utils.graphs_equal(graph, source)


def test_active_trip_with_unavailable_endpoint_is_a_conflict_until_cancelled():
    graph = build_graph([Event("a", "Arrival", 0, status=EventStatus.PREVENTED), Event("b", "Departure", 1)], [])
    graph = travel_to_past(graph, "trip", "b", "a").graph
    report = detect_paradoxes(graph)
    assert [(item.rule, item.relations) for item in report.violations] == [("active_travel", (("b", "a"),))]
    assert detect_paradoxes(cancel_travel(graph, "trip").graph).consistent


def test_state_assertions_at_different_times_or_from_prevented_events_do_not_conflict():
    def state_event(event, time, value, status=EventStatus.OCCURRED):
        return Event(event, event, time, entities=("beacon",), status=status,
                     state_changes=(StateChange("beacon", "power", value),))

    graph = build_graph([state_event("a", 0, "on"), state_event("b", 1, "off"),
                         state_event("c", 0, "off", EventStatus.PREVENTED)], [])
    assert detect_paradoxes(graph).consistent


@pytest.mark.parametrize("graph", [nx.Graph(), nx.MultiDiGraph()])
def test_non_directed_or_multigraph_inputs_are_rejected(graph):
    for analyze in (detect_paradoxes, find_cycle, strongly_connected_components):
        with pytest.raises(TypeError, match="simple directed graph"):
            analyze(graph)


def test_malformed_timeline_inputs_are_rejected():
    graph = nx.DiGraph()
    graph.add_node("no-metadata")
    with pytest.raises(ValueError, match="needs a time and label"):
        detect_paradoxes(graph)
    graph = build_graph([Event("a", "A", 0), Event("b", "B", 1)], [CausalRelation("a", "b")])
    graph.edges["a", "b"]["kind"] = "time_travel"
    with pytest.raises(ValueError, match="earlier target"):
        detect_paradoxes(graph)


def test_empty_graph():
    report = detect_paradoxes(nx.DiGraph())
    assert report.consistent and report.components == report.cycles == ()
