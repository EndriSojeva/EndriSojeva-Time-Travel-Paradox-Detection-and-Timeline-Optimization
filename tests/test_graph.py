import pytest

from timetravel.graph import build_graph
from timetravel.models import CausalRelation, Event


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
