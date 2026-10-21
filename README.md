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

## Publishing simulation specifications through the API

SimSpeak uses Streamlit for its interface and FastAPI to share a saved
`SimulationSpec` snapshot with another application. The current chat backend
remains a mock. Neither Ollama nor a DFT executable is needed for these steps.

### Install

From the repository root:

```bash
uv add fastapi uvicorn httpx
uv sync --extra dev
```

Ensure `simspeak/api.py` exists (it implements `POST /specs` and
`GET /specs/{spec_id}` with a SQLite database). The accompanying API tests
expect an `api.DB_PATH` setting and an `api.init_database()` function.

### Run locally

Start the API in terminal 1:

```bash
uv run uvicorn simspeak.api:app --reload --port 8000
```

Browse the interactive API documentation: http://localhost:8000/docs

Start Streamlit in terminal 2:

```bash
uv run streamlit run app.py
```

Open the application at http://localhost:8501. Fill the simulation form,
click **Apply changes**, and then click **Publish specification**. The UI shows
an ID-specific URL for the published snapshot.

For a nondefault API URL, set `SIMSPEAK_API_URL` **before** starting Streamlit:

```bash
SIMSPEAK_API_URL=http://localhost:8000 uv run streamlit run app.py
```

### Retrieve a specification

Use the published ID returned by the app:

```bash
curl http://localhost:8000/specs/YOUR_SPEC_ID
```

The JSON contains `id`, `specification`, and `generation_issues`. A successful
publication **does not mean the specification is ready to run**: the Pydantic
model permits incomplete drafts. The downstream application must check
`generation_issues` and validate engine-specific execution requirements.

Each publish action creates a **new, immutable snapshot**; it does not update
previous IDs. Clearing the chat does not remove published snapshots.

### Tests

```bash
uv run pytest -v tests/test_api.py
uv run pytest -v
```

The API tests use a temporary SQLite database and do not need a running server.

### Sharing with a teammate

`localhost` is only accessible on your own computer. If the teammate runs
another application on their laptop, you need a reachable server or a secure
network connection. The demo API has **no authentication**, so do not expose
it to an untrusted network or the public internet as-is. Add authentication
and HTTPS before wider deployment.
