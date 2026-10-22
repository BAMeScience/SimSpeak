import pytest
from simspeak.extraction import extract_verified
from simspeak.revisions import apply_chat_revision
from simspeak.models import SimulationSpec

@pytest.mark.parametrize('prompt,value', [
    ('Temperature is 300 K', 300.0),
    ('Set temperature to 350 K', 350.0),
    ('Target temperature: 400 kelvin', 400.0),
    ('Run NPT at 300 K', 300.0),
])
def test_temperature_standalone(prompt, value):
    assert extract_verified(prompt).patch['task']['parameters']['temperature_K'] == value

def test_temperature_does_not_touch_thermostat_barostat():
    r = extract_verified('Temperature is 300 K')
    assert set(r.patch['task']['parameters']) == {'temperature_K'}

def test_barostat_does_not_change_temperature():
    initial = SimulationSpec(method='classical_md', task={'type':'md','parameters':{'temperature_K':300.0,'thermostat':'langevin'}})
    updated, changes, notes = apply_chat_revision(initial, 'Barostat is Nose-Hoover')
    assert updated.task.parameters['temperature_K'] == 300.0
    assert updated.task.parameters['thermostat'] == 'langevin'
    assert updated.task.parameters['barostat'] == 'nose_hoover'

def test_change_temperature_keeps_other_controls():
    initial = SimulationSpec(method='classical_md', task={'type':'md','parameters':{'temperature_K':300.0,'thermostat':'langevin','barostat':'berendsen'}})
    updated, changes, notes = apply_chat_revision(initial, 'Change temperature to 400 K')
    assert updated.task.parameters == {'temperature_K':400.0,'thermostat':'langevin','barostat':'berendsen'}

def test_clear_temperature_only():
    initial = SimulationSpec(method='classical_md', task={'type':'md','parameters':{'temperature_K':300.0,'thermostat':'langevin'}})
    updated, _, _ = apply_chat_revision(initial, 'Clear the temperature')
    assert 'temperature_K' not in updated.task.parameters
    assert updated.task.parameters['thermostat'] == 'langevin'
