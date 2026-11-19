import networkx as nx
import pytest

from timetravel.detection import detect_paradoxes


def test_detection_does_not_claim_unimplemented_validity():
    with pytest.raises(NotImplementedError):
        detect_paradoxes(nx.DiGraph(), [])
