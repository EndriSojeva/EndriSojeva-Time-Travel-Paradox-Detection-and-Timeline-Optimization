"""Small reusable visualization helper."""

import matplotlib.pyplot as plt
import networkx as nx


def draw_timeline(graph: nx.DiGraph, *, problem_nodes=(), cycle_edges=()):
    figure, axis = plt.subplots(figsize=(8, 4))
    problems = set(problem_nodes)
    loops = set(cycle_edges)
    nx.draw_networkx(graph, pos=nx.spring_layout(graph, seed=42), ax=axis,
                     node_color=["#ffa69e" if node in problems else "#b9d9ff" for node in graph],
                     edge_color=["#8b4eb5" if edge in loops else "#46546a" for edge in graph.edges],
                     node_size=1100, arrows=True)
    axis.set_axis_off()
    return figure
