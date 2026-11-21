"""Run reproducible detection and repair trials, and export CSV and PNG evidence."""

import argparse
import json
import os
import platform
import re
import subprocess
import tracemalloc
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from importlib.metadata import version
from math import perm
from pathlib import Path
from time import perf_counter

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from timetravel.algorithms.dfs import find_cycle
from timetravel.algorithms.tarjan import strongly_connected_components
from timetravel.detection import detect_paradoxes
from timetravel.repair import EditKind, RepairEdit, SearchLimits, default_edits, repair_timeline
from timetravel.scenarios import load_scenario

from .generate_scenarios import ScenarioSpec, generate_scenario


def _samples(functions, repetitions):
    """Alternate algorithm order, and measure allocations on an untimed replay."""
    for repetition in range(1, repetitions + 1):
        names = list(functions)
        if repetition % 2 == 0:
            names.reverse()
        for name in names:
            call = functions[name]
            start = perf_counter()
            result = call()
            elapsed = perf_counter() - start
            tracemalloc.start()
            try:
                replay = call()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            yield name, repetition, result, replay, elapsed, peak


def raw_prefix_count(size):
    return sum(perm(size, length) for length in range(1, size + 1))


def _percent(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def exhaustive_oracle(graph, rules, edits, protected=()):
    """Count feasible-prefix search attempts without any pruning, up to six edits."""
    if len(edits) > 6:
        raise ValueError("Oracle is limited to six options")
    attempts = 0
    protected_set = frozenset(protected)

    def visit(current, remaining):
        nonlocal attempts
        if detect_paradoxes(current, rules).consistent:
            return Fraction(0)
        best = None
        for index, edit in enumerate(remaining):
            attempts += 1
            try:
                applied = edit.apply(current, protected_set)
            except ValueError:
                continue
            suffix = visit(applied.graph, remaining[:index] + remaining[index + 1:])
            if suffix is not None:
                cost = Fraction(str(applied.cost)) + suffix
                best = cost if best is None else min(best, cost)
        return best

    return visit(graph, tuple(edits)), attempts


def _graph_fields(graph):
    return {"events": len(graph), "relations": graph.number_of_edges(), "edge_density": nx.density(graph)}


def _detection_cases(profile):
    if profile == "smoke":
        sizes, densities, seeds = (10,), (0.005,), (42,)
    elif profile == "comparison":
        sizes, densities, seeds = (10, 100, 400), (0.005, 0.025), (42,)
    else:
        sizes, densities, seeds = (10, 100, 500, 2_000), (0.005, 0.025), (42, 73)
    for size in sizes:
        for density in densities:
            for seed in seeds:
                yield f"dag-{size}-{density:g}-{seed}", "dag", ScenarioSpec(size, density, seed)
    yield "consistent-travel", "travel", ScenarioSpec(40, 0.035, 42, trips=10)
    yield "mixed-paradoxes", "mixed", ScenarioSpec(40, 0.035, 73, conflicts=6, trips=8, protected=3)
    yield "random-backward", "random", ScenarioSpec(100, 0.04, 73, conflicts=3, random_back_edges=12)


def _detection_rows(profile, repetitions):
    for name, family, spec in _detection_cases(profile):
        scenario = generate_scenario(spec)
        graph = scenario.graph
        reference = {frozenset(group) for group in nx.strongly_connected_components(graph)}
        cyclic_count = sum(len(group) > 1 or any(graph.has_edge(node, node) for node in group) for group in reference)
        expected_cycles = scenario.expected_cycles
        if expected_cycles is not None and expected_cycles != cyclic_count:
            raise AssertionError(f"Generated truth disagrees with NetworkX: {name}")
        functions = {"dfs": lambda: find_cycle(graph), "tarjan": lambda: strongly_connected_components(graph),
                     "detector": lambda: detect_paradoxes(graph)}
        for method, trial, result, replay, elapsed, peak in _samples(functions, repetitions):
            if method == "dfs":
                correct = (result is not None) == bool(cyclic_count) and (result is None or (
                    result[0] == result[-1] and all(graph.has_edge(a, b) for a, b in zip(result, result[1:]))))
            elif method == "tarjan":
                correct = {frozenset(group) for group in result} == reference
            else:
                correct = (len(result.cyclic_components) == cyclic_count
                           and len(result.violations) == scenario.expected_violations
                           and result.consistent == (scenario.expected_violations == 0))
            if not correct or result != replay:
                raise AssertionError(f"Detection disagrees with expected result: {name}/{method}")
            yield {"suite": "detection", "scenario": name, "family": family, "algorithm": method,
                   **_graph_fields(graph), "seed": spec.seed, "edge_probability": spec.edge_probability,
                   "scenario_parameters": json.dumps(asdict(spec)), "trial": trial, "runtime_seconds": elapsed,
                   "peak_python_bytes": peak, "cyclic_components": cyclic_count,
                   "contradictions": scenario.expected_violations, "truth_match": correct,
                   "truth_source": "declared+networkx" if expected_cycles is not None else "networkx+declared_states"}


def _repair_cases(profile, examples):
    standard = SearchLimits(4_000, 8.0, 1)
    for name, fixture, protected, limits in (
        ("repair_tradeoff", "repair_tradeoff", (), standard),
        ("grandfather", "grandfather_paradox", (), standard),
        ("consistent_loop", "consistent_loop", (), standard),
        ("protected", "contradictory_timeline", ("report_a", "report_b"), standard),
        ("candidate_limit", "repair_tradeoff", (), SearchLimits(4, 8, 1)),
        ("time_limit", "repair_tradeoff", (), SearchLimits(4_000, 0, 1)),
    ):
        scenario = load_scenario(examples / f"{fixture}.json")
        yield name, "fixture", scenario.graph, scenario.constraints, default_edits(scenario.graph, protected), \
            protected, limits, {"fixture": fixture}
    groups = (1, 2) if profile == "smoke" else (1, 2, 3, 4, 5)
    for count in groups:
        spec = ScenarioSpec(10, 0.05, 42 + count, conflicts=count, protected=1 if count < 5 else 0)
        scenario = generate_scenario(spec)
        edits = tuple(RepairEdit(EditKind.REMOVE_EVENT, node) for node in scenario.conflict_events)
        yield f"{count}-conflicts", "conflict-sweep", scenario.graph, None, edits, scenario.protected_events, \
            SearchLimits(1000, 8, 1), asdict(spec)


def _repair_rows(profile, repetitions, examples):
    for name, family, graph, rules, edits, protected, limits, parameters in _repair_cases(profile, examples):
        initial = detect_paradoxes(graph, rules)
        has_oracle = len(edits) <= 6
        oracle, oracle_attempts = exhaustive_oracle(graph, rules, edits, protected) if has_oracle else (None, None)
        tiny = len(edits) <= 8
        functions = {method: (lambda method=method: repair_timeline(
            graph, rules, edits=edits, protected_events=protected, method=method,
            limits=limits, track_prefix_pruning=tiny and method == "branch_and_bound",
        )) for method in ("greedy", "branch_and_bound")}
        for method, trial, result, replay, elapsed, peak in _samples(functions, repetitions):
            valid = result.best is None or detect_paradoxes(result.best.graph, rules).consistent
            cost = result.best.total_cost if result.best else None
            if not valid or (has_oracle and result.optimality_proven and cost != oracle):
                raise AssertionError(f"Invalid or mismatched repair: {name}/{method}")
            if has_oracle and result.status == "no_solution" and oracle is not None:
                raise AssertionError(f"Missed feasible repair: {name}")
            stats = result.metrics
            cuts = stats.bound_pruned + stats.dominance_pruned
            total_raw = raw_prefix_count(len(edits)) if tiny and method == "branch_and_bound" else None
            skipped = stats.raw_prefix_descendants_pruned
            yield {"suite": "repair", "scenario": name, "family": family, "algorithm": method,
                   **_graph_fields(graph), "seed": parameters.get("seed"), "scenario_parameters": json.dumps(parameters),
                   "trial": trial, "runtime_seconds": elapsed, "peak_python_bytes": peak,
                   "cyclic_components": len(initial.cyclic_components), "contradictions": len(initial.violations),
                   "cost": float(cost) if cost is not None else None, "cost_exact": str(cost) if cost is not None else None,
                   "optimality_proven": result.optimality_proven, "status": result.status.value,
                   "limit_reason": result.limit_reason, "memory_replay_status": replay.status.value,
                   "memory_replay_candidates": replay.metrics.candidates_explored, "catalog_entries": len(edits),
                   "protected_events": json.dumps(protected), "max_candidates": limits.max_candidates,
                   "max_seconds": limits.max_seconds, "max_alternatives": limits.max_alternatives,
                   "greedy_preview_enabled": method == "branch_and_bound",
                   "candidates_explored": stats.candidates_explored, "expanded": stats.expanded,
                   "pruned": stats.pruned, "invalid": stats.invalid, "greedy_candidates": stats.greedy_candidates,
                   "exact_expanded": stats.exact_expanded, "bound_pruned": stats.bound_pruned,
                   "dominance_pruned": stats.dominance_pruned,
                   "exact_prefix_discard_share_pct": _percent(cuts, cuts + stats.exact_expanded),
                   "raw_prefix_space": total_raw, "raw_prefix_descendants_pruned": skipped,
                   "raw_prefix_space_pruned_pct": _percent(skipped, total_raw) if skipped is not None else None,
                   "oracle_checked": has_oracle, "oracle_cost_exact": str(oracle) if oracle is not None else None,
                   "oracle_attempts": oracle_attempts}


def summarize(frame):
    keys = ["suite", "scenario", "family", "algorithm"]
    numeric = ("runtime_seconds", "peak_python_bytes", "cost", "expanded", "candidates_explored", "pruned",
               "exact_prefix_discard_share_pct", "raw_prefix_space_pruned_pct", "oracle_attempts")
    fields = ("events", "relations", "edge_density", "edge_probability", "contradictions", "cyclic_components",
              "truth_source", "catalog_entries", "max_candidates", "max_seconds", "oracle_cost_exact")
    rows = []
    for group_keys, group in frame.groupby(keys, sort=False):
        row = dict(zip(keys, group_keys, strict=True)) | {field: group[field].iloc[0] for field in fields}
        row["trials"] = len(group)
        row["correct_trials"] = int(group["truth_match"].eq(True).sum()) if row["suite"] == "detection" else None
        row["proven_trials"] = int(group["optimality_proven"].eq(True).sum()) if row["suite"] == "repair" else None
        row["statuses"] = json.dumps(dict(Counter(group["status"].dropna())))
        for metric in numeric:
            sample = group[metric].dropna()
            for label, q in (("min", 0), ("q1", 0.25), ("median", 0.5), ("q3", 0.75), ("max", 1)):
                row[f"{metric}_{label}"] = sample.quantile(q) if len(sample) else None
        rows.append(row)
    return pd.DataFrame(rows)


def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def write_figures(frame, summary, output):
    detection = frame[frame["family"] == "dag"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for ax, field, scale, label in zip(axes, ("runtime_seconds", "peak_python_bytes"), (1_000, 1 / 1024),
                                        ("Median runtime (ms)", "Median peak Python allocations (KiB)"), strict=True):
        for (method, density), group in detection.groupby(["algorithm", "edge_probability"]):
            stats = group.groupby("events")[field].quantile([0.25, 0.5, 0.75]).unstack() * scale
            ax.plot(stats.index, stats[0.5], "o-", label=f"{method}, p={density:g}")
            ax.fill_between(stats.index, stats[0.25], stats[0.75], alpha=0.10)
        ax.set(xlabel="Events", ylabel=label, xscale="log", yscale="log")
    axes[0].legend(fontsize=7)
    fig.suptitle("Acyclic graphs · median and interquartile range")
    _save(fig, output / "detection_scaling.png")

    chosen = summary[summary["scenario"].isin(["repair_tradeoff", "grandfather", "consistent_loop"])]
    cost = chosen.pivot(index="scenario", columns="algorithm", values="cost_median")
    fig, ax = plt.subplots(figsize=(7, 3.7), layout="constrained")
    cost.rename(columns={"branch_and_bound": "Branch-and-Bound", "greedy": "Greedy"}).plot.bar(ax=ax, rot=0)
    ax.set(xlabel="Scenario", ylabel="Median feasible cost (units)", title="Repair costs on reference fixtures")
    _save(fig, output / "repair_costs.png")

    sweep = summary[summary["family"] == "conflict-sweep"].sort_values("contradictions")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), layout="constrained")
    for name, group in sweep.groupby("algorithm"):
        axes[0].plot(group["contradictions"], group["candidates_explored_median"], "o-", label=name)
    exact = sweep[sweep["algorithm"] == "branch_and_bound"]
    axes[1].plot(exact["contradictions"], exact["exact_prefix_discard_share_pct_median"], "o-", label="Exact decisions")
    axes[1].plot(exact["contradictions"], exact["raw_prefix_space_pruned_pct_median"], "s--", label="Raw prefixes (small catalogs)")
    axes[0].set(ylabel="Median candidate attempts", xlabel="Initial contradictions", yscale="log")
    axes[1].set(ylabel="Pruning share (%)", xlabel="Initial contradictions", ylim=(0, 100))
    for ax in axes:
        ax.legend(fontsize=8)
    fig.suptitle("Repair demand as the number of conflicts increases")
    _save(fig, output / "repair_search.png")


def run_benchmark(output, *, profile="full", repetitions=3, source_sha=None, examples=None):
    if profile not in ("full", "comparison", "smoke") or type(repetitions) is not int or repetitions < 1:
        raise ValueError("Invalid benchmark profile or repetition count")
    if tracemalloc.is_tracing():
        raise RuntimeError("Stop existing tracemalloc tracing before benchmarking")
    source_dirty = False
    if source_sha is None:
        source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        source_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    if re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise ValueError("A full Git SHA is required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    examples = Path(examples) if examples is not None else Path(__file__).resolve().parents[1] / "data" / "examples"
    rows = [*_detection_rows(profile, repetitions), *_repair_rows(profile, repetitions, examples)]
    frame = pd.DataFrame(rows)
    summary = summarize(frame)
    frame.insert(0, "source_sha", source_sha)
    summary.insert(0, "source_sha", source_sha)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    frame.to_csv(output / "raw.csv", index=False)
    summary.to_csv(output / "summary.csv", index=False)
    (output / "environment.json").write_text(json.dumps({
        "source_sha": source_sha, "source_dirty": source_dirty, "profile": profile, "repetitions": repetitions,
        "python": platform.python_version(), "system": platform.platform(), "machine": platform.machine(),
        "logical_cpus": os.cpu_count(), "environment": "kaggle" if Path("/kaggle/working").is_dir() else "local",
        "libraries": {name: version(name) for name in ("networkx", "numpy", "pandas", "matplotlib")},
    }, indent=2) + "\n", encoding="utf-8")
    write_figures(frame, summary, figures)
    return frame, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/latest"))
    parser.add_argument("--profile", choices=("full", "comparison", "smoke"), default="full")
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    frame, summary = run_benchmark(args.output, profile=args.profile, repetitions=args.repetitions)
    print(f"Saved {len(frame)} trials and {len(summary)} summaries to {args.output}")

if __name__ == "__main__":
    main()
