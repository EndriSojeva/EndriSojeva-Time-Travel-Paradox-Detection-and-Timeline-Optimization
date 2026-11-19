"""Streamlit shell for the academic timeline analysis project."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

from timetravel.graph import build_graph
from timetravel.models import CausalRelation, Event
from timetravel.visualization import draw_timeline

st.set_page_config(page_title="Time Travel Lab", page_icon="⏳", layout="wide")
st.sidebar.title("Time Travel Lab")
section = st.sidebar.radio("Workspace", ["Dashboard", "Graph Builder", "Paradox Detection",
                                        "Timeline Repair", "Algorithm Comparison", "Performance Analysis"])
st.title(section)
st.caption("Endri Sojeva · Time Travel Paradox Detection and Timeline Optimization")
if section == "Dashboard":
    st.info("The timeline model supports causal links and time-travel edits. Detection, repair and experiments are planned.")
    st.markdown("Explore directed causal graphs in **Graph Builder**. A causal cycle alone does not establish a logical paradox.")
elif section == "Graph Builder":
    examples = Path(__file__).parent / "data" / "examples"
    selected = st.selectbox("Illustrative scenario", sorted(p.name for p in examples.glob("*.json")))
    data = json.loads((examples / selected).read_text(encoding="utf-8"))
    st.write(data["description"])
    graph = build_graph([Event(**e) for e in data["events"]],
                        [CausalRelation(**r) for r in data["relations"]])
    st.caption(f"{graph.number_of_nodes()} events · {graph.number_of_edges()} causal relations")
    figure = draw_timeline(graph)
    st.pyplot(figure)
    plt.close(figure)
    st.json(data, expanded=False)
else:
    st.info("Planned for Phase 2. No algorithm results or performance measurements are available yet.")
