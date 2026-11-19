"""Small reusable visualization helper."""

import matplotlib.pyplot as plt
import networkx as nx


def draw_timeline(graph: nx.DiGraph):
    figure, axis = plt.subplots(figsize=(8, 4))
    nx.draw_networkx(graph, pos=nx.spring_layout(graph, seed=42), ax=axis,
                     node_color="#b9d9ff", node_size=1100, arrows=True)
    axis.set_axis_off()
    return figure
