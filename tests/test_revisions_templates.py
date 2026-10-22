import pytest
from simspeak.models import SimulationSpec
from simspeak.revisions import apply_chat_revision
from simspeak.qe_templates import generate_qe_template
from simspeak.qe_generator import GenerationBlocked


def test_replace_xc():
    current = SimulationSpec.model_validate({'calculator': {'parameters': {'xc': 'PBE'}}})
    new, changes, notes = apply_chat_revision(current, 'Actually use PBEsol instead')
    assert new.calculator.parameters['xc'] == 'PBEsol'
    assert changes == [('calculator.parameters.xc', 'PBE', 'PBEsol')]


def test_change_from_to():
    current = SimulationSpec.model_validate({'calculator': {'parameters': {'xc': 'PBE'}}})
    new, changes, notes = apply_chat_revision(current, 'Change PBE to PBEsol')
    assert new.calculator.parameters['xc'] == 'PBEsol'


def test_clear_xc():
    current = SimulationSpec.model_validate({'calculator': {'parameters': {'xc': 'PBE'}}})
    new, changes, notes = apply_chat_revision(current, 'Clear the XC functional')
    assert 'xc' not in new.calculator.parameters


def test_no_implicit_overwrite():
    current = SimulationSpec.model_validate({'calculator': {'parameters': {'xc': 'PBE'}}})
    new, changes, notes = apply_chat_revision(current, 'PBEsol')
    assert new == current and not changes and notes


def test_template_rejects_incompatible_task():
    spec = SimulationSpec.model_validate({'method': 'classical_md', 'task': {'type': 'md'}})
    with pytest.raises(GenerationBlocked):
        generate_qe_template(spec, b'data', filename='si.cif')


def test_template_rejects_missing_structure():
    with pytest.raises(GenerationBlocked):
        generate_qe_template(SimulationSpec(), b'', filename='si.cif')

def test_template_inserts_missing_scientific_values(monkeypatch):
    import io, json, sys, types, zipfile
    class Atom:
        symbol = 'Si'
        mass = 28.085
        position = (0.0, 0.0, 0.0)
    class Cell:
        volume = 40.0
        array = ((3.4, 0, 0), (0, 3.4, 0), (0, 0, 3.4))
    class Atoms:
        pbc = (True, True, True)
        cell = Cell()
        def __len__(self): return 1
        def __iter__(self): return iter((Atom(),))
        def get_chemical_symbols(self): return ['Si']
    ase = types.ModuleType('ase')
    ase.__path__ = []
    ase_io = types.ModuleType('ase.io')
    ase_io.read = lambda *args, **kwargs: Atoms()
    ase_units = types.ModuleType('ase.units')
    ase_units.Rydberg = 13.605693
    monkeypatch.setitem(sys.modules, 'ase', ase)
    monkeypatch.setitem(sys.modules, 'ase.io', ase_io)
    monkeypatch.setitem(sys.modules, 'ase.units', ase_units)
    spec = SimulationSpec.model_validate({'method': 'dft', 'task': {'type': 'single_point'},
                                          'structure': {'source': 'si.cif'},
                                          'calculator': {'parameters': {'basis': 'plane_wave'}}})
    package = generate_qe_template(spec, b'fake cif', filename='si.cif')
    with zipfile.ZipFile(io.BytesIO(package.content)) as z:
        pw = z.read('pw.in').decode()
        report = json.loads(z.read('generation_report.json'))
    assert '__REQUIRED_SI_PSEUDOPOTENTIAL_UPF__' in pw
    assert '__REQUIRED_ECUTWFC_RY__' in pw
    assert '__REQUIRED_KPOINT_GRID_3_INTEGERS__' in pw
    assert '__REQUIRED_XC_FUNCTIONAL__' in pw
    assert not report['runnable'] and len(report['unresolved']) == 4
