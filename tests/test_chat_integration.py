from unittest.mock import patch

from simspeak.chat_backend import process_simulation_message
from simspeak.llm.models import SimulationChanges
from simspeak.models import SimulationSpec


def test_chat_updates_specification():
    current = SimulationSpec(
        element="Si",
        cutoff_ev=400,
        xc_functional="PBE",
    )

    with patch(
        "simspeak.chat_backend.extract_changes",
        return_value=SimulationChanges(cutoff_ev=500),
    ):
        result = process_simulation_message(
            message="Increase cutoff to 500 eV",
            current_spec=current,
        )

    assert result.specification.cutoff_ev == 500
    assert result.specification.element == "Si"
    assert result.changes == {"cutoff_ev": 500}


def test_chat_preserves_manual_changes():
    current = SimulationSpec(
        element="Si",
        xc_functional="LDA",
        cutoff_ev=400,
    )

    with patch(
        "simspeak.chat_backend.extract_changes",
        return_value=SimulationChanges(kpoints=(8, 8, 8)),
    ):
        result = process_simulation_message(
            message="Use an 8x8x8 mesh",
            current_spec=current,
        )

    assert result.specification.xc_functional == "LDA"
    assert result.specification.kpoints == (8, 8, 8)
