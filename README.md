# SimSpeak v0.3 — Natural-language simulation specification prototype

SimSpeak is a proof of concept for translating natural-language atomistic simulation instructions into a **code-independent scientific specification**. It provides a Streamlit interface for editing the specification, conservative chat-based parameter extraction, structure generation or upload, and preliminary simulation-engine input templates.

**Primary deliverable:** a portable, inspectable JSON representation of simulation intent. **Not a simulation execution platform.** Generated engine inputs may be incomplete or non-runnable; scientific correctness, convergence, and execution are not certified.

## Architecture

The universal specification has exactly four top-level fields:

- `structure` — description or source of the atomic structure
- `method` — scientific method (e.g. classical MD or DFT)
- `calculator` — model and numerical parameters
- `task` — requested calculation or simulation protocol

Engine-specific translation is separate from this specification. The interface includes template adapters for Quantum ESPRESSO, VASP, CP2K, and LAMMPS, but these are not equally complete and are **not guaranteed executable**.

## Two demonstrated workflows

**A. Argon / classical MD / LAMMPS:** Enter a request for a periodic FCC argon crystal, Lennard-Jones model, NPT at 300 K and 1 bar, 2 fs timestep, and 20,000 steps. In the structure section choose *Generate standard crystal (ASE)*, enter `Ar`, `fcc`, a **user-approved example** lattice parameter of `5.26 Å`, and `4,4,4` repetitions. Generate an input template. The separate explicit argon reference workflow requires approval of its scientific configuration; do not mistake a generic LAMMPS template for a runnable file.

**B. Silicon / DFT / Quantum ESPRESSO:** Request a PBE single-point calculation for diamond-cubic silicon with a 50 Ry plane-wave cutoff and 6×6×6 k-point grid. Generate a standard crystal with `Si`, `diamond`, an explicitly chosen example lattice parameter of `5.43 Å`, and `1,1,1` repetitions. QE generation may require a user-supplied compatible Si `.UPF` pseudopotential and matching metadata. No pseudopotential is automatically invented or downloaded.

Both workflows were reported by the project user to pass their local **input-generation UI tests**. This does not mean that the generated files were executed with LAMMPS or Quantum ESPRESSO.

## Install and run

Requirements: Python **3.14+**, `uv` (recommended), and a machine able to install the project dependencies.

```bash
uv sync --extra dev
uv run streamlit run app.py
```

To run tests:

```bash
uv run pytest -q
```

Alternatively, install the dependencies from `pyproject.toml` into an appropriate Python environment. Ollama integration is optional; without it, the app uses conservative rule-based extraction.

## What is verified

- Local test run in the packaging environment: **133 non-UI tests passed, 1 skipped** (`pytest --ignore=tests/test_app.py`).
- Full test collection was blocked because `streamlit` was not installed in that environment.
- The project user confirmed both reference input-generation UI workflows passed on their machine.
- No LAMMPS or Quantum ESPRESSO execution test was performed.

## Scope and limitations

- Extraction handles a limited set of explicitly stated parameters and may miss valid phrasing.
- JSON completeness checks are not guarantees of physical adequacy or runnable inputs.
- Structure creation requires explicit lattice parameters and supercell dimensions; example values are **not automatically justified** for all conditions.
- Uploaded XYZ/CIF/POSCAR files must be structurally valid and compatible with the selected reader.
- Force-field coefficients, topology, pseudopotentials, convergence settings, and code-specific controls may remain unresolved.
- The prototype does not run simulations and should not claim to produce universally executable engine files.

## Project contents

- `app.py` — Streamlit UI
- `simspeak/` — extraction, schema models, validation, structure sources, adapters, and reference workflows
- `schemas/` — universal JSON schema
- `tests/` — automated tests
- `config/argon_lj_example.json` — explicit argon reference configuration
- `DEVELOPMENT_HISTORY.md` — historical development notes (some early sections describe superseded limitations)
- `FINAL_PROJECT_SUMMARY.md` — presentation-ready overview and validation status

## Future work

Improve scientific-intent validation and portability across engines; expand coverage only where scientifically unambiguous. Executable engine inputs are deliberately outside this v0.3 proof-of-concept scope.
