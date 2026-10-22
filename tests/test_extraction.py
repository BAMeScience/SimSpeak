from simspeak.extraction import extract, extract_verified, merge_spec
from simspeak.models import SimulationSpec
from simspeak.validation import validate
import pytest


def test_md_extract_without_defaults():
    result = extract_verified('Run NVT molecular dynamics at 300 K for 10 ps')
    assert result.patch['method'] == 'classical_md'
    assert result.patch['task']['parameters'] == {'ensemble': 'nvt', 'temperature_K': 300.0, 'duration_ps': 10.0}
    assert 'calculator' not in result.patch
    assert validate(merge_spec(SimulationSpec(), result.patch), user_edited=True).status == 'INCOMPLETE'


def test_dft_explicit():
    result = extract_verified('DFT single-point using Quantum ESPRESSO with PBE, 500 eV cutoff')
    assert result.patch['calculator']['name'] == 'espresso'
    assert result.patch['calculator']['parameters']['cutoff_ev'] == 500
    assert result.patch['task']['type'] == 'single_point'


def test_no_guessed_structure_or_potential():
    result = extract_verified('Simulate silicon at 300 K with NVT MD')
    assert 'structure' not in result.patch
    assert 'calculator' not in result.patch


def test_existing_user_edit_not_overwritten():
    existing = SimulationSpec.model_validate({'task': {'type': 'md', 'parameters': {'temperature_K': 400}}})
    with pytest.raises(ValueError, match='Conflict'):
        merge_spec(existing, extract_verified('NVT MD at 300 K').patch)


def test_ambiguous_methods_not_guessed():
    result = extract_verified('Compare DFT and MD')
    assert 'method' not in result.patch


def test_unknown_words_not_promoted():
    result = extract_verified('Run MD on silicon with the best potential and appropriate timestep')
    assert 'calculator' not in result.patch
    assert 'timestep_fs' not in result.patch.get('task', {}).get('parameters', {})


def test_ollama_failure_fallback(monkeypatch):
    import sys
    class Broken:
        def chat(self, **kwargs):
            raise RuntimeError('offline')
    monkeypatch.setitem(sys.modules, 'ollama', Broken())
    result = extract('Run NVE MD for 100 steps', use_ollama=True)
    assert result.patch['task']['parameters']['steps'] == 100
    assert not result.llm_used


@pytest.mark.parametrize('prompt', ['Task should be single_point', 'task.type single_point'])
def test_standalone_single_point(prompt):
    result = extract_verified(prompt)
    assert result.patch['task']['type'] == 'single_point'
    assert result.evidence['task.type'].lower().replace(' ', '_') == 'single_point'

def test_xc_without_dft_keyword():
    result = extract_verified('Use PBE as XC functional')
    assert result.patch['calculator']['parameters']['xc'] == 'PBE'
    assert 'method' not in result.patch

def test_ollama_omission_preserves_verified(monkeypatch):
    import sys, json
    class IncompleteOllama:
        def chat(self, **kwargs):
            return {'message': {'content': json.dumps({})}}
    monkeypatch.setitem(sys.modules, 'ollama', IncompleteOllama())
    result = extract('Task should be single_point. Use PBE as XC functional', use_ollama=True)
    assert result.patch['task']['type'] == 'single_point'
    assert result.patch['calculator']['parameters']['xc'] == 'PBE'


@pytest.mark.parametrize('prompt', ['The timestep is 2fs', 'The timestep is 2 fs', 'timestep: 2 femtoseconds'])
def test_standalone_timestep(prompt):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['timestep_fs'] == 2.0
    assert 'method' not in result.patch

def test_ambiguous_timestep_unit_not_guessed():
    result = extract_verified('The timestep is 2f.')
    assert 'timestep_fs' not in result.patch.get('task', {}).get('parameters', {})
    assert any('unit' in note for note in result.notes)

@pytest.mark.parametrize('prompt', ['Generate the initial state', 'Generate initial velocities'])
def test_standalone_initial_state(prompt):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['initial_state'] == 'generate'
    assert 'method' not in result.patch

def test_structure_filename_remains_supported():
    result = extract_verified('Use silicon.cif as the structure')
    assert result.patch['structure']['source'] == 'silicon.cif'

def test_followup_merge_preserves_existing_method():
    current = SimulationSpec.model_validate({'method': 'classical_md', 'task': {'type': 'md'}})
    for phrase in ('Generate the initial state', 'The timestep is 2fs'):
        current = merge_spec(current, extract_verified(phrase).patch)
    assert current.task.parameters == {'initial_state': 'generate', 'timestep_fs': 2.0}


@pytest.mark.parametrize('prompt', ['Run 10000 steps', 'The number of steps is 10000', 'steps: 10000', 'Use 10000 MD steps'])
def test_standalone_steps(prompt):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['steps'] == 10000
    assert 'method' not in result.patch or prompt.endswith('MD steps')

@pytest.mark.parametrize(('prompt', 'expected'), [
    ('Use Langevin thermostat', 'langevin'),
    ('Set the thermostat to Nose-Hoover', 'nose_hoover'),
    ('Thermostat: Berendsen', 'berendsen'),
])
def test_standalone_thermostat(prompt, expected):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['thermostat'] == expected
    assert 'method' not in result.patch

def test_conflicting_thermostats_are_not_selected():
    result = extract_verified('Use Langevin or Berendsen thermostat')
    assert 'thermostat' not in result.patch.get('task', {}).get('parameters', {})
    assert any('Conflicting thermostats' in n for n in result.notes)

def test_followup_steps_and_thermostat_merge():
    current = SimulationSpec.model_validate({'method': 'classical_md', 'task': {'type': 'md'}})
    for prompt in ('Run 10000 steps', 'Use Langevin thermostat'):
        current = merge_spec(current, extract_verified(prompt).patch)
    assert current.task.parameters['steps'] == 10000
    assert current.task.parameters['thermostat'] == 'langevin'


@pytest.mark.parametrize(('prompt','value'), [
    ('Duration is 10 ps', 10.0),
    ('Run for 2 ns', 2000.0),
    ('duration: 0.5 ps', 0.5),
    ('Simulate for 100 fs', 0.1),
])
def test_standalone_duration(prompt, value):
    result = extract_verified(prompt)
    assert result.patch['task']['parameters']['duration_ps'] == pytest.approx(value)
    assert 'method' not in result.patch

@pytest.mark.parametrize(('prompt','value'), [
    ('Use Tersoff potential', 'tersoff'),
    ('Potential: EAM', 'eam'),
    ('Use OPLS-AA force field', 'opls_aa'),
    ('Use GenFF-2.0', 'cgenff_2_0'),
    ('Use CGenFF 2.0', 'cgenff_2_0'),
    ('Use AMBER ff19SB', 'amber_ff19sb'),
])
def test_standalone_potential(prompt, value):
    result = extract_verified(prompt)
    assert result.patch['calculator']['parameters']['potential'] == value


def test_conflicting_potentials_not_selected():
    result = extract_verified('Use OPLS-AA or AMBER ff19SB')
    assert 'potential' not in result.patch.get('calculator', {}).get('parameters', {})
    assert any('Conflicting force fields' in note for note in result.notes)


def test_timestep_not_misread_as_duration():
    result = extract_verified('The timestep is 2fs')
    assert result.patch['task']['parameters'] == {'timestep_fs': 2.0}


def test_duration_and_potential_followup_merge():
    spec = SimulationSpec.model_validate({'method':'classical_md','task':{'type':'md'}})
    for prompt in ('Use OPLS-AA force field', 'Run for 2 ns'):
        spec = merge_spec(spec, extract_verified(prompt).patch)
    assert spec.calculator.parameters['potential'] == 'opls_aa'
    assert spec.task.parameters['duration_ps'] == 2000.0


def test_evidence_for_normalized_forcefield_and_duration():
    current = SimulationSpec.model_validate({'method':'classical_md','task':{'type':'md'}})
    for prompt in ('Use GenFF-2.0', 'Run for 2 ns'):
        result = extract_verified(prompt)
        current = merge_spec(current, result.patch)
        report = validate(current, user_edited=False, source_text=prompt, evidence=result.evidence)
        assert not any(d.code == 'UNVERIFIED_VALUE' for d in report.diagnostics)

def test_dft_standalone_parameters():
    cases = [
        ('Use a 4x4x4 k-point mesh', 'calculator', 'kpoints', [4, 4, 4]),
        ('kpoints: 6 6 6', 'calculator', 'kpoints', [6, 6, 6]),
        ('Set the force tolerance to 0.01 eV/Å', 'task', 'fmax_ev_ang', 0.01),
        ('force convergence 0.02 eV/Angstrom', 'task', 'fmax_ev_ang', 0.02),
        ('Set the cutoff to 500 eV', 'calculator', 'cutoff_ev', 500),
        ('plane-wave cutoff 60 Ry', 'calculator', 'cutoff_ev', 60 * 13.605693122994),
    ]
    for prompt, section, key, value in cases:
        result = extract_verified(prompt)
        assert result.patch[section]['parameters'][key] == value, prompt
