import json
import os

from ollama import Client

from simspeak.llm.models import SimulationChanges
from simspeak.llm.prompts import SYSTEM_PROMPT
from simspeak.models import SimulationSpec


def extract_changes(
    message: str,
    current_spec: SimulationSpec,
    history: list[dict[str, str]] | None = None,
    client: Client | None = None,
) -> SimulationChanges:
    """Extract simulation parameter changes using Ollama."""

    if not message.strip():
        raise ValueError("Message cannot be empty.")

    if client is None:
        client = Client(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://localhost:11434",
            )
        )

    model = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")

    context = {
        "current_specification": current_spec.model_dump(mode="json"),
        "recent_conversation": (history or [])[-6:],
        "new_message": message,
    }

    response = client.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": json.dumps(
                    context,
                    ensure_ascii=False,
                ),
            },
        ],
        format=SimulationChanges.model_json_schema(),
        options={
            "temperature": 0,
        },
        think=False,
    )

    return SimulationChanges.model_validate_json(response.message.content)
