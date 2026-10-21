import pytest
from pydantic import ValidationError

from simspeak.form import parse_form
from simspeak.models import SimulationSpec, generation_issues

VALID_FORM = {
    "element": "Si",
    "crystal_structure": "diamond",
    "lattice_parameter": "5.43",
    "calculation": "single_point",
    "xc_functional": "PBE",
    "cutoff_ev": "400",
    "kpoints": "4 x 4 x 4",
    "engine": "gpaw",
}


def test_form_to_schema():
    spec = parse_form(VALID_FORM)
    assert spec.kpoints == (4, 4, 4)
    assert spec.lattice_parameter == 5.43
    assert generation_issues(spec) == []


def test_incomplete_draft_allowed():
    assert SimulationSpec().element is None
    assert "Element" in generation_issues(SimulationSpec())


def test_invalid_cutoff_rejected():
    with pytest.raises(ValidationError):
        parse_form({**VALID_FORM, "cutoff_ev": "-1"})


def test_invalid_mesh_rejected():
    with pytest.raises(ValueError):
        parse_form({**VALID_FORM, "kpoints": "4 4"})


def test_invalid_mesh_negative_rejected():
    with pytest.raises(ValidationError):
        parse_form({**VALID_FORM, "kpoints": "4 -2 4"})
