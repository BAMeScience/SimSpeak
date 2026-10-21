"""Chat integration boundary.

Replace send_message() with an Ollama call in a later step.
Keep its signature and return type stable for the Streamlit UI.
"""


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
