from pydantic import ValidationError

from simspeak.models import SimulationSpec


def optional_float(value: str) -> float | None:
    return None if not value.strip() else float(value.strip())


def optional_mesh(value: str) -> tuple[int, int, int] | None:
    if not value.strip():
        return None
    parts = value.replace("x", " ").replace("X", " ").replace(",", " ").split()
    if len(parts) != 3:
        raise ValueError("K-points must have three integers (for example: 4 4 4)")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError("K-points must contain integers only") from exc


def parse_form(raw: dict) -> SimulationSpec:
    """Build a complete replacement draft; raises ValueError/ValidationError."""
    return SimulationSpec.model_validate(
        {
            "element": raw["element"],
            "crystal_structure": raw["crystal_structure"] or None,
            "lattice_parameter": optional_float(raw["lattice_parameter"]),
            "calculation": raw["calculation"],
            "xc_functional": raw["xc_functional"],
            "cutoff_ev": optional_float(raw["cutoff_ev"]),
            "kpoints": optional_mesh(raw["kpoints"]),
            "engine": raw["engine"],
        }
    )
