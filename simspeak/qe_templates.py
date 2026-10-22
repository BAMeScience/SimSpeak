"""ASE-backed QE template creation, explicitly marking unresolved scientific inputs."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import json
import math
import zipfile
from simspeak.models import SimulationSpec
from simspeak.qe_generator import QEPackage, GenerationBlocked

PLACEHOLDER = '__REQUIRED_{name}__'

def generate_qe_template(spec: SimulationSpec, structure_bytes: bytes, *, filename: str) -> QEPackage:
    if spec.method not in (None, 'dft') or spec.task.type not in (None, 'single_point', 'optimize'):
        raise GenerationBlocked('Template adapter supports DFT single_point and optimize (or unspecified method/task).')
    if spec.calculator.name not in (None, 'espresso'):
        raise GenerationBlocked('Calculator conflicts with Quantum ESPRESSO')
    if not filename or Path(filename).name != filename or not structure_bytes:
        raise GenerationBlocked('Upload a named, nonempty structure file')
    if spec.structure.source and Path(spec.structure.source).name != filename:
        raise GenerationBlocked('Structure filename does not match structure.source')
    try:
        from ase.io import read
        from ase.units import Rydberg, Bohr
    except ImportError as exc:
        raise GenerationBlocked('Install ASE to read the structure and generate templates') from exc
    try:
        atoms = read(BytesIO(structure_bytes), format=Path(filename).suffix.lstrip('.').lower())
    except Exception as exc:
        raise GenerationBlocked(f'ASE could not read structure: {exc}') from exc
    if isinstance(atoms, list) or len(atoms) == 0 or not all(atoms.pbc) or abs(atoms.cell.volume) < 1e-12:
        raise GenerationBlocked('A nonempty fully periodic structure with a valid cell is required')
    cp = spec.calculator.parameters
    if cp.get('basis') not in (None, 'plane_wave'):
        raise GenerationBlocked('QE plane-wave template does not support a localized basis')
    unresolved = []
    def required(path, marker):
        unresolved.append({'path': path, 'placeholder': marker, 'reason': 'Required for a runnable QE input; no default selected'})
        return marker
    xc = cp.get('xc')
    if xc not in (None, 'PBE', 'PBEsol', 'LDA'):
        raise GenerationBlocked('XC functional is unsupported by this adapter')
    xc = xc or required('calculator.parameters.xc', PLACEHOLDER.format(name='XC_FUNCTIONAL'))
    cutoff = cp.get('cutoff_ev')
    if cutoff is None:
        cutoff_ry = required('calculator.parameters.cutoff_ev', PLACEHOLDER.format(name='ECUTWFC_RY'))
    elif isinstance(cutoff, bool) or not isinstance(cutoff, (float, int)) or cutoff <= 0:
        raise GenerationBlocked('Cutoff must be positive and expressed in eV')
    else:
        cutoff_ry = f'{cutoff / Rydberg:.12g}'
    kpts = cp.get('kpoints')
    if kpts is None:
        kline = required('calculator.parameters.kpoints', PLACEHOLDER.format(name='KPOINT_GRID_3_INTEGERS')) + ' 0 0 0'
    elif not isinstance(kpts, (list, tuple)) or len(kpts) != 3 or any(type(k) is not int or k <= 0 for k in kpts):
        raise GenerationBlocked('kpoints must be three positive integers')
    else:
        kline = ' '.join(map(str, kpts)) + ' 0 0 0'
    pseudos = cp.get('pseudopotentials') or {}
    if not isinstance(pseudos, dict):
        raise GenerationBlocked('Pseudopotentials must be a species-to-filename mapping')
    elements = sorted(set(atoms.get_chemical_symbols()))
    if set(pseudos) - set(elements):
        raise GenerationBlocked('Pseudopotential mapping contains species absent from structure')
    species_lines = []
    for element in elements:
        pseudo = pseudos.get(element)
        if not pseudo:
            pseudo = required('calculator.parameters.pseudopotentials.' + element, PLACEHOLDER.format(name=element.upper()+'_PSEUDOPOTENTIAL_UPF'))
        elif not isinstance(pseudo, str) or Path(pseudo).name != pseudo:
            raise GenerationBlocked('Pseudopotential filenames must be simple filenames')
        mass = next(atom.mass for atom in atoms if atom.symbol == element)
        species_lines.append(f'{element} {mass:.8f} {pseudo}')
    # QE's forc_conv_thr is in Ry/Bohr; the universal force tolerance is eV/Angstrom.
    optimize = spec.task.type == 'optimize'
    ions_lines = []
    if optimize:
        tolerance = spec.task.parameters.get('fmax_ev_ang')
        if tolerance is None:
            force_ry_bohr = required('task.parameters.fmax_ev_ang', PLACEHOLDER.format(name='FORCE_TOLERANCE_RY_PER_BOHR'))
        elif isinstance(tolerance, bool) or not isinstance(tolerance, (float, int)) or not math.isfinite(tolerance) or tolerance <= 0:
            raise GenerationBlocked('Force tolerance must be a positive finite number in eV/Angstrom')
        else:
            force_ry_bohr = f'{tolerance * Bohr / Rydberg:.12g}'
        # Ionic optimizer is a generation-time engine-specific choice, not a universal schema field.
        ions_lines = ['&IONS', '  ion_dynamics = ' + required('generation.ion_dynamics', PLACEHOLDER.format(name='QE_ION_DYNAMICS')), '/']
    # ecutrho, occupations, spin, smearing, convergence, etc. are not invented.
    lines = ['! SimSpeak template: NOT RUNNABLE until placeholders and required settings are resolved',
             '&CONTROL', "  calculation = 'relax'" if optimize else "  calculation = 'scf'", *([f'  forc_conv_thr = {force_ry_bohr}'] if optimize else []), '/', '&SYSTEM',
             f'  ibrav = 0', f'  nat = {len(atoms)}', f'  ntyp = {len(elements)}',
             f"  input_dft = '{xc}'" if not xc.startswith('__') else f'  input_dft = {xc}',
             f'  ecutwfc = {cutoff_ry}', '/', '&ELECTRONS', '/', *ions_lines, 'ATOMIC_SPECIES', *species_lines,
             'CELL_PARAMETERS angstrom']
    lines += [' '.join(f'{x:.12g}' for x in row) for row in atoms.cell.array]
    lines += ['ATOMIC_POSITIONS angstrom']
    lines += [f'{atom.symbol} ' + ' '.join(f'{x:.12g}' for x in atom.position) for atom in atoms]
    lines += ['K_POINTS automatic', kline]
    if spec.method is None:
        required('method', PLACEHOLDER.format(name='METHOD_DFT_CONFIRMATION'))
    if spec.task.type is None:
        required('task.type', PLACEHOLDER.format(name='TASK_TYPE_CONFIRMATION'))
    # Report required confirmations even when they are not valid QE input keywords.
    report = {'engine': 'quantum_espresso', 'mode': 'template', 'executed': False,
              'runnable': False, 'scientifically_validated': False,
              'unresolved': unresolved,
              'warnings': ['This template may be incomplete even if all placeholders are resolved.',
                           'No pseudopotential compatibility, convergence or physical correctness checks performed.',
                           'ASE was used to parse the structure; the template skeleton is written by SimSpeak.']}
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('pw.in', '\n'.join(lines) + '\n')
        z.writestr('spec.json', json.dumps(spec.model_dump(mode='json'), indent=2))
        z.writestr('generation_report.json', json.dumps(report, indent=2))
        z.writestr('structure/' + filename, structure_bytes)
    return QEPackage(stream.getvalue(), ('pw.in', 'spec.json', 'generation_report.json', 'structure/' + filename))
