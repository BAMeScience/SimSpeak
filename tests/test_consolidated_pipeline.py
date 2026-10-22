"""Regression checks for the consolidated chat -> JSON -> LAMMPS path."""
import io
import json
import sys
import types
import zipfile
from types import SimpleNamespace

from simspeak.engine_adapters import generate_engine_template
from simspeak.extraction import extract_verified
from simspeak.models import SimulationSpec


class FakeAtoms:
    pbc = [True, True, True]
    cell = SimpleNamespace(volume=125, array=[[5, 0, 0], [0, 5, 0], [0, 0, 5]])
    def __len__(self): return 1
    def get_chemical_symbols(self): return ['Si']


def test_chat_to_lammps_npt_bundle(monkeypatch):
    import simspeak.engine_adapters as adapters
    monkeypatch.setattr(adapters, '_load_atoms', lambda *args: FakeAtoms())
    ase = types.ModuleType('ase')
    ase_io = types.ModuleType('ase.io')
    def write(buf, atoms, format):
        assert format == 'extxyz'
        buf.write('1\nLattice="5 0 0 0 5 0 0 0 5"\nSi 0 0 0\n')
    ase_io.write = write
    monkeypatch.setitem(sys.modules, 'ase', ase)
    monkeypatch.setitem(sys.modules, 'ase.io', ase_io)

    spec = SimulationSpec(method='classical_md', calculator={'parameters': {'forcefield': 'opls_aa'}},
        task={'type': 'md', 'parameters': {'ensemble': 'npt', 'steps': 20000, 'timestep_fs': 2.0}})
    for prompt, key, value in [('Temperature is 300 K', 'temperature_K', 300.0),
                               ('Pressure is 1 bar', 'pressure_bar', 1.0),
                               ('Barostat is Nose-Hoover', 'barostat', 'nose_hoover'),
                               ('Thermostat is Nose-Hoover', 'thermostat', 'nose_hoover')]:
        patch = extract_verified(prompt).patch
        assert patch['task']['parameters'][key] == value
        spec.task.parameters.update(patch['task']['parameters'])

    pkg = generate_engine_template(spec, b'fake', filename='silicon.cif', engine='LAMMPS', lammps_units='real')
    with zipfile.ZipFile(io.BytesIO(pkg.content)) as z:
        inp = z.read('in.lammps').decode()
        report = json.loads(z.read('generation_report.json'))
        assert 'coordinates.extxyz' in z.namelist()
        for text in ('units real', 'timestep 2', 'run 20000',
                     'Target temperature (K): 300', 'Target pressure requested (bar): 1',
                     'Barostat requested: nose_hoover', 'Thermostat requested: nose_hoover'):
            assert text in inp
        assert report['runnable'] is False
        assert '__REQUIRED_ENSEMBLE_FIX__' in inp


def test_unselected_units_never_invented(monkeypatch):
    import simspeak.engine_adapters as adapters
    monkeypatch.setattr(adapters, '_load_atoms', lambda *args: FakeAtoms())
    spec = SimulationSpec(method='classical_md', task={'type': 'md', 'parameters': {'timestep_fs': 2.0, 'steps': 100}})
    pkg = generate_engine_template(spec, b'fake', filename='silicon.cif', engine='LAMMPS')
    with zipfile.ZipFile(io.BytesIO(pkg.content)) as z:
        inp = z.read('in.lammps').decode()
        assert 'units __REQUIRED_LAMMPS_UNITS__' in inp
        assert 'timestep __REQUIRED_TIMESTEP_ENGINE_UNITS__' in inp
