import pytest
from simspeak.extraction import extract_verified
from simspeak.models import SimulationSpec
from simspeak.revisions import apply_chat_revision

@pytest.mark.parametrize('message,expected', [
    ('Pressure is 1 bar', 1.0),
    ('Set pressure to 1 atm', 1.01325),
    ('Use 100 kPa pressure', 1.0),
    ('Target pressure: 5 bar', 5.0),
    ('Pressure is 1 MPa', 10.0),
])
def test_pressure_standalone(message, expected):
    result = extract_verified(message)
    assert result.patch['task']['parameters']['pressure_bar'] == pytest.approx(expected)
    assert 'method' not in result.patch
    assert 'ensemble' not in result.patch['task']['parameters']
    assert 'barostat' not in result.patch['task']['parameters']

def test_pressure_change_and_clear():
    spec = SimulationSpec.model_validate({'method':'classical_md', 'task':{'type':'md','parameters':{'pressure_bar':1.0}}})
    updated, changes, notes = apply_chat_revision(spec, 'Actually change pressure to 2 bar')
    assert updated.task.parameters['pressure_bar'] == 2.0
    assert changes
    cleared, changes, notes = apply_chat_revision(updated, 'Clear the pressure')
    assert 'pressure_bar' not in cleared.task.parameters

def test_pressure_conflict_and_unknown_unit():
    assert 'pressure_bar' not in extract_verified('Pressure is 1 bar and pressure is 2 bar').patch.get('task',{}).get('parameters',{})
    assert 'pressure_bar' not in extract_verified('Pressure is 1 psi').patch.get('task',{}).get('parameters',{})
