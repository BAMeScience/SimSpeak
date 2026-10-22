"""Verified chat revisions; no implicit overwrites or scientific defaults."""
from __future__ import annotations
import re
from simspeak.models import SimulationSpec
from simspeak.extraction import extract, _leaves

CLEAR = re.compile(r'\b(?:clear|remove|unset|reset|unspecify|forget)\b', re.I)
REPLACE = re.compile(r'\b(?:actually|instead|change|replace|switch|update|correct|set|use|make|should be)\b', re.I)
ALIASES = {
    'calculator.parameters.xc': r'\b(?:xc|exchange.correlation|functional)\b',
    'calculator.parameters.basis': r'\b(?:basis|plane.wave|localized|local basis)\b',
    'calculator.parameters.cutoff_ev': r'\b(?:cutoff|ecutwfc)\b',
    'calculator.parameters.kpoints': r'\b(?:k.points?|kpoints?|k.mesh)\b',
    'calculator.parameters.pseudopotentials': r'\b(?:pseudopotentials?|pseudos?)\b',
    'calculator.parameters.potential': r'\b(?:potential|force.field)\b',
    'calculator.parameters.potential_file': r'\bpotential file\b',
    'calculator.name': r'\b(?:calculator|engine|code)\b',
    'task.type': r'\b(?:task|single.point|optimization|md)\b',
    'task.parameters.fmax_ev_ang': r'\b(?:fmax|force tolerance|force convergence)\b',
    'task.parameters.timestep_fs': r'\b(?:timestep|time step)\b',
    'task.parameters.steps': r'\b(?:steps|step count)\b',
    'task.parameters.duration_ps': r'\b(?:duration|run time)\b',
    'task.parameters.thermostat': r'\bthermostat\b',
    'task.parameters.ensemble': r'\bensemble\b',
    'task.parameters.temperature_K': r'\btemperature\b',
    'task.parameters.pressure_bar': r'\bpressure\b',
    'task.parameters.barostat': r'\bbarostat\b',
    'task.parameters.initial_state': r'\binitial state\b',
    'structure.source': r'\b(?:structure|source|structure file)\b',
    'method': r'\bmethod\b',
}

def _set(data, path, value):
    parts = path.split('.')
    cur = data
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    if value is None and parts[0] in ('calculator', 'task') and len(parts) == 3:
        cur.pop(parts[-1], None)
    else:
        cur[parts[-1]] = value

def _get(data, path):
    cur = data
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur

def apply_chat_revision(current: SimulationSpec, message: str, *, use_ollama=False):
    """Return (new spec, changes, notes). Changes are atomic and evidence-backed."""
    data = current.model_dump(mode='json')
    notes = []
    changes = []
    if CLEAR.search(message):
        paths = [p for p, pattern in ALIASES.items() if re.search(pattern, message, re.I)]
        # Avoid broad matching of 'potential' when 'potential file' is intended.
        if 'calculator.parameters.potential_file' in paths:
            paths = [p for p in paths if p != 'calculator.parameters.potential']
        if len(paths) != 1:
            return current, [], ['Clear request is ambiguous; name exactly one field.']
        path = paths[0]
        old = _get(data, path)
        _set(data, path, None)
        return SimulationSpec.model_validate(data), [(path, old, None)], []
    # In "change X to Y", X is context, not a second requested value.
    target = message
    if re.search(r"\b(?:change|replace|switch|update|correct)\b", message, re.I):
        m = re.search(r"\b(?:to|with)\s+(.+)$", message, re.I)
        if m:
            target = m.group(1)
            # Preserve the named field for standalone numeric revisions.
            if re.search(r'\bpressure\b', message, re.I) and not re.search(r'\bpressure\b', target, re.I):
                target = 'pressure is ' + target
            if re.search(r'\btemperature\b', message, re.I) and not re.search(r'\btemperature\b', target, re.I):
                target = 'temperature is ' + target
            if re.search(r'\bbarostat\b', message, re.I) and not re.search(r'\bbarostat\b', target, re.I):
                target = 'barostat: ' + target
    result = extract(target, use_ollama=use_ollama)
    notes.extend(result.notes)
    proposals = list(_leaves(result.patch))
    replacing = bool(REPLACE.search(message))
    conflicts = [(p, _get(data, p), v) for p, v in proposals if _get(data, p) not in (None, '') and _get(data, p) != v]
    if conflicts and not replacing:
        return current, [], notes + ['Existing values differ. Say "change ... to ..." to replace them: ' + ', '.join(p for p, _, _ in conflicts)]
    for path, value in proposals:
        old = _get(data, path)
        if old != value:
            _set(data, path, value)
            changes.append((path, old, value))
    return SimulationSpec.model_validate(data), changes, notes
