# SimSpeak v0.3 consolidated development release

## Scope
One installable application archive; no manual merging of previous ZIP files.

- Existing natural-language extraction, four-field universal JSON, form editing, revisions, validation and engine templates are retained.
- Argon LJ NPT reference is integrated with the current universal JSON specification and an explicitly approved reference configuration. Generated package includes `in.lammps`, `argon.data`, `spec.json`, `reference_config.json`, `generation_report.json`, `APPROVAL.txt`.
- Silicon PBE QE SCF reference is integrated with the current universal JSON specification, with explicit structure and UPF uploads. The QE adapter requires cutoff, k-points, pseudopotential mapping and plane-wave basis to be set by the user.
- Reference generators never execute simulations. The general-purpose adapters remain conservative and may produce non-runnable templates.

## Verification performed
- Python compilation: passed.
- Automated non-UI suite (excluding Streamlit-dependent `tests/test_app.py`): **133 passed**.
- Actual Streamlit browser interaction: **not verified**.
- ASE-based Quantum ESPRESSO file generation: **not verified in this environment** (ASE unavailable).
- LAMMPS `lmp` and QE `pw.x` smoke tests: **not run** (executables unavailable).
- The LJ argon model is illustrative, not a calibrated scientific model.

## Usage
1. Install project dependencies from `pyproject.toml` in a Python environment compatible with the project (requires Python >=3.14 as declared).
2. Run `streamlit run app.py`.
3. Use the chat and/or form to create the universal specification.
4. Scroll to **v0.3 reference workflows**. For argon, review and approve the visible reference configuration, then generate the bundle. For silicon, upload a matching periodic structure and compatible Si UPF and specify explicit PBE/plane-wave/cutoff/kpoints/pseudopotential mapping in the form.
5. Review the generated `generation_report.json` and engine inputs. Execution and scientific validation remain separate activities.

## Known limitations
- The QE pseudopotential file is packaged as supplied, not checked for XC compatibility or cutoffs.
- QE input may require additional engine-specific settings (e.g. pseudo_dir) and external validation.
- Chat is not guaranteed to extract all scientific settings; manual form completion remains possible.
- This is an integrated development release, **not** a demonstrated end-to-end runnable release.
