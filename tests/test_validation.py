import pytest
from pydantic import ValidationError
from simspeak.models import SimulationSpec
from simspeak.form import parse_form
from simspeak.validation import validate

def make(**overrides):
    base = {'structure': {'source': 'si.cif'}, 'method': 'classical_md', 'calculator': {'name': 'lammps', 'parameters': {'potential': 'user-potential'}}, 'task': {'type': 'md', 'parameters': {'ensemble': 'nve', 'timestep_fs': 1, 'steps': 100, 'initial_state': 'from_file'}}}
    base.update(overrides)
    return SimulationSpec.model_validate(base)

def test_blank_draft_incomplete():
    assert validate(SimulationSpec(), user_edited=True).status == 'INCOMPLETE'

def test_valid_manual_md():
    assert validate(make(), user_edited=True).status == 'VALID'

def test_llm_without_evidence_invalid():
    assert validate(make(), source_text='MD with silicon').status == 'INVALID'

def test_fake_quote_invalid():
    assert any(x.code == 'UNVERIFIED_EVIDENCE' for x in validate(make(), source_text='MD with silicon', evidence={'method':'classical MD'}).diagnostics)

def test_unknown_parameter_invalid():
    spec = make(task={'type':'md', 'parameters': {'ensemble':'nve','timestep_fs':1,'steps':100,'initial_state':'from_file','made_up':7}})
    assert any(x.code == 'UNKNOWN_PARAMETER' for x in validate(spec, user_edited=True).diagnostics)

def test_method_task_mismatch():
    assert any(x.code == 'INCOMPATIBLE_TASK' for x in validate(make(method='dft'), user_edited=True).diagnostics)

def test_nvt_missing_thermostat():
    spec = make(task={'type':'md','parameters': {'ensemble':'nvt','temperature_K':300,'timestep_fs':1,'steps':100,'initial_state':'from_file'}})
    assert any(x.path == 'task.parameters.thermostat' for x in validate(spec, user_edited=True).diagnostics)

def test_conflicting_duration():
    spec = make(task={'type':'md','parameters': {'ensemble':'nve','timestep_fs':1,'steps':100,'duration_ps':5,'initial_state':'from_file'}})
    assert any(x.code == 'CONFLICT' for x in validate(spec, user_edited=True).diagnostics)

def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        SimulationSpec.model_validate({'element':'Si'})

def test_form_no_defaults():
    spec = parse_form({'source':'', 'method':'', 'calculator':'', 'calculator_parameters':'{}','task':'','task_parameters':'{}'})
    assert spec.method is None and spec.task.type is None and spec.calculator.name is None

def test_form_rejects_non_object_parameters():
    with pytest.raises(ValueError):
        parse_form({'source':'', 'method':'', 'calculator':'', 'calculator_parameters':'[]','task':'','task_parameters':'{}'})
