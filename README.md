# SimSpeak — minimal universal simulation draft

This branch keeps the Streamlit UI and mock chat backend, replacing the DFT-only schema with a minimal four-field Pydantic draft (`structure`, `method`, `calculator`, `task`). It supports classical MD and ground-state DFT **validation only**. No ASE integration, engine input generation, or execution is implemented.

## Run

```bash
uv sync --extra dev
uv run pytest -q
uv run streamlit run app.py
```

The Streamlit form edits a draft manually; no scientific defaults are applied. Calculator and task parameters are JSON objects. The validator produces `VALID`, `INCOMPLETE`, or `INVALID` plus structured diagnostics. `VALID` is only a minimal registry check, **not** a guarantee that a simulation can run.

## LLM evidence boundary

The chat backend remains a mock and **does not populate the form**. Future LLM integrations should call `validate(spec, source_text=original_prompt, evidence={"method": "classical MD", ...})` and never set `user_edited=True`. That flag is reserved for the manually edited UI. Evidence is checked against verbatim substrings of the original prompt, with limited lexical value matching; this is intentionally conservative and **not a comprehensive semantic entailment check**. Avoid treating the current evidence checker as a proof of scientific correctness.

## Design notes

- The four-field model is intentionally permissive for incomplete drafts and forbids unknown top-level fields.
- The deterministic validator uses a deliberately small allowlist for calculator and task parameters. Expand it only with documented rules.
- `structure.source` is a reference string; no file existence or content validation occurs yet.
- `calculator.name` is user-supplied; it is not yet checked against a capability registry.
- The application has no implicit PBE, engine, structure, or timestep defaults.
