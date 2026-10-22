from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SimulationChanges(BaseModel):
    """Fields proposed by the LLM.

    None represents an unspecified value.
    Only non-None values are applied.
    """

    model_config = ConfigDict(extra="forbid")

    element: str | None = None

    crystal_structure: Literal["fcc", "bcc", "diamond"] | None = None

    lattice_parameter: float | None = Field(default=None, gt=0)

    calculation: Literal["single_point", "relaxation"] | None = None

    xc_functional: Literal["PBE", "LDA"] | None = None

    cutoff_ev: float | None = Field(default=None, gt=0)

    kpoints: tuple[int, int, int] | None = None

    engine: Literal["quantum_espresso", "gpaw"] | None = None

    def get_changes(self) -> dict:
        """Return only explicitly populated parameters."""
        return self.model_dump(
            exclude_none=True,
            mode="json",
        )
