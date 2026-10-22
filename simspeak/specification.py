from collections.abc import Mapping

from simspeak.models import SimulationSpec


def update_specification(
    current: SimulationSpec,
    changes: Mapping,
) -> SimulationSpec:
    """Return a validated specification with selected fields updated."""

    current_data = current.model_dump(mode="python")

    updated_data = {**current_data, **changes}

    return SimulationSpec.model_validate(updated_data)
