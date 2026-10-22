"""Explicit ASE crystal builder; structure selection is generation-time metadata."""
from __future__ import annotations

from io import BytesIO
import math

from simspeak.qe_generator import GenerationBlocked

SUPPORTED_CRYSTALS = ('fcc', 'bcc', 'sc', 'diamond')


def generate_crystal(element: str, crystal: str, lattice_a: float, repeat: tuple[int, int, int]):
    """Return (CIF bytes, filename, provenance), without scientific defaults."""
    try:
        from ase.data import atomic_numbers
        from ase.build import bulk
        from ase.io import write
    except ImportError as exc:
        raise GenerationBlocked("ASE is required for automatic crystal generation") from exc

    element = element.strip()
    if element not in atomic_numbers:
        raise GenerationBlocked('Enter a valid chemical element symbol (e.g. Ar or Si)')
    if crystal not in SUPPORTED_CRYSTALS:
        raise GenerationBlocked('Unsupported crystal type')
    if isinstance(lattice_a, bool) or not isinstance(lattice_a, (int, float)) or not math.isfinite(lattice_a) or lattice_a <= 0:
        raise GenerationBlocked('Lattice parameter a must be positive and finite (angstrom)')
    if len(repeat) != 3 or any(type(n) is not int or n <= 0 or n > 30 for n in repeat):
        raise GenerationBlocked('Supercell repetitions must be three integers from 1 to 30')
    try:
        atoms = bulk(element, crystal, a=float(lattice_a), cubic=True)
        atoms = atoms.repeat(repeat)
        buffer = BytesIO()
        write(buffer, atoms, format='cif')
    except Exception as exc:
        raise GenerationBlocked(f'ASE crystal construction failed: {exc}') from exc
    provenance = {'source_type': 'ase_generated_crystal', 'element': element, 'crystal': crystal,
                  'lattice_parameter_angstrom': float(lattice_a), 'supercell': list(repeat),
                  'number_of_atoms': len(atoms)}
    return buffer.getvalue(), 'generated_crystal.cif', provenance
