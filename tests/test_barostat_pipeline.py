import io
import json
import zipfile
import pytest
from simspeak.extraction import extract_verified
from simspeak.revisions import apply_chat_revision
from simspeak.models import SimulationSpec
from simspeak.engine_adapters import generate_engine_template

@pytest.mark.parametrize('prompt,expected', [
    ('Use a Berendsen barostat','berendsen'),
    ('Set the barostat to Nose-Hoover','nose_hoover'),
    ('Use a Parrinello-Rahman barostat','parrinello_rahman'),
    ('Barostat: Monte Carlo','monte_carlo'),
])
def test_extract_barostat(prompt, expected):
    r = extract_verified(prompt)
    assert r.patch['task']['parameters']['barostat'] == expected
    assert 'thermostat' not in r.patch.get('task', {}).get('parameters', {})
    assert 'ensemble' not in r.patch.get('task', {}).get('parameters', {})

def test_barostat_conflict():
    r = extract_verified('Use Berendsen barostat and Nose-Hoover barostat')
    assert 'barostat' not in r.patch.get('task', {}).get('parameters', {})
    assert any('Conflicting barostat' in note for note in r.notes)

def test_revise_and_clear_barostat():
    initial = SimulationSpec(method='classical_md', task={'type':'md', 'parameters': {'barostat':'berendsen'}})
    revised, changes, notes = apply_chat_revision(initial, 'Change barostat to Nose-Hoover')
    assert revised.task.parameters['barostat'] == 'nose_hoover'
    cleared, changes, notes = apply_chat_revision(revised, 'Clear the barostat')
    assert 'barostat' not in cleared.task.parameters

def test_lammps_preserves_npt_controls(monkeypatch):
    from types import SimpleNamespace
    atoms = SimpleNamespace(pbc=[True]*3, cell=SimpleNamespace(volume=125, array=[[5,0,0],[0,5,0],[0,0,5]]), get_chemical_symbols=lambda: ['Si'])
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: atoms)
    spec = SimulationSpec(method='classical_md', task={'type':'md', 'parameters': {
        'ensemble':'npt','pressure_bar':1.0,'barostat':'berendsen',
        'temperature_K':300, 'thermostat':'langevin', 'steps':20000, 'timestep_fs':2.0}})
    result = generate_engine_template(spec, b'fake', filename='si.cif', engine='LAMMPS', lammps_units='real')
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        inp = z.read('in.lammps').decode()
        assert 'Barostat requested: berendsen' in inp
        assert 'Target pressure requested (bar): 1.0' in inp
        assert '0.986923' in inp
        assert 'Target temperature (K): 300' in inp
        assert '__REQUIRED_ENSEMBLE_FIX__' in inp
        assert json.loads(z.read('generation_report.json'))['runnable'] is False


def test_barostat_is_nose_hoover_does_not_set_thermostat():
    result = extract_verified('Barostat is Nose-Hoover')
    params = result.patch['task']['parameters']
    assert params['barostat'] == 'nose_hoover'
    assert 'thermostat' not in params

def test_thermostat_is_nose_hoover_does_not_set_barostat():
    result = extract_verified('Thermostat is Nose-Hoover')
    params = result.patch['task']['parameters']
    assert params['thermostat'] == 'nose_hoover'
    assert 'barostat' not in params

def test_unqualified_nose_hoover_is_not_assigned():
    result = extract_verified('Use Nose-Hoover')
    assert 'thermostat' not in result.patch.get('task', {}).get('parameters', {})
    assert 'barostat' not in result.patch.get('task', {}).get('parameters', {})
