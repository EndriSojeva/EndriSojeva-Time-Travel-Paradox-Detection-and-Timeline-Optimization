"""Streamlit shell for the academic timeline analysis project."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from timetravel.detection import detect_paradoxes
from timetravel.repair import RepairStatus, SearchLimits, repair_timeline
from timetravel.scenarios import load_scenario
from timetravel.visualization import draw_timeline


def show_graph(graph, report=None):
    problems = {event for item in report.violations for event in item.event_ids} if report else set()
    cycle_edges = {relation for cycle in report.cycles for relation in cycle.relations} if report else set()
    figure = draw_timeline(graph, problem_nodes=problems, cycle_edges=cycle_edges)
    st.pyplot(figure)
    plt.close(figure)


def show_repair(scenario, filename):
    graph = scenario.graph
    report = detect_paradoxes(graph, scenario.constraints)
    st.subheader("Original timeline")
    if report.violations:
        for item in report.violations:
            st.write(f"**{item.rule}** · {item.explanation}")
    else:
        st.success("The original timeline is consistent under the selected rules.")

    with st.form("repair_options"):
        method = st.selectbox("Algorithm", ["Branch and Bound", "Greedy"])
        protected = st.multiselect("Protected events", list(graph))
        first, second, third = st.columns(3)
        candidates = first.number_input("Max candidates", min_value=0, max_value=50_000, value=5_000)
        seconds = second.number_input("Max search seconds", min_value=0.0, max_value=60.0, value=5.0)
        alternatives = third.number_input("Max alternatives returned", min_value=1, max_value=10, value=3)
        submitted = st.form_submit_button("Find repairs")
    result_key = f"repair-result:{filename}"
    if submitted:
        st.session_state[result_key] = repair_timeline(
            graph, scenario.constraints, protected_events=protected,
            method="greedy" if method == "Greedy" else "branch_and_bound",
            limits=SearchLimits(candidates, seconds, alternatives),
        )
    result = st.session_state.get(result_key)
    if result is None:
        show_graph(graph, report)
        return

    labels = {
        RepairStatus.ALREADY_CONSISTENT: "Already consistent at zero cost",
        RepairStatus.HEURISTIC: "Valid Greedy repair. Global optimality is unproven.",
        RepairStatus.OPTIMAL: "Minimum repair cost proven for the current edit catalog",
        RepairStatus.NO_IMPROVEMENT: "Greedy found no valid repair along its descent",
        RepairStatus.NO_SOLUTION: "No valid repair exists in the current edit catalog",
        RepairStatus.LIMIT_REACHED: f"Search stopped at the {result.limit_reason} limit. Optimality is unproven.",
    }
    st.info(labels[result.status])
    metrics = result.metrics
    columns = st.columns(3)
    columns[0].metric("Candidates explored", metrics.candidates_explored)
    columns[1].metric("States expanded", metrics.expanded)
    columns[2].metric("Pruned", metrics.pruned)
    if result.best is None:
        show_graph(graph, report)
        return

    choices = {alt.id: alt for alt in result.alternatives}
    selected = st.selectbox("Repair alternative", list(choices), disabled=len(choices) == 1)
    alternative = choices[selected]
    st.metric("Total repair cost", str(alternative.total_cost))
    st.caption(f"Changed events: {', '.join(alternative.changed_events) or 'none'}")
    changed = ", ".join(f"{a} → {b}" for a, b in alternative.changed_relations)
    st.caption(f"Changed relations: {changed or 'none'}")
    if alternative.edits:
        st.table([{"Operation": edit.operation, "Cost": edit.cost,
                   "Target": getattr(edit.before or edit.after, "id", None)
                   or f"{edit.before.source} → {edit.before.target}"}
                  for edit in alternative.edits])
    left, right = st.columns(2)
    with left:
        st.markdown("**Original**")
        show_graph(graph, report)
    with right:
        st.markdown("**Repaired · consistent**")
        show_graph(alternative.graph, alternative.report)


def show_benchmarks(section):
    reference = Path(__file__).parent / "results" / "reference"
    if not (reference / "summary.csv").is_file():
        st.info("Run the benchmark to generate the reference tables and figures.")
        return
    environment = json.loads((reference / "environment.json").read_text(encoding="utf-8"))
    data = pd.read_csv(reference / "summary.csv")
    data["runtime_ms"] = data["runtime_seconds_median"] * 1_000
    data["peak_python_kib"] = data["peak_python_bytes_median"] / 1024
    st.caption(f"Source {environment['source_sha'][:12]} · Python {environment['python']} · "
               f"{environment['repetitions']} trials per configuration")
    if section == "Algorithm Comparison":
        traversal = data[data["algorithm"].isin(["dfs", "tarjan"])]
        st.caption("DFS finds one cycle witness. Tarjan returns the full SCC partition.")
        st.dataframe(traversal[["scenario", "algorithm", "events", "relations", "runtime_ms", "peak_python_kib"]],
                     hide_index=True)
        columns = ["scenario", "algorithm", "cost_median", "proven_trials", "candidates_explored_median",
                   "runtime_ms", "peak_python_kib", "statuses"]
        st.dataframe(data[data["suite"] == "repair"][columns], hide_index=True)
        st.image(str(reference / "figures" / "repair_costs.png"))
        st.caption("A missing cost indicates that no feasible result was returned. A capped search does not prove optimality.")
    else:
        st.image(str(reference / "figures" / "detection_scaling.png"))
        st.image(str(reference / "figures" / "repair_search.png"))
        columns = ["scenario", "algorithm", "events", "relations", "correct_trials", "runtime_ms", "peak_python_kib"]
        st.dataframe(data[data["suite"] == "detection"][columns], hide_index=True)
        st.caption("Memory shows peak Python allocations tracked by tracemalloc, in KiB. It is not process RAM.")


st.set_page_config(page_title="Time Travel Lab", page_icon="⏳", layout="wide")
st.sidebar.title("Time Travel Lab")
section = st.sidebar.radio("Workspace", ["Dashboard", "Graph Builder", "Paradox Detection",
                                        "Timeline Repair", "Algorithm Comparison", "Performance Analysis"])
st.title(section)
st.caption("Endri Sojeva · Time Travel Paradox Detection and Timeline Optimization")
if section == "Dashboard":
    st.info("Build a causal graph, check its consistency and compare repair strategies.")
    st.markdown("Explore directed causal graphs in **Graph Builder**. A causal cycle alone does not establish a logical paradox.")
elif section in ("Graph Builder", "Paradox Detection", "Timeline Repair"):
    examples = Path(__file__).parent / "data" / "examples"
    selected = st.selectbox("Illustrative scenario", sorted(p.name for p in examples.glob("*.json")))
    scenario = load_scenario(examples / selected)
    graph = scenario.graph
    st.write(scenario.description)
    st.caption(f"{graph.number_of_nodes()} events · {graph.number_of_edges()} causal relations")
    if section == "Timeline Repair":
        show_repair(scenario, selected)
    elif section == "Graph Builder":
        show_graph(graph)
        st.json(scenario.data, expanded=False)
    else:
        report = detect_paradoxes(graph, scenario.constraints)
        show_graph(graph, report)
        st.caption("Red nodes mark conflicts. Purple edges mark cycle witnesses.")
        if report.consistent:
            st.success("Consistent under the selected rules")
        else:
            st.error("Inconsistent under the selected rules")
        st.subheader("Causal cycles")
        st.caption(f"{len(report.components)} strongly connected components")
        if report.cycles:
            for cycle in report.cycles:
                st.write(" → ".join(cycle.event_ids))
        else:
            st.write("No causal cycle found.")
        st.subheader("Consistency violations")
        if not report.violations:
            st.write("No consistency violations found.")
        for item in report.violations:
            st.markdown(f"**{item.kind.value.title()} · `{item.rule}`**")
            st.write(item.explanation)
            st.caption("Events: " + ", ".join(
                f"{event} ({graph.nodes[event]['label']})" if event in graph else f"{event} (missing)"
                for event in item.event_ids))
            if item.relations:
                st.caption("Relations: " + ", ".join(f"{source} → {target}" for source, target in item.relations))
else:
    show_benchmarks(section)
