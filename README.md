# SimSpeak

## Development

### Requirements

- Python 3.14
- uv
- Make sure to download [Ollama](https://ollama.com/) and pull a small model following its [docs](https://docs.ollama.com/) page.

### Installation

Clone the repository:

```bash
git clone https://github.com/BAMeScience/SimSpeak.git
cd SimSpeak
git checkout app-jmp
```

Install the project and development dependencies:
```bash
uv sync --extra dev
```

Run Streamlit
```bash
uv run streamlit run app.py
```

Open http://localhost:8501.

Run tests
```bash
uv run pytest -v
```

### Example implementation

```python
from ollama import Client
from pydantic import BaseModel


class Draft(BaseModel):
    sample_name: str | None
    material: str | None


client = Client(host="http://127.0.0.1:11434")
response = client.chat(
    model="qwen3:4b",
    messages=[
        {
            "role": "user",
            "content": "Extract facts; use null if missing. Sample S-001 is NiO.",
        }
    ],
    format=Draft.model_json_schema(),
    think=False,
    options={"temperature": 0},
)

draft = Draft.model_validate_json(response.message.content)

print(draft.model_dump())
```

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