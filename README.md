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

## Parameter dropdowns

The Streamlit form now uses context-sensitive dropdowns for calculator, task, ensembles, potentials, XC functional, basis, thermostat, barostat and initial state. Numeric quantities remain explicit text inputs with numeric validation. Blank selections mean unspecified. No ASE integration or simulation generation is included.

## Chat-to-form extraction (v0.1)

The chat panel now extracts a **conservative subset** of explicit MD/DFT facts into the editable form. Unspecified parameters remain empty. The extractor recognizes selected method/task words, engine names, structure filenames, and a small set of numeric quantities with explicit units. It does **not** infer a silicon structure, choose potentials, or fill missing defaults. Conflicting existing fields are never silently overwritten.

The optional **Use Ollama proposals** checkbox calls a locally running Ollama server (`SIMSPEAK_OLLAMA_MODEL`, default `qwen3:4b`). Its proposal is intersected with independently recognized literal facts. Claims not supported by the deterministic extractor are discarded. If Ollama is unavailable, the app falls back to conservative rule-based extraction.

This is deliberately a limited proof of concept: the deterministic allowlist may miss legitimate scientific phrasing, and lexical extraction is not a complete semantic evidence verifier. The UI validation status reports *minimal registry completeness*, not scientific or execution readiness. Evidence displayed in the UI applies to the last extraction and is cleared after manual form edits. No ASE generation or simulation execution is included.


### Force-field dropdown and standalone chat updates

MD force-field choices include Tersoff, EAM, Lennard-Jones, OPLS-AA,
CGenFF 2.0 (also recognized as `GenFF-2.0`), and AMBER ff19SB.
`amber_ff19sb` is a **specific protein force-field version**, not a
claim that an arbitrary latest AMBER software release defines a universal
force field. Force-field selections are labels only: parameterization,
compatibility, and availability are **not** checked in v0.1.

Standalone chat turns such as `Use OPLS-AA force field`, `Duration is 10 ps`,
and `Run for 2 ns` are recognized without repeating the MD method. Durations
are normalized to ps. Unspecified values remain absent.
