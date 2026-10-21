"""Deterministic draft validation. No ASE, no implicit parameter defaults.

Evidence verification is intentionally conservative: without verified source evidence,
LLM-generated fields cannot be marked VALID. Manual form inputs are trusted only
as user-authorized edits, not as scientifically correct settings.
"""
from dataclasses import dataclass, asdict
from typing import Literal
import re
from simspeak.models import SimulationSpec

Status = Literal['VALID', 'INCOMPLETE', 'INVALID']

@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    message: str
    severity: str = 'blocking'

@dataclass(frozen=True)
class Report:
    status: Status
    diagnostics: list[Diagnostic]

    def as_dict(self):
        return asdict(self)

# This registry is intentionally small. Unknown parameters are rejected.
TASK_PARAMS = {
    'single_point': set(),
    'optimize': {'fmax_ev_ang'},
    'md': {'ensemble', 'temperature_K', 'timestep_fs', 'steps', 'duration_ps',
           'thermostat', 'pressure_bar', 'barostat', 'initial_state'},
}
CALCULATOR_PARAMS = {
    'dft': {'xc', 'cutoff_ev', 'kpoints', 'pseudopotentials', 'basis'},
    'classical_md': {'potential', 'potential_file'},
}


def validate(spec: SimulationSpec, *, source_text: str | None = None,
             evidence: dict[str, str] | None = None,
             user_edited: bool = False) -> Report:
    issues: list[Diagnostic] = []
    def add(code, path, message):
        issues.append(Diagnostic(code, path, message))
    def required(value, path):
        if value is None or value == '':
            add('MISSING', path, 'Required value is unspecified')
    required(spec.structure.source, 'structure.source')
    required(spec.method, 'method')
    required(spec.calculator.name, 'calculator.name')
    required(spec.task.type, 'task.type')
    if spec.method and spec.task.type:
        if (spec.method == 'classical_md' and spec.task.type != 'md') or (spec.method == 'dft' and spec.task.type == 'md'):
            add('INCOMPATIBLE_TASK', 'task.type', 'Task is incompatible with method')
    if spec.method:
        allowed = CALCULATOR_PARAMS[spec.method]
        for name in spec.calculator.parameters:
            if name not in allowed:
                add('UNKNOWN_PARAMETER', f'calculator.parameters.{name}', 'Parameter is not in the minimal registry')
    if spec.task.type:
        for name in spec.task.parameters:
            if name not in TASK_PARAMS[spec.task.type]:
                add('UNKNOWN_PARAMETER', f'task.parameters.{name}', 'Parameter is not supported for this task')
    p = spec.task.parameters
    c = spec.calculator.parameters
    if spec.method == 'classical_md' and spec.task.type == 'md':
        for key in ('ensemble', 'timestep_fs', 'initial_state'):
            required(p.get(key), f'task.parameters.{key}')
        if p.get('steps') is None and p.get('duration_ps') is None:
            add('MISSING', 'task.parameters.steps', 'Provide steps or duration_ps')
        if c.get('potential') is None and c.get('potential_file') is None:
            add('MISSING', 'calculator.parameters.potential', 'Specify an interatomic potential')
        ensemble = p.get('ensemble')
        if ensemble is not None and ensemble not in ('nve', 'nvt', 'npt'):
            add('INVALID_ENSEMBLE', 'task.parameters.ensemble', 'Use nve, nvt, or npt')
        if ensemble in ('nvt', 'npt'):
            for key in ('temperature_K', 'thermostat'):
                required(p.get(key), f'task.parameters.{key}')
        if ensemble == 'npt':
            for key in ('pressure_bar', 'barostat'):
                required(p.get(key), f'task.parameters.{key}')
    if spec.method == 'dft' and spec.task.type in ('single_point', 'optimize'):
        for key in ('xc', 'basis'):
            required(c.get(key), f'calculator.parameters.{key}')
        if spec.task.type == 'optimize':
            required(p.get('fmax_ev_ang'), 'task.parameters.fmax_ev_ang')
    for key in ('timestep_fs', 'duration_ps', 'temperature_K', 'pressure_bar'):
        val = p.get(key)
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0 or (key in ('timestep_fs', 'duration_ps') and val == 0)):
            add('INVALID_VALUE', f'task.parameters.{key}', 'Invalid numerical value')
    for key in ('steps',):
        val = p.get(key)
        if val is not None and (isinstance(val, bool) or not isinstance(val, int) or val <= 0):
            add('INVALID_VALUE', f'task.parameters.{key}', 'Must be a positive integer')
    if p.get('steps') is not None and p.get('duration_ps') is not None and isinstance(p.get('timestep_fs'), (int,float)) and p['timestep_fs'] > 0:
        if abs(p['steps'] * p['timestep_fs'] / 1000 - p['duration_ps']) > 1e-8:
            add('CONFLICT', 'task.parameters', 'steps, timestep_fs and duration_ps disagree')
    # LLM mode requires evidence for every nonempty leaf; evidence is a mapping
    # from dotted JSON path to verbatim quote in the original request.
    if not user_edited:
        def walk(value, prefix):
            if isinstance(value, dict):
                for k, v in value.items():
                    walk(v, f'{prefix}.{k}' if prefix else k)
            elif value is not None and value != '':
                yield_path.append(prefix)
        yield_path = []
        walk(spec.model_dump(mode='json'), '')
        for path in yield_path:
            quote = (evidence or {}).get(path)
            if not source_text or not quote or quote not in source_text:
                add('UNVERIFIED_EVIDENCE', path, 'No verified verbatim source quote')
            else:
                # Prevent a generic word such as "simulation" from certifying an
                # arbitrary value. The quote must contain the leaf value, except
                # for known lexical aliases (e.g. classical_md / classical MD).
                obj = spec.model_dump(mode='json')
                for part in path.split('.'):
                    obj = obj[part]
                literal = str(obj).lower()
                aliases = {'classical_md': ['classical md', 'molecular dynamics'], 'dft': ['dft', 'density functional theory'], 'md': ['md', 'molecular dynamics'], 'single_point': ['single point', 'single-point'], 'optimize': ['optimize', 'optimization', 'relaxation']}
                accepted = [literal] + aliases.get(literal, [])
                if not any(token in quote.lower() for token in accepted):
                    add('UNVERIFIED_VALUE', path, 'Source quote does not support the declared value')
    invalid = any(i.code not in ('MISSING',) for i in issues)
    return Report('INVALID' if invalid else 'INCOMPLETE' if issues else 'VALID', issues)
