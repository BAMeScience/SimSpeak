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

### Ollama setup

Follow the instructions in the [official docs](https://docs.ollama.com/).

#### Install Ollama

If not already installed, run:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

And start the Ollama server:
```bash
ollama serve
```

In another terminal, verify the installation
```bash
ollama --version
```

#### Download a model

Run:
```bash
ollama pull <model-name>
```

Where `<model-name>` is defined as in the list of [Ollama supported models](https://ollama.com/search). For example, for Qwen3 4B:
```bash
ollama pull qwen3:4b
```

And check the installed models:
```bash
ollama list
```

#### Test the model independently

The Ollama server is run in `localhost:11434`, and you can inspect the downloaded models in `http://localhost:11434/api/tags`.

You can test a model in a chat version running:
```bash
ollama run <model-name>
```

E.g.:
```bash
ollama run qwen3:4b
```
And try:
```bash
Extract the chemical element, lattice parameter, and
exchange-correlation functional from this description:

Calculate silicon using PBE with a lattice parameter of 5.43 Å.
```

You can see the thinking process for the model, e.g.:
```text
<think>
Okay, let's see. The user wants me to extract the chemical element,
lattice parameter, and exchange-correlation functional from the
description: "Calculate silicon using PBE with a lattice parameter of 5.43
Å."

First, I need to break down the sentence. The main subject is "Calculate
silicon using PBE..." So the chemical element here is silicon, which is
Si. The lattice parameter is given as 5.43 Å. The exchange-correlation
functional is PBE, which stands for Perdew-Burke-Ernst.

Wait, but I should confirm if PBE is the correct functional. PBE is indeed
the standard for the exchange-correlation functional in density functional
theory calculations. So the exchange-correlation functional is PBE.

Let me check again. The description mentions using PBE, so that's the
functional. The lattice parameter is 5.43 Å. The element is silicon. So
the answer should be element: Si, lattice parameter: 5.43 Å,
exchange-correlation functional: PBE.

I think that's all. No other details are provided, so those three elements
are the ones to extract.
</think>

The chemical element is **silicon (Si)**, the lattice parameter is **5.43
Å**, and the exchange-correlation functional is **PBE**.

**Extracted Information:**
- **Chemical Element**: Si
- **Lattice Parameter**: 5.43 Å
- **Exchange-Correlation Functional**: PBE
```

End the interactive chat by typing:
```bash
/bye
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
