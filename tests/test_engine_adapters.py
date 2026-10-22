import io
import json
import zipfile
from types import SimpleNamespace
import pytest
from simspeak.engine_adapters import generate_engine_template, GenerationBlocked
from simspeak.models import SimulationSpec


class Atoms:
    pbc = [True, True, True]
    cell = SimpleNamespace(volume=125, array=[[5, 0, 0], [0, 5, 0], [0, 0, 5]])
    def __len__(self): return 1
    def get_chemical_symbols(self): return ['Si']
    def __iter__(self): return iter([SimpleNamespace(symbol='Si', position=[0, 0, 0])])


def test_lammps_placeholder_bundle(monkeypatch):
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: Atoms())
    spec = SimulationSpec(method='classical_md', task={'type': 'md', 'parameters': {'steps': 1000, 'timestep_fs': 2}})
    result = generate_engine_template(spec, b'fake', filename='silicon.cif', engine='LAMMPS')
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        report = json.loads(z.read('generation_report.json'))
        inp = z.read('in.lammps').decode()
        assert 'run 1000' in inp and 'NON-RUNNABLE' in inp
        assert report['runnable'] is False
        assert any(x['path'] == 'generation.lammps.pair_style' for x in report['unresolved'])


def test_cp2k_placeholder_bundle(monkeypatch):
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: Atoms())
    spec = SimulationSpec(method='dft', task={'type': 'optimize', 'parameters': {'fmax_ev_ang': 0.01}})
    result = generate_engine_template(spec, b'fake', filename='silicon.cif', engine='CP2K')
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        inp = z.read('cp2k.inp').decode()
        assert 'GEO_OPT' in inp and '__REQUIRED_SI_BASIS__' in inp
        assert json.loads(z.read('generation_report.json'))['runnable'] is False


def test_engine_method_mismatch(monkeypatch):
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: Atoms())
    with pytest.raises(GenerationBlocked):
        generate_engine_template(SimulationSpec(method='dft', task={'type': 'single_point'}), b'fake', filename='si.cif', engine='LAMMPS')


def test_filename_mismatch():
    with pytest.raises(GenerationBlocked):
        generate_engine_template(SimulationSpec(structure={'source': 'other.cif'}), b'fake', filename='si.cif', engine='LAMMPS')

@pytest.mark.parametrize('units,expected', [('real', 'timestep 2'), ('metal', 'timestep 0.002')])
def test_lammps_explicit_units_and_nve(monkeypatch, units, expected):
    import sys
    import types
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: Atoms())
    ase = types.ModuleType('ase')
    ase_io = types.ModuleType('ase.io')
    def write(file, atoms, format):
        assert format == 'extxyz'
        file.write('1\nLattice="5 0 0 0 5 0 0 0 5"\nSi 0 0 0\n')
    ase_io.write = write
    monkeypatch.setitem(sys.modules, 'ase', ase)
    monkeypatch.setitem(sys.modules, 'ase.io', ase_io)
    spec = SimulationSpec(method='classical_md', task={'type':'md','parameters':{'ensemble':'nve','timestep_fs':2,'steps':20000}})
    result = generate_engine_template(spec,b'fake',filename='si.cif',engine='LAMMPS',lammps_units=units)
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        inp = z.read('in.lammps').decode()
        report = json.loads(z.read('generation_report.json'))
        assert expected in inp
        assert 'fix integrator all nve' in inp
        assert 'coordinates.extxyz' in z.namelist()
        assert report['runnable'] is False
        assert not any(x['path']=='generation.lammps.ensemble_fix' for x in report['unresolved'])


def test_lammps_unselected_units_remain_unresolved(monkeypatch):
    monkeypatch.setattr('simspeak.engine_adapters._load_atoms', lambda *a: Atoms())
    spec = SimulationSpec(method='classical_md', task={'type':'md','parameters':{'timestep_fs':2,'steps':10}})
    result = generate_engine_template(spec,b'fake',filename='si.cif',engine='LAMMPS')
    with zipfile.ZipFile(io.BytesIO(result.content)) as z:
        assert '__REQUIRED_TIMESTEP_ENGINE_UNITS__' in z.read('in.lammps').decode()
