import pytest
from simspeak.models import SimulationSpec
from simspeak.qe_generator import GenerationBlocked, generate_qe


def spec(**overrides):
    data = dict(
        structure={'source': 'silicon.cif'}, method='dft',
        calculator={'name': 'espresso', 'parameters': {
            'xc': 'PBE', 'basis': 'plane_wave', 'cutoff_ev': 500,
            'kpoints': [4, 4, 4], 'pseudopotentials': {'Si': 'Si.UPF'}}},
        task={'type': 'single_point', 'parameters': {}},
    )
    data.update(overrides)
    return SimulationSpec.model_validate(data)


def test_missing_upload():
    with pytest.raises(GenerationBlocked, match='Upload'):
        generate_qe(spec(), b'', filename='silicon.cif')


def test_no_optimization_silent_mapping():
    with pytest.raises(GenerationBlocked, match='single_point'):
        generate_qe(spec(task={'type': 'optimize', 'parameters': {'fmax_ev_ang': 0.01}}), b'x', filename='silicon.cif')


def test_reject_mismatched_source():
    with pytest.raises(GenerationBlocked, match='filename'):
        generate_qe(spec(), b'x', filename='other.cif')


def test_missing_cutoff():
    s = spec()
    del s.calculator.parameters['cutoff_ev']
    with pytest.raises(GenerationBlocked, match='cutoff'):
        generate_qe(s, b'x', filename='silicon.cif')


def test_missing_pseudopotentials():
    s = spec()
    del s.calculator.parameters['pseudopotentials']
    with pytest.raises(GenerationBlocked, match='pseudopotential'):
        generate_qe(s, b'x', filename='silicon.cif')


def test_missing_kpoints():
    s = spec()
    del s.calculator.parameters['kpoints']
    with pytest.raises(GenerationBlocked, match='k-point'):
        generate_qe(s, b'x', filename='silicon.cif')
