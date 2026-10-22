"""Strict, non-executing Quantum ESPRESSO input generation via ASE.

Engine selection and resource files are generation-time inputs, not schema fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
import json
import math
import zipfile

from simspeak.models import SimulationSpec
from simspeak.validation import validate


class GenerationBlocked(ValueError):
    """The requested translation cannot be performed without assumptions."""


@dataclass(frozen=True)
class QEPackage:
    content: bytes
    filenames: tuple[str, ...]


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise GenerationBlocked(f'{label} must be a positive finite number')
    return float(value)


def generate_qe(spec: SimulationSpec, structure_bytes: bytes, *, filename: str) -> QEPackage:
    """Produce a ZIP with pw.in, structure, manifest; never execute a calculation.

    Only plane-wave ground-state single-point DFT is supported in this first adapter.
    Optimization is blocked until convergence semantics are mapped explicitly.
    """
    if spec.method != 'dft' or spec.task.type != 'single_point':
        raise GenerationBlocked('QE v0 adapter supports DFT single_point only; optimization and MD are not mapped')
    if spec.calculator.name not in (None, 'espresso'):
        raise GenerationBlocked('Selected calculator conflicts with Quantum ESPRESSO; choose espresso or leave it unspecified')
    if not spec.structure.source:
        raise GenerationBlocked('Specify a structure source')
    if not filename or Path(filename).name != filename or filename != Path(spec.structure.source).name:
        raise GenerationBlocked('Uploaded structure filename must match structure.source')
    if not structure_bytes:
        raise GenerationBlocked('Upload the structure file referenced by structure.source')
    report = validate(spec, user_edited=True)
    if report.status != 'VALID':
        raise GenerationBlocked('Specification validation failed: ' + '; '.join(f'{d.path}: {d.message}' for d in report.diagnostics))
    cp = spec.calculator.parameters
    if cp.get('basis') != 'plane_wave':
        raise GenerationBlocked('QE adapter requires an explicit plane_wave basis')
    xc = cp.get('xc')
    if xc not in ('PBE', 'PBEsol', 'LDA'):
        raise GenerationBlocked('XC must be explicitly selected from PBE, PBEsol, LDA')
    cutoff = _positive(cp.get('cutoff_ev'), 'Plane-wave kinetic energy cutoff (eV)')
    mesh = cp.get('kpoints')
    if not isinstance(mesh, (list, tuple)) or len(mesh) != 3 or any(type(k) is not int or k <= 0 for k in mesh):
        raise GenerationBlocked('Specify three positive integer k-point mesh dimensions')
    pseudos = cp.get('pseudopotentials')
    if not isinstance(pseudos, dict) or not pseudos or any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() or Path(v).name != v for k, v in pseudos.items()):
        raise GenerationBlocked('Specify pseudopotential filenames per chemical element (no paths)')
    try:
        from ase.io import read
        from ase.io.espresso import write_espresso_in
        from ase.units import Rydberg
    except ImportError as exc:
        raise GenerationBlocked('ASE must be installed to generate Quantum ESPRESSO input') from exc
    try:
        atoms = read(BytesIO(structure_bytes), format=Path(filename).suffix.lstrip('.').lower())
    except Exception as exc:
        raise GenerationBlocked(f'ASE could not read the structure: {exc}') from exc
    if isinstance(atoms, list) or len(atoms) == 0:
        raise GenerationBlocked('Structure must contain atoms')
    if not all(atoms.pbc) or abs(atoms.cell.volume) < 1e-12:
        raise GenerationBlocked('This adapter requires a fully periodic structure with a nonzero cell')
    elements = set(atoms.get_chemical_symbols())
    if set(pseudos) != elements:
        raise GenerationBlocked(f'Pseudopotential mapping must exactly cover {sorted(elements)}')
    # Do not invent an ecutrho, occupations, smearing, spin, or mixing scheme.
    # ASE's writer handles file syntax; user-supplied pseudo files are not bundled.
    stream = StringIO()
    try:
        write_espresso_in(
            stream, atoms, pseudopotentials=pseudos, kpts=tuple(mesh),
            input_data={
                'control': {'calculation': 'scf'},
                'system': {'ecutwfc': cutoff / Rydberg, 'input_dft': xc},
            },
        )
    except Exception as exc:
        raise GenerationBlocked(f'ASE Quantum ESPRESSO writer failed: {exc}') from exc
    manifest = {
        'engine': 'quantum_espresso', 'adapter': 'qe_single_point_v0',
        'executed': False, 'scientifically_validated': False,
        'cutoff_input_ev': cutoff, 'kpoints_mesh': list(mesh),
        'pseudopotential_files_required': pseudos,
        'warnings': [
            'Pseudopotential files are NOT included or validated; place matching files where QE expects them.',
            'QE and ASE may apply additional writer/engine defaults; inspect the generated input before running.',
            'Pseudopotential-dependent cutoffs, charge, spin, occupations, and convergence have not been validated.',
        ],
    }
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pw.in', stream.getvalue())
        archive.writestr('spec.json', json.dumps(spec.model_dump(mode='json'), indent=2))
        archive.writestr('generation_report.json', json.dumps(manifest, indent=2))
        archive.writestr('structure/' + filename, structure_bytes)
    return QEPackage(output.getvalue(), ('pw.in', 'spec.json', 'generation_report.json', 'structure/' + filename))
