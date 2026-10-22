from simspeak.llm.models import SimulationChanges


def test_partial_extraction():
    changes = SimulationChanges(cutoff_ev=500)

    assert changes.get_changes() == {"cutoff_ev": 500}


def test_empty_extraction():
    changes = SimulationChanges()

    assert changes.get_changes() == {}


def test_kpoint_extraction():
    changes = SimulationChanges(kpoints=(6, 6, 6))

    assert changes.get_changes() == {"kpoints": [6, 6, 6]}
