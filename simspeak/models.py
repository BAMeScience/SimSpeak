"""Canonical, editable draft schema shared by the UI and future Ollama/ASE code."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SimulationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    element: str | None = Field(default=None, description="Chemical symbol, e.g. Si")
    crystal_structure: Literal["fcc", "bcc", "diamond"] | None = None
    lattice_parameter: float | None = Field(default=None, gt=0, description="Angstrom")
    calculation: Literal["single_point", "relaxation"] = "single_point"
    xc_functional: Literal["PBE", "LDA"] = "PBE"
    cutoff_ev: float | None = Field(default=None, gt=0, description="eV")
    kpoints: tuple[int, int, int] | None = None
    engine: Literal["quantum_espresso", "gpaw"] = "quantum_espresso"

    @field_validator("element")
    @classmethod
    def clean_element(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("kpoints")
    @classmethod
    def positive_mesh(
        cls, value: tuple[int, int, int] | None
    ) -> tuple[int, int, int] | None:
        if value is not None and any(k <= 0 for k in value):
            raise ValueError("Each k-point grid dimension must be a positive integer")
        return value


def generation_issues(spec: SimulationSpec) -> list[str]:
    """Completeness checks only; not a scientific convergence guarantee."""
    missing = []
    for field, label in (
        ("element", "Element"),
        ("crystal_structure", "Crystal structure"),
        ("lattice_parameter", "Lattice parameter"),
        ("cutoff_ev", "Plane-wave cutoff"),
        ("kpoints", "K-point grid"),
    ):
        if getattr(spec, field) is None:
            missing.append(label)
    if spec.engine == "quantum_espresso":
        missing.append("QE pseudopotential (configure in a later step)")
    return missing
