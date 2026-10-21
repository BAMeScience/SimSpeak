# SimSpeak

Run:
```bash
uv venv
. .venv/bin/activate
```

And:
```bash
uv sync
```

Make sure to download [Ollama](https://ollama.com/) and pull a small model following its [docs](https://docs.ollama.com/) page.

Example implementation:

```python
from ollama import Client
from pydantic import BaseModel


class Draft(BaseModel):
    sample_name: str | None
    material: str | None


client = Client(host="http://127.0.0.1:11434")
response = client.chat(
    model="qwen3:4b",
    messages=[{"role": "user", "content":
        "Extract facts; use null if missing. "
        "Sample S-001 is NiO."}],
    format=Draft.model_json_schema(),
    think=False,
    options={"temperature": 0},
)

draft = Draft.model_validate_json(
    response.message.content
)

print(draft.model_dump())
```
