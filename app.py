"""Streamlit shell for the academic timeline analysis project."""

from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

from timetravel.detection import detect_paradoxes
from timetravel.scenarios import load_scenario
from timetravel.visualization import draw_timeline

st.set_page_config(page_title="Time Travel Lab", page_icon="⏳", layout="wide")
st.sidebar.title("Time Travel Lab")
section = st.sidebar.radio("Workspace", ["Dashboard", "Graph Builder", "Paradox Detection",
                                        "Timeline Repair", "Algorithm Comparison", "Performance Analysis"])
st.title(section)
st.caption("Endri Sojeva · Time Travel Paradox Detection and Timeline Optimization")
if section == "Dashboard":
    st.info("Build a causal graph and check its consistency. Repair and performance experiments are planned.")
    st.markdown("Explore directed causal graphs in **Graph Builder**. A causal cycle alone does not establish a logical paradox.")
elif section in ("Graph Builder", "Paradox Detection"):
    examples = Path(__file__).parent / "data" / "examples"
    selected = st.selectbox("Illustrative scenario", sorted(p.name for p in examples.glob("*.json")))
    scenario = load_scenario(examples / selected)
    graph = scenario.graph
    st.write(scenario.description)
    st.caption(f"{graph.number_of_nodes()} events · {graph.number_of_edges()} causal relations")
    report = detect_paradoxes(graph, scenario.constraints) if section == "Paradox Detection" else None
    problems = {event for item in report.violations for event in item.event_ids} if report else set()
    cycle_edges = {relation for cycle in report.cycles for relation in cycle.relations} if report else set()
    figure = draw_timeline(graph, problem_nodes=problems, cycle_edges=cycle_edges)
    st.pyplot(figure)
    plt.close(figure)
    if report is None:
        st.json(scenario.data, expanded=False)
    else:
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
    st.info("Planned for Phase 2. No algorithm results or performance measurements are available yet.")
