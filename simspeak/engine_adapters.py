"""Non-executing, conservative multi-engine template generation.

ASE parses structures. Engine-specific skeletons are explicitly not runnable.
No unknown scientific values are silently replaced by engine defaults.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import json
import math
import zipfile

from simspeak.models import SimulationSpec
from simspeak.qe_generator import GenerationBlocked, QEPackage
from simspeak.qe_templates import generate_qe_template

ENGINES = ('Quantum ESPRESSO', 'VASP', 'CP2K', 'LAMMPS')


def _load_atoms(data: bytes, filename: str):
    if not data or not filename or Path(filename).name != filename:
        raise GenerationBlocked('A named, nonempty structure upload is required')
    try:
        from ase.io import read
    except ImportError as exc:
        raise GenerationBlocked('ASE is required to parse the structure') from exc
    try:
        atoms = read(BytesIO(data), format=Path(filename).suffix.lstrip('.').lower())
    except Exception as exc:
        raise GenerationBlocked(f'ASE cannot parse structure: {exc}') from exc
    if isinstance(atoms, list) or not len(atoms):
        raise GenerationBlocked('Structure must contain atoms')
    return atoms


def _value(mapping, key, path, missing, marker, *, positive=False):
    value = mapping.get(key)
    if value is None or value == '':
        token = f'__REQUIRED_{marker}__'
        missing.append({'path': path, 'placeholder': token, 'reason': 'No explicit value supplied'})
        return token
    if positive and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0):
        raise GenerationBlocked(f'{path} must be a positive finite number')
    return value


def generate_engine_template(spec: SimulationSpec, structure_bytes: bytes, *, filename: str, engine: str, lammps_units: str | None = None) -> QEPackage:
    """Return a non-runnable input template ZIP with provenance and unresolved fields."""
    if lammps_units not in (None, 'real', 'metal'):
        raise GenerationBlocked('LAMMPS units must be real, metal, or unspecified')
    if engine != 'LAMMPS' and lammps_units is not None:
        raise GenerationBlocked('LAMMPS units may only be selected for LAMMPS')
    if engine not in ENGINES:
        raise GenerationBlocked(f'Unknown engine: {engine}')
    if spec.structure.source and Path(spec.structure.source).name != filename:
        raise GenerationBlocked('Uploaded filename differs from structure.source')
    if engine == 'Quantum ESPRESSO':
        return generate_qe_template(spec, structure_bytes, filename=filename)
    atoms = _load_atoms(structure_bytes, filename)
    cp, tp = spec.calculator.parameters, spec.task.parameters
    missing = []
    files = {}
    warnings = ['NON-RUNNABLE TEMPLATE: placeholders and engine-specific decisions must be resolved.',
                'No engine execution, potential/pseudopotential verification, or convergence testing performed.']
    symbols = sorted(set(atoms.get_chemical_symbols()))
    if engine in ('VASP', 'CP2K'):
        if spec.method not in (None, 'dft') or spec.task.type not in (None, 'single_point', 'optimize'):
            raise GenerationBlocked(f'{engine} adapter currently supports only DFT single_point/optimize')
        if not all(atoms.pbc) or abs(atoms.cell.volume) < 1e-12:
            raise GenerationBlocked(f'{engine} requires a periodic structure with a nonzero cell')
        if cp.get('basis') not in (None, 'plane_wave') and engine == 'VASP':
            raise GenerationBlocked('VASP adapter requires plane-wave basis')
        xc = _value(cp, 'xc', 'calculator.parameters.xc', missing, 'XC')
        cutoff = _value(cp, 'cutoff_ev', 'calculator.parameters.cutoff_ev', missing, 'CUTOFF_EV', positive=True)
        mesh = cp.get('kpoints')
        if mesh is None:
            meshtext = _value(cp, 'kpoints', 'calculator.parameters.kpoints', missing, 'KPOINT_MESH')
        elif not isinstance(mesh, (list, tuple)) or len(mesh) != 3 or any(type(k) is not int or k <= 0 for k in mesh):
            raise GenerationBlocked('kpoints must be three positive integers')
        else:
            meshtext = ' '.join(map(str, mesh))
        task = spec.task.type
        if task is None:
            _value({}, 'task', 'task.type', missing, 'DFT_TASK')
        if engine == 'VASP':
            if xc not in ('PBE', 'PBEsol', 'LDA') and not str(xc).startswith('__'):
                raise GenerationBlocked('VASP XC translation not defined for this functional')
            gga = {'PBE': 'PE', 'PBEsol': 'PS', 'LDA': 'CA'}.get(xc, xc)
            lines = ['# SimSpeak NON-RUNNABLE template', f'GGA = {gga}', f'ENCUT = {cutoff}']
            if task == 'single_point':
                lines.append('NSW = 0')
            elif task == 'optimize':
                fmax = _value(tp, 'fmax_ev_ang', 'task.parameters.fmax_ev_ang', missing, 'FMAX_EV_ANG', positive=True)
                lines.extend([f'EDIFFG = -{fmax}' if isinstance(fmax, (int, float)) else f'EDIFFG = {fmax}',
                              'IBRION = __REQUIRED_VASP_IONIC_OPTIMIZER__'])
                missing.append({'path': 'generation.vasp_ionic_optimizer', 'placeholder': '__REQUIRED_VASP_IONIC_OPTIMIZER__', 'reason': 'Engine-specific choice'})
            else:
                lines.append('NSW = __REQUIRED_TASK_SPECIFIC_NSW__')
            files['INCAR'] = '\n'.join(lines) + '\n'
            files['KPOINTS'] = 'SimSpeak mesh\n0\nGamma\n' + str(meshtext) + '\n0 0 0\n'
            try:
                from ase.io import write
                from io import StringIO
                buf = StringIO()
                write(buf, atoms, format='vasp', direct=True, sort=False, vasp5=True)
                files['POSCAR'] = buf.getvalue()
            except Exception as exc:
                raise GenerationBlocked(f'ASE VASP structure writer failed: {exc}') from exc
            files['POTCAR_REQUIRED.txt'] = 'Supply compatible POTCAR datasets for species: ' + ', '.join(symbols) + '\n'
            for element in symbols:
                _value({}, element, f'calculator.parameters.pseudopotentials.{element}', missing, f'{element.upper()}_POTCAR')
        else:
            if cp.get('basis') not in (None, 'localized'):
                raise GenerationBlocked('CP2K adapter currently supports localized GPW basis only')
            # CP2K requires basis sets and pseudopotentials, which are never selected implicitly.
            basis_lines = []
            for element in symbols:
                basis = _value({}, element, f'generation.cp2k.basis.{element}', missing, f'{element.upper()}_BASIS')
                pseudo = _value({}, element, f'generation.cp2k.potential.{element}', missing, f'{element.upper()}_POTENTIAL')
                basis_lines += [f'    &KIND {element}', f'      BASIS_SET {basis}', f'      POTENTIAL {pseudo}', '    &END KIND']
            run = 'ENERGY' if task == 'single_point' else 'GEO_OPT' if task == 'optimize' else '__REQUIRED_RUN_TYPE__'
            if task == 'optimize':
                fmax = _value(tp, 'fmax_ev_ang', 'task.parameters.fmax_ev_ang', missing, 'FMAX_EV_ANG', positive=True)
                # CP2K MAX_FORCE uses hartree/bohr; avoid a wrong conversion for missing values.
                try:
                    from ase.units import Hartree, Bohr
                except ImportError:
                    # Physical constants for unit conversion; ASE is still required for real structure parsing.
                    Hartree, Bohr = 27.211386024367, 0.529177210563
                fmax = f'{fmax * Bohr / Hartree:.12g}' if isinstance(fmax, (float, int)) else fmax
                opt_section = f'&MOTION\n  &GEO_OPT\n    MAX_FORCE {fmax}\n  &END GEO_OPT\n&END MOTION\n'
            else:
                opt_section = ''
            cell = '\n'.join(f'      {axis} ' + ' '.join(f'{v:.12g}' for v in row) for axis, row in zip('ABC', atoms.cell.array))
            coords = '\n'.join(f'      {a.symbol} ' + ' '.join(f'{v:.12g}' for v in a.position) for a in atoms)
            files['cp2k.inp'] = (f'# SimSpeak NON-RUNNABLE template\n&GLOBAL\n  RUN_TYPE {run}\n&END GLOBAL\n'
                f'&FORCE_EVAL\n  METHOD Quickstep\n  &DFT\n    BASIS_SET_FILE_NAME __REQUIRED_BASIS_LIBRARY__\n'
                f'    POTENTIAL_FILE_NAME __REQUIRED_POTENTIAL_LIBRARY__\n    &MGRID\n      CUTOFF __REQUIRED_CP2K_GRID_CUTOFF_RY__\n    &END MGRID\n'
                f'    &XC\n      &XC_FUNCTIONAL {xc}\n      &END XC_FUNCTIONAL\n    &END XC\n  &END DFT\n'
                f'  &SUBSYS\n    &CELL\n{cell}\n    &END CELL\n    &COORD\n{coords}\n    &END COORD\n'
                + '\n'.join(basis_lines) + '\n  &END SUBSYS\n&END FORCE_EVAL\n' + opt_section)
            for name in ('BASIS_LIBRARY', 'POTENTIAL_LIBRARY', 'CP2K_GRID_CUTOFF_RY'):
                missing.append({'path': 'generation.cp2k.' + name.lower(), 'placeholder': f'__REQUIRED_{name}__', 'reason': 'Engine-specific resource/numerical choice'})
            warnings.append('Universal plane-wave cutoff and k-point mesh cannot be mapped directly to CP2K GPW settings; values were not reused.')
    else:
        if spec.method not in (None, 'classical_md') or spec.task.type not in (None, 'md'):
            raise GenerationBlocked('LAMMPS adapter supports classical_md task md only')
        forcefield = cp.get('forcefield') or cp.get('potential')
        ff = forcefield or _value({}, 'forcefield', 'calculator.parameters.forcefield', missing, 'FORCEFIELD')
        dt = _value(tp, 'timestep_fs', 'task.parameters.timestep_fs', missing, 'TIMESTEP_FS', positive=True)
        steps = _value(tp, 'steps', 'task.parameters.steps', missing, 'STEPS')
        if isinstance(steps, int) and steps <= 0:
            raise GenerationBlocked('Steps must be positive')
        if isinstance(steps, (float, bool)):
            raise GenerationBlocked('Steps must be a positive integer')
        ensemble = _value(tp, 'ensemble', 'task.parameters.ensemble', missing, 'ENSEMBLE')
        # ASE exports positions/cell without inventing molecular bonds, charges or atom types.
        try:
            from ase.io import write
            from io import StringIO
            coord_buffer = StringIO()
            write(coord_buffer, atoms, format='extxyz')
            files['coordinates.extxyz'] = coord_buffer.getvalue()
        except Exception as exc:
            warnings.append(f'ASE coordinate export unavailable: {exc}')
        # The unit system is an explicit engine-generation choice, not a scientific default.
        units = lammps_units or _value({}, 'units', 'generation.lammps.units', missing, 'LAMMPS_UNITS')
        if lammps_units == 'real':
            timestep = dt
        elif lammps_units == 'metal':
            timestep = dt / 1000 if isinstance(dt, (int, float)) else '__REQUIRED_TIMESTEP_ENGINE_UNITS__'
        else:
            timestep = '__REQUIRED_TIMESTEP_ENGINE_UNITS__'
        if timestep == '__REQUIRED_TIMESTEP_ENGINE_UNITS__':
            missing.append({'path': 'generation.lammps.timestep_engine_units', 'placeholder': timestep,
                            'reason': 'Select LAMMPS units to convert the timestep'})
        if ensemble == 'nve':
            integrator = 'nve'
        else:
            integrator = '__REQUIRED_ENSEMBLE_FIX__'
            missing.append({'path': 'generation.lammps.ensemble_fix', 'placeholder': integrator,
                            'reason': 'Thermostat/barostat parameters and algorithm must be resolved'})
        atom_style = _value({}, 'atom_style', 'generation.lammps.atom_style', missing, 'ATOM_STYLE')
        data_file = _value({}, 'data_file', 'generation.lammps.data_file', missing, 'LAMMPS_DATA_FILE')
        pair_style = _value({}, 'pair_style', 'generation.lammps.pair_style', missing, 'PAIR_STYLE')
        pair_coeff = _value({}, 'pair_coeff', 'generation.lammps.pair_coefficients', missing, 'PAIR_COEFFICIENTS')
        # Preserve all explicitly requested NPT controls in the generated template.
        # Algorithm names do not imply a valid LAMMPS fix: coupling constants,
        # temperature, pressure, and topology may still be unresolved.
        npt_comments = ''
        if ensemble == 'npt':
            pressure = tp.get('pressure_bar')
            barostat = tp.get('barostat')
            temperature = tp.get('temperature_K')
            thermostat = tp.get('thermostat')
            if pressure is not None:
                npt_comments += f'# Target pressure requested (bar): {pressure}\n'
                if units == 'real':
                    npt_comments += f'# Target pressure in LAMMPS real units (atm): {pressure / 1.01325:.9g}\n'
                elif units == 'metal':
                    npt_comments += f'# Target pressure in LAMMPS metal units (bar): {pressure}\n'
            else:
                npt_comments += '# Target pressure: __REQUIRED_TARGET_PRESSURE__\n'
                missing.append({'path':'task.parameters.pressure_bar', 'placeholder':'__REQUIRED_TARGET_PRESSURE__', 'reason':'NPT target pressure not specified'})
            if barostat is not None:
                npt_comments += f'# Barostat requested: {barostat}\n'
                warnings.append('Requested barostat is recorded but not mapped to a LAMMPS fix; algorithms and ensembles may not be equivalent.')
            else:
                npt_comments += '# Barostat: __REQUIRED_BAROSTAT__\n'
                missing.append({'path':'task.parameters.barostat', 'placeholder':'__REQUIRED_BAROSTAT__', 'reason':'NPT barostat not specified'})
            npt_comments += f'# Target temperature (K): {temperature if temperature is not None else "__REQUIRED_TEMPERATURE_K__"}\n'
            npt_comments += f'# Thermostat requested: {thermostat if thermostat is not None else "__REQUIRED_THERMOSTAT__"}\n'
        files['in.lammps'] = ('# SimSpeak NON-RUNNABLE template\n'
            '# coordinates.extxyz contains ASE-exported geometry, NOT molecular topology.\n'
            f'units {units}\natom_style {atom_style}\nread_data {data_file}\n'
            f'# Force field requested: {ff}\n'
            f'pair_style {pair_style}\npair_coeff {pair_coeff}\n'
            f'# Ensemble requested: {ensemble}\n{npt_comments}fix integrator all {integrator}\n'
            f'# Timestep requested (fs): {dt}\ntimestep {timestep}\n'
            f'run {steps}\n')
        warnings.append('ASE-exported coordinates are not a force-field-typed LAMMPS data file. Bonded topology, charges and parameters are unresolved.')
        warnings.append('LAMMPS template is not executable until all placeholders and model-specific requirements are resolved.')
    report = {'engine': engine, 'mode': 'template', 'runnable': False, 'executed': False,
              'scientifically_validated': False, 'unresolved': missing, 'warnings': warnings,
              'structure_species': symbols, 'task': spec.task.type}
    files['spec.json'] = json.dumps(spec.model_dump(mode='json'), indent=2)
    files['generation_report.json'] = json.dumps(report, indent=2)
    files['structure/' + filename] = structure_bytes
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return QEPackage(stream.getvalue(), tuple(files))
