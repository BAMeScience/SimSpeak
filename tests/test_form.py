import pytest
from pydantic import ValidationError

from simspeak.form import optional_float, optional_mesh, parse_form

VALID_FORM = {
    "element": "Si",
    "crystal_structure": "diamond",
    "lattice_parameter": "5.43",
    "calculation": "single_point",
    "xc_functional": "PBE",
    "cutoff_ev": "400",
    "kpoints": "4 4 4",
    "engine": "gpaw",
}


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", None),
        ("   ", None),
        ("5.43", 5.43),
        (" 400 ", 400.0),
        ("1e-5", 1e-5),
    ],
)
def test_optional_float(value, expected):
    assert optional_float(value) == expected


def test_optional_float_invalid():
    with pytest.raises(ValueError):
        optional_float("not-a-number")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", None),
        ("4 4 4", (4, 4, 4)),
        ("4x4x4", (4, 4, 4)),
        ("4 x 4 x 4", (4, 4, 4)),
        ("4,4,4", (4, 4, 4)),
        ("2 3 4", (2, 3, 4)),
    ],
)
def test_optional_mesh(value, expected):
    assert optional_mesh(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "4 4",
        "4 4 4 4",
        "4.5 4 4",
        "abc",
    ],
)
def test_optional_mesh_invalid(value):
    with pytest.raises(ValueError):
        optional_mesh(value)


def test_parse_complete_form():
    spec = parse_form(VALID_FORM)

    assert spec.element == "Si"
    assert spec.crystal_structure == "diamond"
    assert spec.lattice_parameter == 5.43
    assert spec.cutoff_ev == 400
    assert spec.kpoints == (4, 4, 4)
    assert spec.engine == "gpaw"


def test_parse_incomplete_form():
    raw = {
        **VALID_FORM,
        "element": "",
        "crystal_structure": "",
        "lattice_parameter": "",
        "cutoff_ev": "",
        "kpoints": "",
    }

    spec = parse_form(raw)

    assert spec.element is None
    assert spec.crystal_structure is None
    assert spec.lattice_parameter is None
    assert spec.cutoff_ev is None
    assert spec.kpoints is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("lattice_parameter", "-1"),
        ("cutoff_ev", "-100"),
        ("kpoints", "4 -1 4"),
        ("xc_functional", "INVALID"),
        ("engine", "INVALID"),
        ("crystal_structure", "INVALID"),
    ],
)
def test_parse_invalid_form(field, value):
    raw = {**VALID_FORM, field: value}

    with pytest.raises((ValueError, ValidationError)):
        parse_form(raw)
