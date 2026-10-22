import io
import json
import zipfile
import pytest
from simspeak.argon_reference import ArgonLJConfig, generate_argon_lj_bundle


def config(**changes):
    values = dict(lattice_constant_ang=5.4, cells_per_axis=4,
                  epsilon_kcal_mol=0.238, sigma_ang=3.405, cutoff_ang=8.5,
                  temperature_k=300, pressure_bar=1, timestep_fs=2, steps=20000,
                  tdamp_fs=200, pdamp_fs=2000, random_seed=12345, mass_g_mol=39.948)
    values.update(changes)
    return ArgonLJConfig(**values)


def test_complete_bundle():
    with zipfile.ZipFile(io.BytesIO(generate_argon_lj_bundle(config()))) as z:
        assert set(z.namelist()) == {'in.lammps','argon.data','reference_config.json','generation_report.json'}
        script=z.read('in.lammps').decode()
        data=z.read('argon.data').decode()
        report=json.loads(z.read('generation_report.json'))
        assert 'fix integrator all npt temp 300 300 200 iso 0.986923266716 0.986923266716 2000' in script
        assert 'timestep 2' in script and 'run 20000' in script
        assert '__REQUIRED_' not in script
        assert '256 atoms' in data and 'Masses' in data and 'Atoms # atomic' in data
        assert report['executed'] is False


@pytest.mark.parametrize('change', [{'cutoff_ang':11},{'tdamp_fs':0},{'steps':-1},
                                   {'temperature_k':float('nan')},{'cells_per_axis':1}])
def test_reject_invalid_configuration(change):
    with pytest.raises(ValueError): generate_argon_lj_bundle(config(**change))


def test_reproducible():
    assert generate_argon_lj_bundle(config()) == generate_argon_lj_bundle(config())
