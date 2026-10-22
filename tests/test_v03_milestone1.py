"""v0.3 milestone 1: stable, engine-neutral extraction contracts."""
from simspeak.extraction import extract_verified
from simspeak.models import SimulationSpec
from simspeak.validation import validate


def test_schema_has_exactly_four_top_level_fields():
    assert set(SimulationSpec.model_fields) == {'structure', 'method', 'calculator', 'task'}


def test_md_reference_extracts_independently_without_scientific_defaults():
    text = 'Create a classical MD NPT argon Lennard-Jones simulation at 300 K and pressure 1 bar, with a timestep 2 fs for 20000 steps using LAMMPS.'
    patch = extract_verified(text).patch
    assert patch['method'] == 'classical_md'
    assert patch['calculator']['name'] == 'lammps'
    assert patch['calculator']['parameters']['potential'] == 'lj'
    assert patch['task']['parameters']['ensemble'] == 'npt'
    assert patch['task']['parameters']['temperature_K'] == 300
    assert patch['task']['parameters']['pressure_bar'] == 1
    assert patch['task']['parameters']['timestep_fs'] == 2
    assert patch['task']['parameters']['steps'] == 20000
    assert 'thermostat' not in patch['task']['parameters']
    assert 'barostat' not in patch['task']['parameters']


def test_dft_reference_extracts_without_inventing_cutoff_or_kpoints():
    patch = extract_verified('Perform a PBE DFT single-point calculation using Quantum ESPRESSO.').patch
    assert patch['method'] == 'dft'
    assert patch['calculator']['name'] == 'espresso'
    assert patch['calculator']['parameters']['xc'] == 'PBE'
    assert patch['task']['type'] == 'single_point'
    assert 'cutoff_ev' not in patch['calculator']['parameters']
    assert 'kpoints' not in patch['calculator']['parameters']
    assert 'pseudopotentials' not in patch['calculator']['parameters']


def test_standalone_md_followups_do_not_change_method_or_other_parameters():
    for text, key, expected in [
        ('Temperature is 300 K', 'temperature_K', 300),
        ('Pressure is 1 bar', 'pressure_bar', 1),
        ('Thermostat is Nose-Hoover', 'thermostat', 'nose_hoover'),
        ('Barostat is Nose-Hoover', 'barostat', 'nose_hoover'),
    ]:
        patch = extract_verified(text).patch
        assert patch == {'task': {'parameters': {key: expected}}}


def test_incomplete_md_reference_reports_missing_choices():
    spec = SimulationSpec(method='classical_md', calculator={'name':'lammps','parameters':{'potential':'lj'}}, task={'type':'md','parameters':{'ensemble':'npt','temperature_K':300,'pressure_bar':1,'timestep_fs':2,'steps':20000}})
    report = validate(spec, user_edited=True)
    missing = {d.path for d in report.diagnostics if d.code == 'MISSING'}
    assert {'structure.source', 'task.parameters.initial_state', 'task.parameters.thermostat', 'task.parameters.barostat'} <= missing
