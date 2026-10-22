"""SimSpeak: mock chat, editable universal specification, deterministic validation."""
import json
import streamlit as st
from pydantic import ValidationError
from simspeak.chat_backend import send_message
from simspeak.revisions import apply_chat_revision
from simspeak.models import SimulationSpec
from simspeak.validation import validate

st.set_page_config(page_title='SimSpeak', page_icon='⚛️', layout='wide')
st.title('SimSpeak')
if 'spec_undo' not in st.session_state:
    st.session_state.spec_undo = []
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'spec' not in st.session_state:
    st.session_state.spec = SimulationSpec().model_dump(mode='json')
if 'extraction_evidence' not in st.session_state:
    st.session_state.extraction_evidence = {}
if 'extraction_notes' not in st.session_state:
    st.session_state.extraction_notes = []
if 'spec_user_edited' not in st.session_state:
    st.session_state.spec_user_edited = False
with st.sidebar:
    st.subheader('Controls')
    if st.button('Clear chat', use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    if st.button('Undo last change', use_container_width=True, disabled=not st.session_state.spec_undo):
        st.session_state.spec = st.session_state.spec_undo.pop()
        st.session_state.spec_user_edited = True
        st.session_state.extraction_evidence = {}
        st.rerun()
    if st.button('Reset fields', use_container_width=True):
        st.session_state.spec_undo = []
        st.session_state.spec = SimulationSpec().model_dump(mode='json')
        st.session_state.spec_user_edited = False
        st.session_state.extraction_evidence = {}
        st.session_state.extraction_notes = []
        st.rerun()
spec = SimulationSpec.model_validate(st.session_state.spec)
chat_col, form_col = st.columns([1.15, 1], gap='large')
with form_col:
    st.subheader('Simulation fields')
    st.caption('No scientific defaults. Empty fields mean unspecified. JSON parameters must be objects.')
    st.caption('Dropdowns only offer supported choices. Blank means unspecified; no scientific defaults.')
    source = st.text_input('Structure file', value=spec.structure.source or '', placeholder='silicon.cif')
    methods = ['', 'classical_md', 'dft']
    method = st.selectbox('Method', methods, index=methods.index(spec.method or ''), format_func=lambda x: x or 'Not specified')
    calculator_options = {'classical_md': ['', 'lammps', 'openmm'], 'dft': ['', 'espresso', 'vasp', 'gpaw']}
    available_calculators = calculator_options.get(method, [''])
    if spec.calculator.name and spec.calculator.name not in available_calculators and spec.method == method:
        available_calculators.append(spec.calculator.name)
    calculator = st.selectbox('Calculator', available_calculators,
                              index=available_calculators.index(spec.calculator.name) if spec.calculator.name in available_calculators else 0,
                              format_func=lambda x: x or 'Not specified')
    task_options = {'classical_md': ['', 'md'], 'dft': ['', 'single_point', 'optimize']}
    available_tasks = task_options.get(method, [''])
    task = st.selectbox('Task', available_tasks,
                        index=available_tasks.index(spec.task.type) if spec.task.type in available_tasks else 0,
                        format_func=lambda x: x or 'Not specified')

    def choice(label, options, existing=None):
        options = ['', *options]
        if existing is not None and existing not in options:
            options.append(existing)
        return st.selectbox(label, options, index=options.index(existing) if existing in options else 0,
                            format_func=lambda x: x or 'Not specified') or None

    def number_text(label, existing=None):
        return st.text_input(label, value='' if existing is None else str(existing), placeholder='Not specified').strip()

    def numeric(value, label, integer=False):
        if not value:
            return None
        try:
            parsed = int(value) if integer else float(value)
        except ValueError as exc:
            raise ValueError(f'{label} must be a number') from exc
        if isinstance(parsed, float) and not __import__('math').isfinite(parsed):
            raise ValueError(f'{label} must be finite')
        return parsed

    cp = spec.calculator.parameters if spec.method == method else {}
    tp = spec.task.parameters if spec.method == method and spec.task.type == task else {}
    calc_parameters = {}
    task_parameters = {}
    st.markdown('**Calculator parameters**')
    if method == 'classical_md':
        potential = choice('Potential', ['tersoff', 'eam', 'lj', 'opls_aa', 'cgenff_2_0', 'amber_ff19sb'], cp.get('potential'))
        potential_file = st.text_input('Potential file', value=cp.get('potential_file') or '', placeholder='Not specified')
        if potential: calc_parameters['potential'] = potential
        if potential_file.strip(): calc_parameters['potential_file'] = potential_file.strip()
    elif method == 'dft':
        xc = choice('XC functional', ['PBE', 'PBEsol', 'LDA'], cp.get('xc'))
        basis = choice('Basis', ['plane_wave', 'localized'], cp.get('basis'))
        cutoff = number_text('Cutoff (eV)', cp.get('cutoff_ev'))
        kpoints = st.text_input('k-points (e.g. 4,4,4)', value=','.join(map(str, cp.get('kpoints', []))) if isinstance(cp.get('kpoints'), list) else '', placeholder='Not specified')
        pseudo = st.text_input('Pseudopotentials (JSON mapping)', value=json.dumps(cp['pseudopotentials']) if 'pseudopotentials' in cp else '', placeholder='Not specified')
        if xc: calc_parameters['xc'] = xc
        if basis: calc_parameters['basis'] = basis

    st.markdown('**Task parameters**')
    if method == 'classical_md' and task == 'md':
        ensemble = choice('Ensemble', ['nve', 'nvt', 'npt'], tp.get('ensemble'))
        timestep = number_text('Timestep (fs)', tp.get('timestep_fs'))
        steps = number_text('Steps', tp.get('steps'))
        duration = number_text('Duration (ps)', tp.get('duration_ps'))
        initial_state = choice('Initial state', ['provided', 'generate'], tp.get('initial_state'))
        if ensemble: task_parameters['ensemble'] = ensemble
        if initial_state: task_parameters['initial_state'] = initial_state
        if ensemble in ('nvt', 'npt'):
            temperature = number_text('Temperature (K)', tp.get('temperature_K'))
            thermostat = choice('Thermostat', ['nose_hoover', 'langevin', 'berendsen'], tp.get('thermostat'))
            if thermostat: task_parameters['thermostat'] = thermostat
        if ensemble == 'npt':
            pressure = number_text('Pressure (bar)', tp.get('pressure_bar'))
            barostat = choice('Barostat', ['nose_hoover', 'berendsen', 'parrinello_rahman', 'monte_carlo'], tp.get('barostat'))
            if barostat: task_parameters['barostat'] = barostat
    elif method == 'dft' and task == 'optimize':
        fmax = number_text('Force tolerance (eV/Å)', tp.get('fmax_ev_ang'))

    if st.button('Apply changes', type='primary'):
        try:
            if method == 'dft':
                if cutoff: calc_parameters['cutoff_ev'] = numeric(cutoff, 'Cutoff')
                if kpoints.strip():
                    parts = [x.strip() for x in kpoints.split(',')]
                    if len(parts) != 3: raise ValueError('k-points must contain three integers')
                    calc_parameters['kpoints'] = [numeric(x, 'k-points', integer=True) for x in parts]
                if pseudo.strip():
                    parsed = json.loads(pseudo)
                    if not isinstance(parsed, dict): raise ValueError('Pseudopotentials must be a JSON object')
                    calc_parameters['pseudopotentials'] = parsed
            if method == 'classical_md' and task == 'md':
                for name, value, integer in [('timestep_fs', timestep, False), ('steps', steps, True), ('duration_ps', duration, False)]:
                    if value: task_parameters[name] = numeric(value, name, integer)
                if ensemble in ('nvt', 'npt') and temperature: task_parameters['temperature_K'] = numeric(temperature, 'Temperature')
                if ensemble == 'npt' and pressure: task_parameters['pressure_bar'] = numeric(pressure, 'Pressure')
            if method == 'dft' and task == 'optimize' and fmax:
                task_parameters['fmax_ev_ang'] = numeric(fmax, 'Force tolerance')
            candidate = SimulationSpec.model_validate({
                'structure': {'source': source.strip() or None},
                'method': method or None,
                'calculator': {'name': calculator or None, 'parameters': calc_parameters},
                'task': {'type': task or None, 'parameters': task_parameters},
            })
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            st.error(f'Changes not saved: {exc}')
        else:
            st.session_state.spec_undo.append(st.session_state.spec.copy())
            st.session_state.spec = candidate.model_dump(mode='json')
            st.session_state.spec_user_edited = True
            st.session_state.extraction_evidence = {}  # Manual edits supersede previous extraction evidence.
            spec = candidate
            st.success('Draft updated. Validation is independent of form parsing.')
    with st.expander('Current specification (JSON)'):
        st.json(spec.model_dump(mode='json'))
    report = validate(spec, user_edited=st.session_state.spec_user_edited)
    st.subheader('Validation')
    st.write(f'**{report.status}**')
    if report.diagnostics:
        for d in report.diagnostics:
            st.write(f'- `{d.code}` at `{d.path}`: {d.message}')
    else:
        st.caption('Minimal schema and registry checks passed. Not an execution guarantee.')
    st.subheader('Generate engine input files')
    st.caption('v0.2 multi-engine templates. Never executes simulations; unresolved settings remain placeholders.')
    from simspeak.engine_adapters import ENGINES, generate_engine_template
    engine = st.selectbox('Target engine for generation', ENGINES)
    lammps_units = st.selectbox('LAMMPS unit system (generation-time choice)', ['Not specified', 'real', 'metal']) if engine == 'LAMMPS' else 'Not specified'
    selected_units = None if lammps_units == 'Not specified' else lammps_units
    structure_mode = st.radio('Structure source for generation', ['Generate standard crystal (ASE)', 'Upload structure file'], horizontal=True)
    structure_bytes = None
    structure_filename = None
    structure_provenance = None
    if structure_mode == 'Generate standard crystal (ASE)':
        st.caption('All crystal parameters must be supplied explicitly. No lattice constant or supercell is assumed.')
        element = st.text_input('Element symbol', value='', placeholder='Ar or Si')
        crystal = st.selectbox('Crystal structure', ['Not specified', 'fcc', 'bcc', 'sc', 'diamond'])
        lattice_text = st.text_input('Lattice parameter a (angstrom)', value='', placeholder='Required, e.g. 5.26')
        repeat_text = st.text_input('Supercell repetitions (nx,ny,nz)', value='', placeholder='Required, e.g. 4,4,4')
        source_identity = (structure_mode, element, crystal, lattice_text, repeat_text)
    else:
        uploaded = st.file_uploader('Upload a structure file', type=['cif', 'xyz', 'vasp', 'poscar'])
        source_identity = (structure_mode, uploaded.name, uploaded.getvalue()) if uploaded else (structure_mode, None)
    current_key = (spec.model_dump_json(), engine, selected_units, source_identity)
    if st.button('Generate input template ZIP'):
        from simspeak.qe_generator import GenerationBlocked
        try:
            if structure_mode == 'Generate standard crystal (ASE)':
                from simspeak.structure_sources import generate_crystal
                if not lattice_text.strip() or not repeat_text.strip() or not element.strip() or crystal == 'Not specified':
                    raise GenerationBlocked('Specify element, lattice parameter and all three supercell repetitions')
                try:
                    lattice = float(lattice_text)
                    parts = [int(x.strip()) for x in repeat_text.split(',')]
                except ValueError as exc:
                    raise GenerationBlocked('Lattice parameter must be numeric and repetitions must be comma-separated integers') from exc
                structure_bytes, structure_filename, structure_provenance = generate_crystal(element, crystal, lattice, tuple(parts))
            else:
                if uploaded is None:
                    raise GenerationBlocked('Upload a structure file first')
                structure_bytes, structure_filename = uploaded.getvalue(), uploaded.name
            # Keep the universal four-field schema unchanged; generation-time structure
            # provenance is recorded separately and never silently added to the JSON.
            generation_spec = spec.model_copy(deep=True)
            generation_spec.structure.source = structure_filename
            package = generate_engine_template(generation_spec, structure_bytes, filename=structure_filename, engine=engine, lammps_units=selected_units)
            if structure_provenance is not None:
                from io import BytesIO
                import zipfile
                zip_buffer = BytesIO()
                with zipfile.ZipFile(BytesIO(package.content)) as original, zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as output:
                    for name in original.namelist():
                        output.writestr(name, original.read(name))
                    output.writestr('structure_generation.json', json.dumps(structure_provenance, indent=2))
                    output.writestr(structure_filename, structure_bytes)
                package_content = zip_buffer.getvalue()
            else:
                package_content = package.content
        except (GenerationBlocked, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state.generated_package = package_content
            st.session_state.generated_key = current_key
            st.success('Input package generated. Review the generation report and any unresolved placeholders.')
    if st.session_state.get('generated_package') is not None:
        if st.session_state.get('generated_key') == current_key:
            st.download_button('Download input ZIP', st.session_state.generated_package, file_name='simspeak-v0.3-inputs.zip', mime='application/zip')
        else:
            st.warning('Inputs changed since generation. Generate again.')
    with st.expander('Verified extraction evidence'):
        st.json(st.session_state.extraction_evidence)
        for note in st.session_state.extraction_notes:
            st.caption(note)
    with st.expander('Validation report (JSON)'):
        st.json(report.as_dict())
with chat_col:
    st.subheader('Chat')
    st.caption('Verified chat extraction populates fields; unspecified values stay blank.')
    use_ollama = st.checkbox('Use Ollama proposals (optional)', value=False, help='LLM suggestions are admitted only if independently matched by deterministic extraction. Requires a running Ollama server.')
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    if prompt := st.chat_input('Describe your simulation...'):
        history = list(st.session_state.messages)
        st.session_state.messages.append({'role': 'user', 'content': prompt})
        with st.chat_message('user'):
            st.markdown(prompt)
        try:
            candidate, changes, notes = apply_chat_revision(SimulationSpec.model_validate(st.session_state.spec), prompt, use_ollama=use_ollama)
            if changes:
                st.session_state.spec_undo.append(st.session_state.spec.copy())
            st.session_state.spec = candidate.model_dump(mode='json')
            st.session_state.extraction_evidence = {p: prompt for p, _, _ in changes}
            st.session_state.extraction_notes = notes
            # Every extracted value has already passed the deterministic allowlist.
            # User-edited=True avoids the legacy all-or-nothing evidence validator;
            # provenance is checked BEFORE the merge and retained in session state.
            st.session_state.spec_user_edited = True
            report = validate(candidate, user_edited=True)
            count = len(changes)
            reply = f'Extracted {count} verified field(s). Validation: **{report.status}**.'
            if changes:
                reply += '\n\n**Changes:** ' + ', '.join(f'`{p}`: {old!r} → {new!r}' for p, old, new in changes)
            if notes:
                reply += '\n\n' + '\n'.join('- ' + note for note in notes)
            if report.diagnostics:
                reply += '\n\n**Validation findings:**\n' + '\n'.join(
                    f'- `{d.code}` `{d.path}`: {d.message}' for d in report.diagnostics
                )
        except Exception as exc:
            reply = f'No fields were updated: {exc}'
        st.session_state.messages.append({'role': 'assistant', 'content': reply})
        st.rerun()

st.divider()
st.header('v0.3 reference workflows')
st.caption('Opt-in reproducible examples. No simulation is executed by SimSpeak.')
ref_mode = st.radio('Reference package', ['Argon LJ / LAMMPS NPT', 'Silicon PBE / Quantum ESPRESSO SCF'])
if ref_mode.startswith('Argon'):
    from dataclasses import asdict
    from simspeak.argon_reference import ArgonLJConfig
    from simspeak.reference_workflows import argon_reference_from_spec
    from pathlib import Path
    example = json.loads((Path(__file__).parent / 'config' / 'argon_lj_example.json').read_text())
    st.caption('Review the complete example parameterization. The temperature, pressure, timestep and steps come from your current JSON specification.')
    st.json(example)
    approved = st.checkbox('I approve the explicit argon reference parameters shown above')
    if st.button('Prepare argon reference', disabled=not approved):
        try:
            data = argon_reference_from_spec(SimulationSpec.model_validate(st.session_state.spec), ArgonLJConfig(**example))
        except (ValueError, TypeError) as exc:
            st.error(str(exc))
        else:
            st.session_state.reference_download = ('argon-lammps.zip', data)
else:
    from simspeak.reference_workflows import silicon_qe_reference_from_spec
    st.caption('Set the silicon structure filename, PBE, plane_wave basis, cutoff, k-point mesh and Si pseudopotential mapping in the universal JSON. Upload the matching structure and UPF here.')
    silicon_structure = st.file_uploader('Silicon periodic structure', type=['cif', 'xyz'], key='silicon_structure')
    silicon_pseudo = st.file_uploader('Silicon UPF pseudopotential', type=['UPF', 'upf'], key='silicon_pseudo')
    if st.button('Prepare silicon QE reference'):
        try:
            if silicon_structure is None or silicon_pseudo is None:
                raise ValueError('Upload both the silicon structure and the UPF file')
            data = silicon_qe_reference_from_spec(SimulationSpec.model_validate(st.session_state.spec),
                       silicon_structure.getvalue(), silicon_structure.name,
                       silicon_pseudo.name, silicon_pseudo.getvalue())
        except (ValueError, TypeError) as exc:
            st.error(str(exc))
        else:
            st.session_state.reference_download = ('silicon-qe.zip', data)
if st.session_state.get('reference_download'):
    filename, payload = st.session_state.reference_download
    st.download_button('Download reference package', payload, file_name=filename, mime='application/zip')
