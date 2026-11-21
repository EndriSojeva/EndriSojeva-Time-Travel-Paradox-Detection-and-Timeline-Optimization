import csv
import json
from pathlib import Path
from subprocess import run
import sys

import networkx as nx
import nbformat
import pytest
from nbclient import NotebookClient

from experiments.benchmark import exhaustive_oracle, raw_prefix_count, run_benchmark
from experiments.generate_scenarios import ScenarioSpec, generate_scenario
from timetravel.detection import detect_paradoxes
from timetravel.graph import build_graph
from timetravel.models import Event, StateChange
from timetravel.repair import SearchLimits, default_edits, repair_timeline
from timetravel.scenarios import load_scenario

ROOT = Path(__file__).resolve().parents[1]

def test_seeded_generation_is_deterministic_and_matches_declared_counts():
    spec = ScenarioSpec(30, 0.3, 42, conflicts=3, trips=7, protected=4)
    first, second = (generate_scenario(spec) for _ in range(2))
    assert nx.utils.graphs_equal(first.graph, second.graph)
    assert first.protected_events == second.protected_events and len(first.protected_events) == 4
    report = detect_paradoxes(first.graph)
    assert len(report.cyclic_components) == first.expected_cycles == 7
    assert len(report.violations) == first.expected_violations == 3
    assert len(first.graph.graph["travel_actions"]) == 7
    random = generate_scenario(ScenarioSpec(20, 0.2, 42, random_back_edges=3))
    assert random.expected_cycles is None
    assert random.expected_violations == 0 and detect_paradoxes(random.graph).consistent


def test_generator_cli_preserves_named_trips_on_reload(tmp_path):
    path = tmp_path / "generated.json"
    run([sys.executable, "-m", "experiments.generate_scenarios", "--size", "12", "--trips", "2",
         "--conflicts", "1", "--seed", "73", "--protected", "2", "--output", str(path)], check=True)
    scenario = load_scenario(path)
    report = detect_paradoxes(scenario.graph, scenario.constraints)
    assert (len(report.cycles), len(report.violations)) == (2, 1)
    assert len(scenario.graph.graph["travel_actions"]) == 2
    assert scenario.data["parameters"]["seed"] == 73
    assert len(scenario.data["protected_events"]) == 2


def test_pruning_counts_disjoint_unvisited_raw_descendants():
    events = [Event(key, key, 0, entities=("beacon",),
                    state_changes=(StateChange("beacon", "power", value),), modification_cost=cost)
              for key, value, cost in (("a", "on", 1), ("b", "off", 2))]
    graph = build_graph([*events, Event("c", "Context", 1, modification_cost=100)], [])
    oracle, exhaustive_attempts = exhaustive_oracle(graph, None, default_edits(graph))
    result = repair_timeline(graph, limits=SearchLimits(max_alternatives=1),
                             use_greedy_bound=False, track_prefix_pruning=True)
    stats = result.metrics
    assert result.best.total_cost == oracle == 1
    assert stats.bound_pruned == 2 and stats.exact_expanded == 1 and stats.dominance_pruned == 0
    assert stats.raw_prefix_descendants_pruned == raw_prefix_count(2) == 4
    assert raw_prefix_count(3) == 15
    assert stats.candidates_explored == 3 and exhaustive_attempts == 5


def test_smoke_benchmark_exports_reconcilable_raw_rows_and_figures(tmp_path):
    sha = "a" * 40
    raw, summary = run_benchmark(tmp_path, profile="smoke", repetitions=3, source_sha=sha)
    with (tmp_path / "raw.csv").open(encoding="utf-8", newline="") as source:
        assert len(list(csv.DictReader(source))) == len(raw)
    assert set(raw.source_sha) == {sha}
    assert (summary.trials == 3).all() and summary.trials.sum() == len(raw)
    elapsed = raw[(raw.scenario == "repair_tradeoff") & (raw.algorithm == "greedy")].runtime_seconds
    sample = summary[(summary.scenario == "repair_tradeoff") & (summary.algorithm == "greedy")].iloc[0]
    assert sample.runtime_seconds_median == pytest.approx(elapsed.median())
    assert sample.runtime_seconds_q1 <= sample.runtime_seconds_median <= sample.runtime_seconds_q3
    assert (raw.peak_python_bytes > 0).all()
    exact = raw[(raw.scenario == "repair_tradeoff") & (raw.algorithm == "branch_and_bound")]
    assert (exact.cost_exact == exact.oracle_cost_exact).all() and exact.optimality_proven.all()
    limited = raw[raw.scenario.isin(["candidate_limit", "time_limit"])]
    assert set(limited.status) == {"limit_reached"} and not limited.optimality_proven.any()
    assert (raw[raw.scenario == "protected"].cost.isna()).all()
    metadata = json.loads((tmp_path / "environment.json").read_text(encoding="utf-8"))
    assert metadata["source_sha"] == sha and metadata["repetitions"] == 3
    for name in ("detection_scaling", "repair_costs", "repair_search"):
        assert (tmp_path / "figures" / f"{name}.png").read_bytes().startswith(b"\x89PNG")


@pytest.mark.parametrize("filename", ["04_Algorithm_Comparison.ipynb", "05_Performance_Analysis.ipynb"])
def test_benchmark_notebook_runs_with_smoke_profile(filename, monkeypatch, tmp_path):
    monkeypatch.setenv("TIMETRAVEL_BENCHMARK_PROFILE", "smoke")
    notebook = nbformat.read(ROOT / "notebooks" / filename, as_version=4)
    nbformat.validate(notebook)
    notebook.cells.insert(0, nbformat.v4.new_code_cell(
        f"from pathlib import Path\nRESULTS_DIR = Path({str(tmp_path)!r})\nSOURCE_COMMIT = {'a' * 40!r}",
    ))
    NotebookClient(notebook, timeout=90, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT / "notebooks")}}).execute()
    outputs = [out for cell in notebook.cells for out in cell.get("outputs", [])]
    assert sum("image/png" in out.get("data", {}) for out in outputs) == 2
    assert sum("text/html" in out.get("data", {}) for out in outputs) >= 2
    run_dir = tmp_path / f"notebook-{filename[:2]}"
    assert (run_dir / "raw.csv").is_file() and (run_dir / "summary.csv").is_file()
