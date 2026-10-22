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

## ASE Quantum ESPRESSO input generation (experimental)

The **Generate engine input files** section adds a first, deliberately narrow ASE
adapter for **periodic DFT single-point** calculations with a plane-wave basis.
Upload the structure file matching `structure.source` and select **Generate QE
input ZIP**. The download includes `pw.in`, the original `spec.json`, a
`generation_report.json`, and the structure file. It does **not** run QE.

The adapter requires explicitly specified XC, plane-wave cutoff in eV,
three-dimensional k-point mesh, and one pseudopotential filename for every
chemical element. It converts cutoff from eV to Ry and writes `pw.in` through
`ase.io.espresso.write_espresso_in`. No pseudopotential files are provided or
validated. Geometry optimization, MD, nonperiodic systems, localized basis,
and other engines are blocked, not guessed. The engine is a generation-time
selection and does not alter the universal four-field schema.

**Important:** This is a syntax-generation proof of concept, not a fully
reproducible or scientifically validated input. ASE/QE may introduce defaults;
users must inspect the generated file and supply compatible pseudopotentials,
charge/spin, occupations, and convergence settings as appropriate. No claim is
made that the resulting input is ready to execute.

## Template generation and chat revisions

- In **Generate engine input files**, select **Template (allow missing parameters)** to create a Quantum ESPRESSO `pw.in` template using ASE to read a periodic structure. Missing XC, kinetic-energy cutoff, k-point grid and pseudopotential filenames are written as `__REQUIRED_...__` placeholders. A `generation_report.json` lists unresolved paths. The template is **not runnable**; ASE is required for structure parsing.
- **Strict** mode retains the earlier fully specified QE writer. Both modes are currently restricted to periodic DFT single-point calculations. Engine selection is not added to the universal four-field schema.
- Chat can now accept explicit changes (`Actually use PBEsol instead`, `Change PBE to PBEsol`), clears (`Clear the XC functional`), and **Undo last change**. Conflicting new values without an explicit revision request are not applied. Each accepted edit records its prior state for undo.
- No pseudopotential files are downloaded or selected automatically; no simulation is executed. Template placeholders are intentionally not executable QE syntax.
