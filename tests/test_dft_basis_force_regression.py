import pytest
from simspeak.extraction import extract_verified

@pytest.mark.parametrize('prompt,value', [
    ('Force tolerance is 0.01 eV/Å', 0.01),
    ('Set force tolerance to 0.01 eV/Angstrom', 0.01),
    ('fmax: 0.02 eV/A', 0.02),
    ('0.03 eV/Å force convergence', 0.03),
])
def test_force_tolerance(prompt, value):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['fmax_ev_ang'] == value

@pytest.mark.parametrize('prompt', [
    'Use a local basis', 'Use localized basis', 'Set basis to local orbitals',
    'Use atomic orbital basis', 'Use a localized orbital basis',
])
def test_local_basis(prompt):
    result = extract_verified(prompt)
    assert result.patch['calculator']['parameters']['basis'] == 'localized'

def test_plane_wave_unchanged():
    assert extract_verified('Use plane-wave basis').patch['calculator']['parameters']['basis'] == 'plane_wave'
