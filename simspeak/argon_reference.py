"""Opt-in, explicit Argon LJ reference bundle; never a universal scientific default."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from io import BytesIO
import json
import math
import zipfile


@dataclass(frozen=True)
class ArgonLJConfig:
    lattice_constant_ang: float
    cells_per_axis: int
    epsilon_kcal_mol: float
    sigma_ang: float
    cutoff_ang: float
    temperature_k: float
    pressure_bar: float
    timestep_fs: float
    steps: int
    tdamp_fs: float
    pdamp_fs: float
    random_seed: int
    mass_g_mol: float


def generate_argon_lj_bundle(config: ArgonLJConfig) -> bytes:
    """Create an all-atom FCC Ar data file and LAMMPS NPT script in real units.

    All numerical scientific choices are required and supplied by the caller.
    No simulation is executed here.
    """
    floats = ('lattice_constant_ang','epsilon_kcal_mol','sigma_ang','cutoff_ang',
              'temperature_k','timestep_fs','tdamp_fs','pdamp_fs','mass_g_mol')
    for name in floats:
        value = getattr(config, name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be positive and finite')
    if not isinstance(config.pressure_bar, (int,float)) or not math.isfinite(config.pressure_bar):
        raise ValueError('pressure_bar must be finite')
    for name in ('cells_per_axis','steps','random_seed'):
        value = getattr(config,name)
        if type(value) is not int or value <= 0:
            raise ValueError(f'{name} must be a positive integer')
    if config.cells_per_axis < 2:
        raise ValueError('At least two FCC cells per axis are required for this reference')
    length = config.cells_per_axis * config.lattice_constant_ang
    if config.cutoff_ang >= length / 2:
        raise ValueError('cutoff must be smaller than half the periodic box length')
    basis = ((0,0,0),(.5,.5,0),(.5,0,.5),(0,.5,.5))
    positions = []
    for i in range(config.cells_per_axis):
        for j in range(config.cells_per_axis):
            for k in range(config.cells_per_axis):
                for x,y,z in basis:
                    positions.append(((i+x)*config.lattice_constant_ang,
                                      (j+y)*config.lattice_constant_ang,
                                      (k+z)*config.lattice_constant_ang))
    data = ['LAMMPS data file: explicit FCC argon LJ reference', '',
            f'{len(positions)} atoms', '1 atom types', '',
            f'0 {length:.12g} xlo xhi', f'0 {length:.12g} ylo yhi',
            f'0 {length:.12g} zlo zhi', '', 'Masses', '',
            f'1 {config.mass_g_mol:.12g}', '', 'Atoms # atomic', '']
    data.extend(f'{index} 1 {x:.12g} {y:.12g} {z:.12g}' for index,(x,y,z) in enumerate(positions,1))
    p_atm = config.pressure_bar / 1.01325
    script = '\n'.join([
        '# SimSpeak argon LJ REFERENCE: user must review explicit scientific parameters',
        'units real', 'atom_style atomic', 'boundary p p p', 'read_data argon.data',
        'pair_style lj/cut ' + f'{config.cutoff_ang:.12g}',
        f'pair_coeff 1 1 {config.epsilon_kcal_mol:.12g} {config.sigma_ang:.12g}',
        'neighbor 2.0 bin', 'neigh_modify delay 0 every 1 check yes',
        f'velocity all create {config.temperature_k:.12g} {config.random_seed} mom yes rot no dist gaussian',
        f'fix integrator all npt temp {config.temperature_k:.12g} {config.temperature_k:.12g} {config.tdamp_fs:.12g} '
        f'iso {p_atm:.12g} {p_atm:.12g} {config.pdamp_fs:.12g}',
        f'timestep {config.timestep_fs:.12g}', 'thermo 100', 'thermo_style custom step temp press pe ke etotal vol',
        f'run {config.steps}', ''])
    report = {'engine':'LAMMPS', 'mode':'explicit_argon_reference', 'runnable_candidate':True,
              'executed':False, 'scientifically_validated':False,
              'units':'real', 'atoms':len(positions),
              'pressure_atm':p_atm,
              'warnings':['Not executed against LAMMPS in the packaging environment.',
                          'This is a user-reviewed illustrative LJ model, not a calibrated argon force field.',
                          'Stability and physical validity require simulation and scientific review.']}
    files = {'in.lammps':script, 'argon.data':'\n'.join(data)+'\n',
             'reference_config.json':json.dumps(asdict(config),indent=2)+'\n',
             'generation_report.json':json.dumps(report,indent=2)+'\n'}
    out=BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in files.items(): z.writestr(name,content)
    return out.getvalue()
