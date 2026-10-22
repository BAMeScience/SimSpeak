import json
from io import BytesIO
from zipfile import ZipFile
import pytest
pytest.importorskip("ase")
from simspeak.structure_sources import generate_crystal
from simspeak.qe_generator import GenerationBlocked


def test_argon_fcc_256_atoms_and_cif_roundtrip():
    from ase.io import read
    data, filename, meta = generate_crystal('Ar', 'fcc', 5.26, (4, 4, 4))
    atoms = read(BytesIO(data), format='cif')
    assert filename == 'generated_crystal.cif'
    assert len(atoms) == 256
    assert all(atoms.pbc)
    assert meta['number_of_atoms'] == 256
    assert meta['lattice_parameter_angstrom'] == 5.26


def test_silicon_diamond():
    from ase.io import read
    data, _, _ = generate_crystal('Si', 'diamond', 5.43, (1, 1, 1))
    assert len(read(BytesIO(data), format='cif')) == 8


@pytest.mark.parametrize('element, crystal, a, repeats', [
    ('Xx', 'fcc', 5.0, (1,1,1)), ('Ar', 'hcp', 5.0, (1,1,1)),
    ('Ar', 'fcc', 0, (1,1,1)), ('Ar', 'fcc', 5.0, (0,1,1)),
    ('Ar', 'fcc', 5.0, (1,2)),
])
def test_invalid_crystal_settings_blocked(element, crystal, a, repeats):
    with pytest.raises(GenerationBlocked):
        generate_crystal(element, crystal, a, repeats)
