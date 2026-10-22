# SimSpeak v0.3 — Milestone 2 (partial): explicit argon LJ reference

This checkpoint adds a separate opt-in, reproducible FCC argon Lennard-Jones NPT LAMMPS bundle generator. The general-purpose LAMMPS adapter remains conservative and unchanged. All scientific values are provided through `config/argon_lj_example.json`, which is an **illustrative configuration requiring scientific review**, not a universal default or a validated argon force field.

Generate the reference candidate with:

```sh
python generate_argon_reference.py config/argon_lj_example.json argon_reference.zip
```

Output includes `in.lammps`, `argon.data`, `reference_config.json`, and `generation_report.json`. The input uses `units real`, atomic LJ pair style, explicit epsilon/sigma/cutoff, FCC atom coordinates, and `fix npt` with explicit damping values. The generator does not need ASE and does not alter the four-field universal schema.

## Verification and limitations

- Python automated non-UI tests: see included `MILESTONE_2_TEST_RESULTS.txt`.
- No LAMMPS binary available in this environment: **not engine-executed, not yet confirmed runnable**.
- Streamlit unavailable: UI integration is not implemented or verified.
- This separate reference generator is not yet wired into the chat → JSON → LAMMPS adapter pipeline. That remains a Milestone 2 requirement.
- No claim of physical accuracy or stable NPT dynamics is made.

Next: integrate explicit reference configuration selection into the application without injecting scientific defaults, then execute the generated package using an installed LAMMPS binary and review output.
