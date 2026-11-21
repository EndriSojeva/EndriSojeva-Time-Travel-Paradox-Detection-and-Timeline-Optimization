from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from random import Random

import networkx as nx
import pytest

from timetravel.detection import detect_paradoxes
from timetravel.graph import build_graph, get_event
from timetravel.models import CausalRelation, Event, EventStatus, StateChange
from timetravel.operations import TravelStatus, travel_to_past
from timetravel.repair import EditKind, RepairEdit, RepairStatus, SearchLimits, default_edits, repair_timeline
from timetravel.scenarios import load_scenario

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


def beacon(event_id, value, cost=1):
    return Event(event_id, event_id, 1900, entities=("beacon",), modification_cost=cost,
                 state_changes=(StateChange("beacon", "power", value),))


@pytest.fixture
def conflict():
    return build_graph([beacon("a", "on"), beacon("b", "off")], [])


def brute_force(graph, catalog, rules=None, protected=frozenset()):
    """Test oracle: exhaust all feasible ordered prefixes, with no bound or memoization."""
    if detect_paradoxes(graph, rules).consistent:
        return Fraction(0)
    costs = []
    for i, edit in enumerate(catalog):
        try:
            result = edit.apply(graph, protected)
        except ValueError:
            continue
        continuation = brute_force(result.graph, catalog[:i] + catalog[i + 1:], rules, protected)
        if continuation is not None:
            costs.append(Fraction(str(result.cost)) + continuation)
    return min(costs, default=None)


@pytest.mark.parametrize("name", ["valid_timeline", "consistent_loop"])
@pytest.mark.parametrize("method", ["greedy", "branch_and_bound"])
def test_consistent_graph_needs_no_edits_even_if_cyclic(name, method):
    scenario = load_scenario(EXAMPLES / f"{name}.json")
    result = repair_timeline(scenario.graph, scenario.constraints, method=method, limits=SearchLimits(0, 0, 1))
    assert result.status == RepairStatus.ALREADY_CONSISTENT and result.optimality_proven
    assert result.best.total_cost == 0 and not result.best.edits
    assert result.metrics.candidates_explored == 0 and result.best.graph is not scenario.graph
    assert nx.utils.graphs_equal(result.best.graph, scenario.graph)


def test_greedy_is_more_expensive_than_the_oracle_on_three_conflicts():
    scenario = load_scenario(EXAMPLES / "repair_tradeoff.json")
    graph = scenario.graph
    rules = scenario.constraints
    greedy = repair_timeline(graph, rules, method="greedy", limits=SearchLimits(max_alternatives=1))
    exact = repair_timeline(graph, rules, limits=SearchLimits(max_alternatives=1))
    assert len(exact.initial_report.logical_violations) == 3
    assert greedy.status == RepairStatus.HEURISTIC and not greedy.optimality_proven
    assert greedy.best.total_cost == 6
    assert exact.status == RepairStatus.OPTIMAL and exact.optimality_proven
    assert exact.best.total_cost == brute_force(graph, default_edits(graph), rules) == 5
    assert exact.metrics.pruned > 0 and exact.metrics.greedy_candidates > 0
    assert greedy.best.report.consistent and detect_paradoxes(exact.best.graph, rules).consistent
    assert exact.best.changed_events == ("hub", "z")


def test_equal_cost_alternatives_are_deterministic_distinct_and_independent(conflict):
    previous = deepcopy(conflict)
    limits = SearchLimits(max_alternatives=2)
    a = repair_timeline(conflict, limits=limits)
    b = repair_timeline(conflict, limits=limits)
    assert [(x.id, x.changed_events, x.total_cost) for x in a.alternatives] == [
        ("timeline-1", ("a",), 1), ("timeline-2", ("b",), 1),
    ]
    assert [x.edits for x in a.alternatives] == [x.edits for x in b.alternatives]
    assert all(x.report.consistent and x.search_metrics == a.metrics for x in a.alternatives)
    a.best.graph.nodes["b"]["label"] = "Alternative only"
    assert conflict.nodes["b"]["label"] == "b" and a.alternatives[1].graph.nodes["a"]["label"] == "a"
    assert nx.utils.graphs_equal(conflict, previous)


def test_single_repair_with_protection_and_invalid_candidates(conflict):
    edits = [RepairEdit("remove_event", "a"), RepairEdit("remove_event", "missing"), RepairEdit("remove_event", "b")]
    result = repair_timeline(conflict, edits=edits, protected_events=["a"], use_greedy_bound=False)
    assert result.optimality_proven and len(result.alternatives) == 1
    assert result.best.changed_events == ("b",)
    assert result.metrics.invalid == 2 and result.metrics.candidates_explored == 3
    assert not detect_paradoxes(conflict).consistent


def test_no_solution_is_proven_only_by_exact_search(conflict):
    exact = repair_timeline(conflict, protected_events=["a", "b"])
    greedy = repair_timeline(conflict, protected_events=["a", "b"], method="greedy")
    assert exact.status == RepairStatus.NO_SOLUTION and exact.best is None
    assert greedy.status == RepairStatus.NO_IMPROVEMENT and greedy.best is None
    assert not exact.optimality_proven and exact.limit_reason is None


def test_candidate_limit_preserves_a_valid_incumbent_without_an_optimality_claim(conflict):
    result = repair_timeline(conflict, limits=SearchLimits(1, 10, 1))
    assert result.best.report.consistent
    assert result.status == RepairStatus.LIMIT_REACHED and result.limit_reason == "candidates"
    assert result.metrics.candidates_explored == 1 and not result.optimality_proven
    complete = repair_timeline(conflict, edits=(RepairEdit("remove_event", "b"),), limits=SearchLimits(1, 10, 1))
    assert complete.optimality_proven and complete.metrics.candidates_explored == 1


def test_time_limit_stops_before_any_attempt(conflict):
    result = repair_timeline(conflict, limits=SearchLimits(100, 0, 1))
    assert result.status == RepairStatus.LIMIT_REACHED and result.limit_reason == "time"
    assert result.best is None and not result.optimality_proven and not result.metrics.candidates_explored


def test_deadline_returns_best_valid_repair_found_before_stopping(conflict, monkeypatch):
    ticks = iter((0.0, 0.0, 0.0, 1.0))
    monkeypatch.setattr("timetravel.repair.monotonic", lambda: next(ticks, 1.0))
    result = repair_timeline(conflict, limits=SearchLimits(100, 1.0, 2), use_greedy_bound=False)
    assert result.status == RepairStatus.LIMIT_REACHED and result.limit_reason == "time"
    assert result.best.report.consistent and result.metrics.candidates_explored == 1
    assert not result.optimality_proven


def test_exact_search_can_take_a_nonimproving_edit_to_unlock_a_valid_reschedule():
    graph = build_graph([beacon("a", "on"), beacon("b", "off", 0.1), Event("c", "C", 1901)],
                        [CausalRelation("b", "c", 0.2)])
    options = (RepairEdit("reschedule_event", "b", 1902), RepairEdit("remove_relation", ("b", "c")))
    greedy = repair_timeline(graph, edits=options, method="greedy")
    exact = repair_timeline(graph, edits=options, protected_events=["a", "c"])
    assert greedy.status == RepairStatus.NO_IMPROVEMENT
    assert exact.optimality_proven and exact.best.total_cost == brute_force(graph, options) == Fraction("0.3")
    assert [edit.operation for edit in exact.best.edits] == ["remove_relation", "reschedule_event"]
    assert exact.best.changed_relations == (("b", "c"),) and exact.best.changed_events == ("b",)


def test_replacement_can_fix_grandfather_without_removing_any_event():
    scenario = load_scenario(EXAMPLES / "grandfather_paradox.json")
    event = Event("e0", "Survival restored", 1920, entities=("ancestor",), status=EventStatus.OCCURRED)
    result = repair_timeline(scenario.graph, scenario.constraints, protected_events=["e1", "e2"],
                             edits=[RepairEdit("modify_event", "e0", event)])
    assert result.optimality_proven and result.best.total_cost == 1
    assert len(result.best.report.cycles) == 1 and result.best.report.consistent
    assert len(result.best.graph) == len(scenario.graph)


def test_current_fee_changes_with_order_and_best_first_search_preserves_that(conflict):
    event = get_event(conflict, "a")
    free_event = replace(event, modification_cost=0)
    edits = (RepairEdit("reschedule_event", "a", 1901), RepairEdit("modify_event", "a", free_event))
    exact = repair_timeline(conflict, edits=edits)
    assert exact.best.total_cost == brute_force(conflict, edits) == 1
    assert len(exact.best.edits) == 1  # Same cost via a two-edit path, but the direct edit ranks first.


def test_rewiring_and_travel_cancellation_use_existing_rules():
    graph = build_graph([Event("a", "Unavailable", 0, status=EventStatus.PREVENTED),
                         Event("b", "Earlier", 0), Event("c", "Departure", 1)], [])
    graph = travel_to_past(graph, "trip", "c", "a", 4).graph
    edits = (RepairEdit("modify_relation", ("c", "a"), CausalRelation("c", "b", 2)),
             RepairEdit("cancel_travel", "trip", cost=3), RepairEdit("prevent_travel", "new_trip", cost=1))
    result = repair_timeline(graph, edits=edits, limits=SearchLimits(max_alternatives=2))
    assert [alt.total_cost for alt in result.alternatives] == [3, 4]
    assert result.best.graph.graph["travel_actions"]["trip"].status == TravelStatus.CANCELLED
    assert result.alternatives[1].graph.has_edge("c", "b") and graph.has_edge("c", "a")
    assert edits[2].apply(graph).graph.graph["travel_actions"]["new_trip"].status == TravelStatus.PREVENTED


@pytest.mark.parametrize("seed", range(12))
def test_exact_matches_exhaustive_search_for_small_generated_catalogs(seed):
    random = Random(seed)
    events = [beacon(str(i), random.choice(["on", "off"]), random.randint(0, 5)) for i in range(4)]
    graph = build_graph(events, [])
    catalog = (*default_edits(graph), RepairEdit("reschedule_event", "0", 1901))
    expected = brute_force(graph, catalog)
    result = repair_timeline(graph, edits=catalog, limits=SearchLimits(5_000, 10, 2), use_greedy_bound=bool(seed % 2))
    assert result.optimality_proven and result.best.total_cost == expected
    assert all(detect_paradoxes(option.graph).consistent for option in result.alternatives)


@pytest.mark.parametrize("edit", [
    lambda: RepairEdit("reschedule_event", "b", float("nan")),
    lambda: RepairEdit("remove_relation", "a"),
    lambda: RepairEdit("modify_event", "b", Event("c", "C", 1)),
    lambda: RepairEdit("prevent_travel", "trip", cost=-1),
])
def test_rejects_ill_formed_edit_catalog_entries(edit):
    with pytest.raises(ValueError):
        edit()


@pytest.mark.parametrize("args", [(-1, 1, 1), (1, float("inf"), 1), (1, 1, 0)])
def test_rejects_invalid_search_limits(args):
    with pytest.raises(ValueError):
        SearchLimits(*args)
