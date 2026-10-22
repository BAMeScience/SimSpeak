"""Explicit reference workflows built on the four-field SimulationSpec.

No numerical reference configuration is silently inferred from natural language.
"""
from __future__ import annotations
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import json
import zipfile

from simspeak.argon_reference import ArgonLJConfig, generate_argon_lj_bundle
from simspeak.models import SimulationSpec
from simspeak.qe_generator import generate_qe, GenerationBlocked


def argon_reference_from_spec(spec: SimulationSpec, approved: ArgonLJConfig) -> bytes:
    if spec.method != 'classical_md' or spec.task.type != 'md' or spec.calculator.name not in (None, 'lammps'):
        raise ValueError('Select classical_md / md / LAMMPS for the argon reference')
    if spec.calculator.parameters.get('potential') != 'lj':
        raise ValueError('The argon reference requires an explicit LJ potential')
    tp = spec.task.parameters
    if tp.get('ensemble') != 'npt':
        raise ValueError('The argon reference requires an explicit NPT ensemble')
    for key in ('temperature_K', 'pressure_bar', 'timestep_fs', 'steps'):
        if key not in tp:
            raise ValueError(f'Missing requested parameter: {key}')
    for key in ('thermostat', 'barostat'):
        if tp.get(key) not in (None, 'nose_hoover'):
            raise ValueError(f'The reference uses Nose-Hoover; incompatible {key}')
    cp = spec.calculator.parameters
    if cp.get('potential_file'):
        raise ValueError('The LJ reference does not use an external potential file')
    cfg = replace(approved, temperature_k=tp['temperature_K'], pressure_bar=tp['pressure_bar'],
                  timestep_fs=tp['timestep_fs'], steps=tp['steps'])
    generated = generate_argon_lj_bundle(cfg)
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(generated)) as source, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr('spec.json', json.dumps(spec.model_dump(mode='json'), indent=2))
        target.writestr('APPROVAL.txt', 'Explicit argon reference configuration approved by the user. See reference_config.json.\n')
    return out.getvalue()


def silicon_qe_reference_from_spec(spec: SimulationSpec, structure: bytes, filename: str,
                                   pseudo_filename: str, pseudo_bytes: bytes) -> bytes:
    if spec.method != 'dft' or spec.task.type != 'single_point':
        raise GenerationBlocked('Silicon QE reference requires DFT single_point')
    if spec.calculator.name not in (None, 'espresso'):
        raise GenerationBlocked('Silicon QE reference requires Quantum ESPRESSO')
    if spec.calculator.parameters.get('xc') != 'PBE':
        raise GenerationBlocked('Silicon QE reference requires PBE')
    if not pseudo_bytes or not pseudo_filename.endswith('.UPF') or Path(pseudo_filename).name != pseudo_filename:
        raise GenerationBlocked('Upload an explicit silicon .UPF pseudopotential')
    if spec.calculator.parameters.get('pseudopotentials') != {'Si': pseudo_filename}:
        raise GenerationBlocked('The specification must map Si to the uploaded UPF filename')
    # Pseudopotential bytes are supplied by the user, never downloaded or invented.
    package = generate_qe(spec, structure, filename=filename)
    out = BytesIO()
    with zipfile.ZipFile(BytesIO(package.content)) as source, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            data = source.read(name)
            if name == 'pw.in':
                data = data.replace(b"pseudo_dir       = '.'", b"pseudo_dir       = './'")
            target.writestr(name, data)
        target.writestr(pseudo_filename, pseudo_bytes)
    return out.getvalue()
