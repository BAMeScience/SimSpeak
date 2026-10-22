import pytest
from pydantic import ValidationError

from simspeak.models import SimulationSpec
from simspeak.specification import update_specification


def test_update_single_field():
    original = SimulationSpec(
        element="Si",
        cutoff_ev=400,
        xc_functional="PBE",
    )

    updated = update_specification(
        original,
        {"cutoff_ev": 500},
    )

    assert updated.cutoff_ev == 500
    assert updated.element == "Si"
    assert updated.xc_functional == "PBE"

    # Original object remains unchanged
    assert original.cutoff_ev == 400


def test_invalid_update():
    original = SimulationSpec()

    with pytest.raises(ValidationError):
        update_specification(
            original,
            {"cutoff_ev": -500},
        )


def test_unknown_field():
    original = SimulationSpec()

    with pytest.raises(ValidationError):
        update_specification(
            original,
            {"invented_parameter": 123},
        )


def test_change_engine():
    original = SimulationSpec(
        engine="gpaw",
        cutoff_ev=400,
    )

    updated = update_specification(
        original,
        {"engine": "quantum_espresso"},
    )

    assert updated.engine == "quantum_espresso"
    assert updated.cutoff_ev == 400
