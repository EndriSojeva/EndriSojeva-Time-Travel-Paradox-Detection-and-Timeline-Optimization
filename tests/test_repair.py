import networkx as nx
import pytest

from timetravel.repair import repair_timeline


def test_repair_does_not_claim_unimplemented_optimality():
    with pytest.raises(NotImplementedError):
        repair_timeline(nx.DiGraph())
