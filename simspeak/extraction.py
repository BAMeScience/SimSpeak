"""Conservative natural-language extraction with optional Ollama proposals.

Only independently recognized facts may enter the draft. An LLM cannot
introduce values, paths, or defaults that the deterministic extractor missed.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from simspeak.models import SimulationSpec


@dataclass
class ExtractionResult:
    patch: dict[str, Any]
    evidence: dict[str, str]
    notes: list[str] = field(default_factory=list)
    llm_used: bool = False


def _match(text: str, pattern: str, flags: int = re.I) -> re.Match | None:
    return re.search(pattern, text, flags)


def extract_verified(text: str) -> ExtractionResult:
    """Extract only a small allowlist of literal, unambiguous facts.

    No structure filenames, potential files, or pseudopotentials are inferred.
    No unit conversion is performed. Ambiguous requests remain incomplete.
    """
    if not text.strip():
        raise ValueError('Request must not be empty')
    patch: dict[str, Any] = {}
    evidence: dict[str, str] = {}
    notes: list[str] = []

    def put(path: str, value: Any, quote: str):
        cursor = patch
        parts = path.split('.')
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
        evidence[path] = quote

    md = _match(text, r'\b(?:classical\s+md|molecular\s+dynamics|MD(?:\s+simulation)?|NVE|NVT|NPT)\b')
    dft = _match(text, r'\b(?:DFT|density\s+functional\s+theory)\b')
    if md and not dft:
        put('method', 'classical_md', md.group())
        put('task.type', 'md', md.group())
    elif dft and not md:
        put('method', 'dft', dft.group())
    elif md and dft:
        notes.append('Both MD and DFT mentioned: method left unspecified.')

    # Task declarations are valid even when the method is not stated.
    task_matches = list(re.finditer(r'\b(?:single[-_ ]point|geometry\s+optimization|geometry\s+relaxation|relaxation|optimize)\b', text, re.I))
    task_values = {'single_point' if 'single' in m.group().lower() else 'optimize' for m in task_matches}
    if len(task_values) == 1 and task_matches and not md:
        put('task.type', next(iter(task_values)), task_matches[0].group())
    elif len(task_values) > 1:
        notes.append('Conflicting task types mentioned: task left unspecified.')

    # Explicit engine names, not assumed from method.
    engine_aliases = {'lammps': 'lammps', 'openmm': 'openmm', 'quantum espresso': 'espresso', 'espresso': 'espresso', 'vasp': 'vasp', 'gpaw': 'gpaw'}
    hits = [(name, match) for alias, name in engine_aliases.items() if (match := _match(text, r'\b' + re.escape(alias) + r'\b'))]
    names = {name for name, _ in hits}
    if len(names) == 1:
        name, match = hits[0]
        put('calculator.name', name, match.group())
    elif len(names) > 1:
        notes.append('Multiple calculators mentioned: calculator left unspecified.')

    # File reference requires an explicit filename token; no filesystem access.
    files = list(re.finditer(r'(?<![\w./-])([\w./-]+\.(?:cif|xyz|vasp|POSCAR))(?![\w./-])', text, re.I))
    if len(files) == 1:
        put('structure.source', files[0].group(1), files[0].group(1))
    elif len(files) > 1:
        notes.append('Multiple structure files mentioned: structure left unspecified.')

    # Individual chat turns can supply MD settings without repeating 'MD'.
    # These values are proposals only; method/task are never inferred from them.
    timestep_mentions = list(re.finditer(
        r'\b(?:time\s*step|timestep)\s*(?:is|of|=|:)?\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)\b', text, re.I
    ))
    if timestep_mentions:
        valid = [m for m in timestep_mentions if m.group(2).lower() in ('fs', 'femtosecond', 'femtoseconds')]
        if len(timestep_mentions) == 1 and len(valid) == 1:
            put('task.parameters.timestep_fs', float(valid[0].group(1)), valid[0].group())
        else:
            notes.append('Timestep not extracted: ambiguous, unsupported, or conflicting unit/value; specify e.g. 2 fs.')

    state_hits = []
    for name, pattern in (
        ('generate', r'\b(?:generate|initialize|initialise|create)\s+(?:the\s+|an?\s+)?initial\s+state\b|\bgenerate\s+(?:initial\s+)?velocities\b'),
        ('provided', r'\b(?:use\s+)?(?:provided|existing)\s+(?:initial\s+)?(?:state|velocities)\b'),
    ):
        state_hits.extend((name, m) for m in re.finditer(pattern, text, re.I))
    if len({name for name, _ in state_hits}) == 1 and state_hits:
        name, m = state_hits[0]
        put('task.parameters.initial_state', name, m.group())
    elif state_hits:
        notes.append('Conflicting initial-state instructions: left unspecified.')

    # Standalone MD follow-ups must not require repeating the method name.
    # Accept only explicit step counts, not bare numbers or inferred durations.
    step_patterns = (
        r'\b(?:run|perform|simulate|for|use|set|steps?\s*(?:is|are|to|=|:))\s*(?:for\s*)?(\d+)\s*(?:MD\s+)?(?:time\s*)?steps?\b',
        r'\b(?:number\s+of\s+steps|nsteps|steps)\s*(?:is|are|to|=|:|of)\s*(\d+)\b',
        r'\b(\d+)\s*(?:MD\s+)?(?:time\s*)?steps?\b',
    )
    step_hits = [m for pattern in step_patterns for m in re.finditer(pattern, text, re.I)]
    step_values = {int(m.group(1)) for m in step_hits}
    if len(step_values) == 1 and step_hits:
        value = next(iter(step_values))
        if value > 0:
            put('task.parameters.steps', value, step_hits[0].group())
        else:
            notes.append('Steps must be a positive integer.')
    elif len(step_values) > 1:
        notes.append('Conflicting step counts: steps left unspecified.')

    # Pressure is a standalone MD parameter. Convert explicit absolute-pressure
    # units to bar; do not infer a barostat or an NPT ensemble.
    pressure_pattern = (
        r'\b(?:target\s+|external\s+)?pressure\s*(?:is|of|to|at|=|:)?\s*'
        r'([0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*'
        r'(bar|bars|atm|atmospheres?|kPa|MPa|Pa)\b'
        r'|\b([0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?)\s*'
        r'(bar|bars|atm|atmospheres?|kPa|MPa|Pa)\s+(?:target\s+)?pressure\b'
    )
    pressure_hits = list(re.finditer(pressure_pattern, text, re.I))
    factors = {'bar': 1, 'bars': 1, 'atm': 1.01325,
               'atmosphere': 1.01325, 'atmospheres': 1.01325,
               'kpa': 0.01, 'mpa': 10, 'pa': 1e-5}
    pressure_values = []
    for m in pressure_hits:
        amount = m.group(1) or m.group(3)
        unit = (m.group(2) or m.group(4)).lower()
        pressure_values.append((float(amount) * factors[unit], m))
    if pressure_values and len({round(v, 10) for v, _ in pressure_values}) == 1:
        value, match = pressure_values[0]
        put('task.parameters.pressure_bar', value, match.group())
    elif len({round(v, 10) for v, _ in pressure_values}) > 1:
        notes.append('Conflicting pressure values: target pressure left unspecified.')
    elif re.search(r'\bpressure\b', text, re.I):
        notes.append('Target pressure requires an explicit value and supported unit (bar, atm, Pa, kPa, MPa).')

    # Barostat names require explicit barostat context. Never infer an ensemble,
    # target pressure, or thermostat from the selected pressure-control family.
    barostat_aliases = {
        'nose_hoover': r'\bNos[eé][\s_-]*Hoover\b',
        'berendsen': r'\bBerendsen\b',
        'parrinello_rahman': r'\bParrinello[\s_-]*Rahman\b',
        'monte_carlo': r'\b(?:Monte[\s_-]*Carlo|MC)\b',
    }
    barostat_hits = []
    if re.search(r'\bbarostat\b', text, re.I):
        for name, pattern in barostat_aliases.items():
            for m in re.finditer(pattern, text, re.I):
                # Match either "use Berendsen barostat" or "barostat: Berendsen".
                before, after = text[:m.start()], text[m.end():]
                if (re.search(r'\bbarostat\b(?:\s+(?:is|to|as|set\s+to)|\s*[:=])?\s*$', before, re.I)
                        or re.match(r'\s+barostat\b', after, re.I)):
                    barostat_hits.append((name, m))
    barostat_names = {name for name, _ in barostat_hits}
    if len(barostat_names) == 1 and barostat_hits:
        name, match = barostat_hits[0]
        put('task.parameters.barostat', name, match.group())
    elif len(barostat_names) > 1:
        notes.append('Conflicting barostat selections: barostat left unspecified.')
    elif re.search(r'\bbarostat\b', text, re.I):
        notes.append('Barostat mentioned without a supported explicit type.')

    thermostat_aliases = {
        'nose_hoover': r'\bNos[eé][\s_-]*Hoover\b',
        'langevin': r'\bLangevin\b',
        'berendsen': r'\bBerendsen\b',
    }
    thermostat_hits = [(name, m) for name, pattern in thermostat_aliases.items()
                       for m in re.finditer(pattern, text, re.I)
                       if (not any(m.start() == b.start() and m.end() == b.end() for _, b in barostat_hits)
                           and (name == 'langevin' or re.search(r'\bthermostat\b[^.!?;]*$', text[:m.start()], re.I)
                                or re.match(r'\s+thermostat\b', text[m.end():], re.I)))]
    thermostat_names = {name for name, _ in thermostat_hits}
    if len(thermostat_names) == 1 and thermostat_hits:
        name, match = thermostat_hits[0]
        put('task.parameters.thermostat', name, match.group())
    elif len(thermostat_names) > 1:
        notes.append('Conflicting thermostats: thermostat left unspecified.')
    elif re.search(r'\bthermostat\b', text, re.I):
        notes.append('Thermostat mentioned without a supported explicit type.')

    # Duration and force-field selection are valid standalone follow-up turns.
    # Only explicitly written units are accepted; never infer a time unit.
    duration_hits = list(re.finditer(
        r'(?<![\w.])(\d+(?:\.\d+)?)\s*(ps|picoseconds?|ns|nanoseconds?|fs|femtoseconds?)\b',
        text, re.I,
    ))
    duration_hits = [m for m in duration_hits if not re.search(
        r'(?:time\s*step|timestep)\s*(?:is|of|=|:)?\s*$', text[max(0, m.start()-24):m.start()], re.I
    )]
    duration_values = []
    for match in duration_hits:
        unit = match.group(2).lower()
        factor = 1000 if unit in ('ns', 'nanosecond', 'nanoseconds') else (0.001 if unit in ('fs', 'femtosecond', 'femtoseconds') else 1)
        duration_values.append((float(match.group(1)) * factor, match))
    # Require an explicit duration context for femtoseconds to avoid timestep confusion.
    duration_values = [(v, m) for v, m in duration_values if
                       not m.group(2).lower().startswith(('fs', 'femto')) or
                       re.search(r'\b(?:duration|run\s+(?:for|time)|simulate\s+for)\b', text, re.I)]
    if len({v for v, _ in duration_values}) == 1 and duration_values:
        value, match = duration_values[0]
        if value > 0:
            put('task.parameters.duration_ps', value, match.group())
        else:
            notes.append('Duration must be positive.')
    elif len({v for v, _ in duration_values}) > 1:
        notes.append('Conflicting durations: duration left unspecified.')
    elif re.search(r'\bduration\b', text, re.I):
        notes.append('Duration requires an explicit supported time unit (fs, ps, ns).')

    potential_aliases = {
        'tersoff': r'\btersoff\b',
        'eam': r'\bEAM\b',
        'lj': r'\b(?:Lennard[- ]Jones|LJ)\b',
        'opls_aa': r'\bOPLS[\s/-]*AA\b',
        'cgenff_2_0': r'\b(?:C?GenFF)[\s-]*2\.0\b',
        'amber_ff19sb': r'\b(?:AMBER[\s_-]*)?ff19SB\b|\bAMBER[\s_-]*19SB\b',
    }
    potential_hits = [(name, m) for name, pattern in potential_aliases.items()
                      for m in re.finditer(pattern, text, re.I)]
    potential_names = {name for name, _ in potential_hits}
    if len(potential_names) == 1 and potential_hits:
        name, match = potential_hits[0]
        put('calculator.parameters.potential', name, match.group())
    elif len(potential_names) > 1:
        notes.append('Conflicting force fields: potential left unspecified.')
    elif re.search(r'\b(?:potential|force\s*field|forcefield)\b', text, re.I):
        notes.append('No supported explicit force field identified; no potential selected.')

    if patch.get('method') == 'classical_md':
        ensembles = list(re.finditer(r'\b(?:NVE|NVT|NPT)\b', text, re.I))
        if len({m.group().lower() for m in ensembles}) == 1 and ensembles:
            put('task.parameters.ensemble', ensembles[0].group().lower(), ensembles[0].group())
    # Temperature is an independent MD setting. Standalone follow-ups must not
    # require the user to repeat MD/NVT/NPT. Avoid interpreting an unrelated
    # Kelvin value as a target unless the temperature context is explicit.
    temp_hits = list(re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(?:K|kelvin)\b', text, re.I))
    temperature_context = bool(re.search(r'\b(?:temperature|temp|target\s+temp|at\s+\d+(?:\.\d+)?\s*(?:K|kelvin)\b)\b', text, re.I))
    if len(temp_hits) == 1 and (temperature_context or patch.get('method') == 'classical_md'):
        put('task.parameters.temperature_K', float(temp_hits[0].group(1)), temp_hits[0].group())
    elif len(temp_hits) > 1:
        notes.append('Multiple temperatures: left unspecified.')
    # XC is an explicit calculator setting even if 'DFT' was not said.
    if patch.get('method') != 'classical_md':
        xc_hits = [(name, m) for name in ('PBEsol', 'PBE', 'LDA') if (m := _match(text, r'\b' + name + r'\b'))]
        if len(xc_hits) == 1:
            put('calculator.parameters.xc', xc_hits[0][0], xc_hits[0][1].group())
        elif len(xc_hits) > 1:
            notes.append('Conflicting XC functionals: XC left unspecified.')
    # DFT parameters are independent updates: users need not repeat "DFT".
    if patch.get('method') != 'classical_md':
        cutoff_patterns = [
            r'\b(?:plane[- ]wave\s+|energy\s+|kinetic[- ]energy\s+)?cutoff\s*(?:energy\s*)?(?:is|of|to|=|:)?\s*(\d+(?:\.\d+)?)\s*(eV|Ry|Rydberg(?:s)?)\b',
            r'\b(\d+(?:\.\d+)?)\s*(eV|Ry|Rydberg(?:s)?)\s+(?:plane[- ]wave\s+|energy\s+)?cutoff\b',
        ]
        cutoff_hits = [m for pattern in cutoff_patterns for m in re.finditer(pattern, text, re.I)]
        cutoff_values = [(float(m.group(1)) * (13.605693122994 if m.group(2).lower().startswith('ry') else 1), m) for m in cutoff_hits]
        if len({round(v, 8) for v, _ in cutoff_values}) == 1 and cutoff_values:
            value, m = cutoff_values[0]
            put('calculator.parameters.cutoff_ev', value, m.group())
        elif len(cutoff_values) > 1:
            notes.append('Conflicting cutoffs: cutoff left unspecified.')
        elif re.search(r'\bcutoff\b', text, re.I):
            notes.append('Cutoff requires an explicit supported unit (eV or Ry).')

        mesh = r'(\d+)\s*(?:[x×,]|\s+)\s*(\d+)\s*(?:[x×,]|\s+)\s*(\d+)'
        k_patterns = [
            r'\b(?:k[- ]?points?|k[- ]?point\s+(?:mesh|grid|sampling)|k[- ]?mesh|monkhorst[- ]pack)\s*(?:mesh|grid|sampling|of|is|to|=|:)?\s*' + mesh + r'\b',
            r'\b' + mesh + r'\s*(?:k[- ]?points?|k[- ]?point\s+(?:mesh|grid)|k[- ]?mesh)\b',
        ]
        k_hits = [m for pattern in k_patterns for m in re.finditer(pattern, text, re.I)]
        k_values = [(tuple(int(m.group(i)) for i in (1, 2, 3)), m) for m in k_hits]
        if len({v for v, _ in k_values}) == 1 and k_values:
            value, m = k_values[0]
            if all(n > 0 for n in value):
                put('calculator.parameters.kpoints', list(value), m.group())
            else:
                notes.append('k-point mesh dimensions must be positive.')
        elif len(k_values) > 1:
            notes.append('Conflicting k-point meshes: mesh left unspecified.')

        # Accept common local-basis phrasings as well as plane-wave basis.
        basis_patterns = {
            'plane_wave': r'\bplane[\s_-]*waves?\b',
            'localized': r'\b(?:local(?:ized|ised)?|atomic)[\s_-]+(?:orbital(?:s)?|basis(?:[\s_-]+set)?)\b|\b(?:localized|localised)\b',
        }
        basis_hits = [(name, m) for name, pattern in basis_patterns.items()
                      for m in re.finditer(pattern, text, re.I)]
        if len({name for name, _ in basis_hits}) == 1 and basis_hits:
            name, match = basis_hits[0]
            put('calculator.parameters.basis', name, match.group())
        elif len({name for name, _ in basis_hits}) > 1:
            notes.append('Conflicting basis representations: basis left unspecified.')

        # Do not require a word boundary after Å: it is a Unicode word character.
        # The unit may be written eV/Å, eV/A, eV/Angstrom or eV/Angstroms.
        number = r'(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)'
        unit = r'eV\s*/\s*(?:Å|A|angstroms?)(?![\w])'
        label = r'(?:fmax|force[\s_-]*(?:tolerance|convergence|threshold|criterion)|force\s+convergence\s+criterion)'
        force_patterns = [
            rf'\b{label}\s*(?:is|of|to|at|=|:)?\s*{number}\s*{unit}',
            rf'\b{number}\s*{unit}\s+(?:{label})\b',
        ]
        force_hits = [m for pattern in force_patterns for m in re.finditer(pattern, text, re.I)]
        force_values = [(float(m.group(1)), m) for m in force_hits]
        if len({v for v, _ in force_values}) == 1 and force_values:
            value, match = force_values[0]
            if value > 0:
                put('task.parameters.fmax_ev_ang', value, match.group())
            else:
                notes.append('Force tolerance must be positive.')
        elif len({v for v, _ in force_values}) > 1:
            notes.append('Conflicting force tolerances: tolerance left unspecified.')
        elif re.search(label, text, re.I):
            notes.append('Force tolerance requires an explicit positive value in eV/Å.')

    # A Pydantic roundtrip also rejects unexpected schema shape.
    SimulationSpec.model_validate(patch)
    return ExtractionResult(patch, evidence, notes)


def _leaves(value: Any, prefix: str = ''):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaves(v, f'{prefix}.{k}' if prefix else k)
    elif value is not None:
        yield prefix, value


def extract(text: str, *, use_ollama: bool = False, model: str | None = None) -> ExtractionResult:
    """Optionally request an LLM proposal, then keep ONLY deterministic matches.

    LLM omission is permitted; LLM additions or alterations are rejected.
    When Ollama is unavailable, the verified rule-based extractor still works.
    """
    verified = extract_verified(text)
    if not use_ollama:
        return verified
    try:
        import ollama
        schema = SimulationSpec.model_json_schema()
        response = ollama.chat(
            model=model or os.getenv('SIMSPEAK_OLLAMA_MODEL', 'qwen3:4b'),
            messages=[{'role': 'system', 'content': 'Extract only explicitly stated simulation details. Never infer missing parameters. Return JSON matching the schema.'}, {'role': 'user', 'content': text}],
            format=schema,
            options={'temperature': 0},
        )
        content = response['message']['content']
        candidate = SimulationSpec.model_validate(json.loads(content)).model_dump(exclude_none=True)
        approved = dict(_leaves(verified.patch))
        proposal = dict(_leaves(candidate))
        # Deterministically verified facts survive even when the LLM omits them.
        # LLM-only values are never promoted without independent verification.
        accepted = dict(approved)
        result_patch: dict[str, Any] = {}
        for path, value in accepted.items():
            cursor = result_patch
            parts = path.split('.')
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = value
        notes = list(verified.notes)
        rejected = {k for k, v in proposal.items() if k not in approved or approved[k] != v}
        if rejected:
            notes.append('LLM claims rejected (not independently verified): ' + ', '.join(sorted(rejected)))
        return ExtractionResult(result_patch, {k: verified.evidence[k] for k in accepted}, notes, llm_used=True)
    except Exception as exc:
        verified.notes.append(f'Ollama unavailable or returned invalid output ({type(exc).__name__}); verified extraction used.')
        return verified


def merge_spec(current: SimulationSpec, patch: dict[str, Any]) -> SimulationSpec:
    """Merge verified facts without deleting existing values or replacing conflicts."""
    data = current.model_dump(mode='json')
    for path, value in _leaves(patch):
        parts = path.split('.')
        cursor = data
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        old = cursor.get(parts[-1])
        if old is None or old == '':
            cursor[parts[-1]] = value
        elif old != value:
            raise ValueError(f'Conflict at {path}: existing {old!r}, extracted {value!r}. Resolve manually.')
    return SimulationSpec.model_validate(data)
