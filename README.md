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

### Quantum ESPRESSO geometry optimization (input generation)

The ASE/QE adapter now supports `task.type: optimize` as a **fixed-cell ionic relaxation** (`calculation = 'relax'`), in addition to `single_point`. It translates `task.parameters.fmax_ev_ang` into QE's `forc_conv_thr` in Ry/Bohr. Template generation leaves missing scientific values and the QE-specific ionic optimizer as explicit `__REQUIRED_...__` markers and lists them in `generation_report.json`; the resulting file is **not runnable** until resolved. Strict generation requires the user to choose `bfgs` or `damp` as a generation-time option (outside the universal JSON). Cell relaxation (`vc-relax`) is not supported. No simulations are executed. ASE/Streamlit runtime behavior needs verification in an environment with those dependencies installed.

## Integrated v0.2 preview: four-engine template generation

The Streamlit generation panel now provides a common selection interface for **Quantum ESPRESSO, VASP, CP2K, and LAMMPS**. This is an integrated **template preview**, not a fully runnable multi-engine release. Engine selection is outside the four-field scientific schema. The ZIP includes `spec.json`, the uploaded structure, and `generation_report.json` with unresolved choices.

| Engine | Supported draft | Generated files | Important limits |
| --- | --- | --- | --- |
| Quantum ESPRESSO | Periodic plane-wave DFT single-point / fixed-cell optimize | `pw.in` | Uses the existing ASE-backed structure reader; pseudopotentials, missing numerical settings and optimizer remain placeholders |
| VASP | Periodic plane-wave DFT single-point / fixed-cell optimize | `INCAR`, `KPOINTS`, `POSCAR`, `POTCAR_REQUIRED.txt` | ASE writes POSCAR; POTCAR not generated; optimization algorithm and missing scientific settings unresolved |
| CP2K | Periodic localized-basis GPW DFT single-point / optimize | `cp2k.inp` | Explicit basis/potential library placeholders; CP2K grid cutoff is not interchangeable with universal plane-wave cutoff; GPW implementation choices remain unresolved |
| LAMMPS | Classical MD | `in.lammps` | Requires engine-specific atom style, units, data/topology, force-field mappings and integrator settings; not executable |

**All four template types are marked non-runnable**, including templates with no unresolved placeholders: the generation report does not certify scientific completeness or compatibility. No simulation is executed. This release does not implement a universal automatic force-field conversion or pseudopotential retrieval. No arbitrary engine defaults are selected as scientific decisions. Existing chat editing and undo behavior are preserved.

### Testing and known gaps

Run `python -m pytest -q tests/` in an environment with the project dependencies installed. The v0.2 adapter regression tests cover placeholder reporting, task incompatibility, and structure source matching. ASE and Streamlit were unavailable in the development runtime; **the four-engine writers and interactive UI have not been end-to-end verified with actual installed dependencies**. Validate generated files against each engine before using them. The LAMMPS and CP2K outputs are intentionally skeletons, not fully translatable scientific input decks.

## LAMMPS adapter improvements (coordinate export and explicit units)

LAMMPS bundles now attempt to include `coordinates.extxyz` exported by ASE. This is **coordinate geometry only**, not a LAMMPS data file with bonded topology, force-field atom typing or charges. Accordingly `read_data` remains a placeholder. For a selected LAMMPS unit system (`real` or `metal`) the explicitly specified timestep in femtoseconds is converted to LAMMPS time units (fs or ps respectively); without a selection the timestep remains unresolved. The NVE ensemble maps to `fix ... nve`; NVT/NPT remain unresolved because coupling parameters and algorithms are not uniquely specified. The universal JSON is unchanged. Generated files are non-runnable templates and must not be executed without completing and validating all missing settings.

### Barostat chat and LAMMPS NPT template (v0.2 update)

Standalone prompts such as `Use a Berendsen barostat`, `Barostat: Monte Carlo`,
`Change barostat to Nose-Hoover`, and `Clear the barostat` now update the
universal `task.parameters.barostat` field. A barostat name does not imply an
ensemble, pressure, or thermostat. Conflicting names in one prompt are rejected.

LAMMPS NPT templates preserve explicitly supplied target pressure (bar and
converted LAMMPS units), target temperature, thermostat, and barostat as
comments. They deliberately do not invent a `fix npt` command or coupling
constants. The generated bundle remains marked non-runnable until all engine
and scientific requirements are resolved.

## Consolidated v0.2 release (temperature + NPT adapter)

This package consolidates the standalone temperature extraction regression fix,
thermostat/barostat disambiguation, and the improved LAMMPS adapter into one app.
Use **this extracted directory** when launching Streamlit; do not mix `app.py`
with `simspeak/` modules from earlier ZIP releases.

For LAMMPS, choose the **LAMMPS unit system** in the generation UI. With `real`
units, 2 fs is written as `timestep 2.0`; with no selected units, a placeholder
is retained. The NPT template records pressure, temperature, thermostat and
barostat, but remains non-runnable until force-field/topology and integration
parameters are resolved. No scientific defaults are inserted.

Regression coverage includes a combined chat-to-JSON-to-LAMMPS NPT template test.

## v0.3 integrated reference workflows

See [V03_RELEASE_REPORT.md](V03_RELEASE_REPORT.md). The Streamlit application now has two opt-in reference generators (argon LJ/LAMMPS NPT and silicon PBE/QE SCF). Reference parameters must be explicitly approved or supplied. Neither engine is run by the application. The reference packages are distinct from the conservative generic engine templates.

### v0.3 structure-source update

In **Generate engine input files**, choose **Generate standard crystal (ASE)** or **Upload structure file**. The generated-crystal option requires an element symbol, crystal type (FCC/BCC/simple cubic/diamond), lattice parameter in angstrom, and three integer supercell repetitions. All values must be explicitly entered; there are no scientific defaults. SimSpeak builds the crystal with ASE, exports a CIF, and bundles `structure_generation.json` with the generated input template. The universal JSON remains four-field; structure-builder choices are generation-time metadata. Upload remains supported for CIF/XYZ/POSCAR/VASP. A generated crystal does not automatically make the engine input runnable: missing force-field and pseudopotential settings are still reported.
