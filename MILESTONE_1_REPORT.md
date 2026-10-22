# SimSpeak v0.3 — Milestone 1: Shared Pipeline Baseline

Date: 2026-10-22. Baseline: SimSpeak-v0.2-consolidated-NPT-temperature.zip.

## Verified
- Four top-level JSON fields remain unchanged: `structure`, `method`, `calculator`, `task`.
- 123 non-UI tests pass (118 pre-existing plus five new v0.3 acceptance tests).
- New tests cover MD and DFT reference extraction, standalone temperature/pressure/thermostat/barostat updates, and validation of incomplete NPT specifications.
- Missing scientific values are not automatically supplied in the tested examples.

## Not yet verified / known gaps
- Streamlit UI test collection fails because Streamlit is unavailable in the current environment. UI tests were excluded from the passing run.
- No actual LAMMPS or Quantum ESPRESSO execution was performed.
- Neither reference workflow is yet a runnable simulation bundle. Explicit atomic structures, LJ parameters, thermostat/barostat damping, pseudopotentials, k-points and cutoff still require selection/validation.
- The parser does not reliably understand all free-form reference requests (for example, `argon` and `silicon crystal` do not automatically identify a structure file). This is intentional for now: do not invent a structure.
- The existing validator does not enforce every engine-specific runnable-input requirement; those belong in the next adapter milestones.

## Reproduce
From the extracted `SimSpeak-v0.2` directory:

```sh
python -m pytest -q --ignore=tests/test_app.py
```

Full suite requires Streamlit and any other project dependencies.

## Next milestones
2. LAMMPS argon LJ NPT: explicit reference configuration, generated data and script, real smoke test.
3. Quantum ESPRESSO silicon PBE SCF: explicit pseudopotential and numerical configuration, real smoke test.
4. UI and reproducible release package.

No scientific defaults or universal schema extensions were introduced in Milestone 1.
