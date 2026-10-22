"""Chat integration boundary.

Replace send_message() with an Ollama call in a later step.
Keep its signature and return type stable for the Streamlit UI.
"""

from dataclasses import dataclass

from simspeak.llm.client import extract_changes
from simspeak.models import SimulationSpec
from simspeak.specification import update_specification


@dataclass
class ChatResult:
    reply: str
    specification: SimulationSpec
    changes: dict


def process_simulation_message(
    message: str,
    current_spec: SimulationSpec,
    history: list[dict[str, str]] | None = None,
) -> ChatResult:
    """Process a message and return the updated simulation."""

    extracted = extract_changes(
        message=message,
        current_spec=current_spec,
        history=history,
    )

    changes = extracted.get_changes()

    if not changes:
        return ChatResult(
            reply=(
                "I couldn't identify any supported simulation "
                "parameters to update. Please clarify your request."
            ),
            specification=current_spec,
            changes={},
        )

    updated_spec = update_specification(
        current=current_spec,
        changes=changes,
    )

    description = "\n".join(
        f"- **{field}**: `{value}`" for field, value in changes.items()
    )

    reply = f"I've updated the simulation specification:\n\n{description}"

    return ChatResult(
        reply=reply,
        specification=updated_spec,
        changes=changes,
    )


def send_message(message: str, history: list[dict[str, str]]) -> str:
    """Return a mock reply; no LLM or network access is required."""
    if not message.strip():
        raise ValueError("Message must not be empty")

    return (
        "**Mock backend received your request:**\n\n"
        f"> {message}\n\n"
        "Next, we'll extract parameters into editable simulation fields. "
        "For now this is only a connectivity test."
    )
