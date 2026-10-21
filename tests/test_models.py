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


def test_default_specification():
    spec = SimulationSpec()

    assert spec.element is None
    assert spec.crystal_structure is None
    assert spec.lattice_parameter is None
    assert spec.calculation == "single_point"
    assert spec.xc_functional == "PBE"
    assert spec.engine == "quantum_espresso"


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        SimulationSpec(
            element="Si",
            unknown_parameter=123,
        )


def test_invalid_crystal_structure():
    with pytest.raises(ValidationError):
        SimulationSpec(crystal_structure="hexagonal")


def test_invalid_engine():
    with pytest.raises(ValidationError):
        SimulationSpec(engine="unsupported_code")


def test_invalid_lattice_parameter():
    with pytest.raises(ValidationError):
        SimulationSpec(lattice_parameter=-5.43)


def test_invalid_kpoints():
    with pytest.raises(ValidationError):
        SimulationSpec(kpoints=(4, 0, 4))


def test_element_whitespace_removed():
    spec = SimulationSpec(element="  Si  ")

    assert spec.element == "Si"


def test_json_roundtrip():
    spec = SimulationSpec(
        element="Si",
        crystal_structure="diamond",
        lattice_parameter=5.43,
        cutoff_ev=400,
        kpoints=(4, 4, 4),
        engine="gpaw",
    )

    json_data = spec.model_dump_json()

    restored = SimulationSpec.model_validate_json(json_data)

    assert restored == spec


def test_qe_requires_pseudopotential():
    spec = SimulationSpec(
        element="Si",
        crystal_structure="diamond",
        lattice_parameter=5.43,
        cutoff_ev=400,
        kpoints=(4, 4, 4),
        engine="quantum_espresso",
    )

    issues = generation_issues(spec)

    assert any("pseudopotential" in issue.lower() for issue in issues)


def test_valid_gpaw_specification():
    spec = SimulationSpec(
        element="Si",
        crystal_structure="diamond",
        lattice_parameter=5.43,
        cutoff_ev=400,
        kpoints=(4, 4, 4),
        engine="gpaw",
    )

    assert generation_issues(spec) == []
