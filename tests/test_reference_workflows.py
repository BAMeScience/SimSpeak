import json
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
import pytest
from simspeak.models import SimulationSpec
from simspeak.argon_reference import ArgonLJConfig
from simspeak.reference_workflows import argon_reference_from_spec, silicon_qe_reference_from_spec

CONFIG = ArgonLJConfig(**json.loads((Path(__file__).parents[1] / 'config' / 'argon_lj_example.json').read_text()))

def spec():
    return SimulationSpec(method='classical_md', calculator={'name':'lammps','parameters':{'potential':'lj'}},
                          task={'type':'md','parameters':{'ensemble':'npt','temperature_K':300,'pressure_bar':1,'timestep_fs':2,'steps':20000}})

def test_argon_pipeline_creates_consistent_complete_files():
    data = argon_reference_from_spec(spec(), CONFIG)
    with ZipFile(BytesIO(data)) as z:
        assert {'in.lammps','argon.data','spec.json','reference_config.json','generation_report.json','APPROVAL.txt'} <= set(z.namelist())
        script = z.read('in.lammps').decode()
        assert 'fix integrator all npt temp 300 300 200 iso' in script
        assert 'timestep 2' in script and 'run 20000' in script
        assert '__REQUIRED_' not in script
        assert json.loads(z.read('spec.json'))['task']['parameters']['temperature_K'] == 300

def test_argon_rejects_unapproved_protocol():
    s = spec()
    s.task.parameters['barostat'] = 'berendsen'
    with pytest.raises(ValueError, match='incompatible'):
        argon_reference_from_spec(s, CONFIG)

def test_qe_reference_rejects_missing_uploaded_pseudo():
    s = SimulationSpec(method='dft', calculator={'name':'espresso','parameters':{'xc':'PBE','basis':'plane_wave','cutoff_ev':400,'kpoints':[4,4,4],'pseudopotentials':{'Si':'Si.UPF'}}},
                       task={'type':'single_point'}, structure={'source':'silicon.cif'})
    with pytest.raises(ValueError, match='Upload'):
        silicon_qe_reference_from_spec(s,b'fake','silicon.cif','Si.UPF',b'')
