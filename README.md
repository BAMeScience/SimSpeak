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

| Phase                     | Components                                                        | Expected result |
| ---                       | ---                                                               | --- |
| **1. Foundation**         | Repository, Pydantic schema, ASE structure builder, Streamlit UI  | Enter parameters manually and generate a silicon structure |
| **2. Input generation**   | Quantum ESPRESSO and GPAW adapters                                | Generate and download simulation input files |
| **3. LLM integration**    | Ollama client, extraction prompts, structured outputs             | Convert natural language into the schema |
| **4. Memory**             | SQLite, conversation management, specification revisions          | Modify experiments through successive messages |
| **5. Integration**        | Error handling, validation, tests, UI improvements                | Fully functional local demo |


```text
                       SimSpeak
                          │
                          ▼
                ┌───────────────────┐
                │    STREAMLIT      │
                │                   │
                │ Chat interface    │
                │ Editable form     │
                │ JSON preview      │
                │ Generated files   │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │ SIMULATION SERVICE│
                │                   │
                │ Create            │
                │ Update            │
                │ Validate          │
                │ Generate          │
                └─────────┬─────────┘
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │ OLLAMA  │ │PYDANTIC │ │ MEMORY  │
        │         │ │         │ │         │
        │ Text →  │ │ Schema  │ │ SQLite  │
        │ Changes │ │Validate │ │History  │
        └─────────┘ └─────────┘ └─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │  ASE / GENERATORS │
                │                   │
                │ Quantum ESPRESSO  │
                │ GPAW              │
                │ Future: VASP, MD  │
                └─────────┬─────────┘
                          │
                          ▼
                   GENERATED FILES
```