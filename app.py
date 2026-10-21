"""SimSpeak: mock chat, editable universal specification, deterministic validation."""
import json
import streamlit as st
from pydantic import ValidationError
from simspeak.chat_backend import send_message
from simspeak.form import parse_form
from simspeak.models import SimulationSpec
from simspeak.validation import validate

st.set_page_config(page_title='SimSpeak', page_icon='⚛️', layout='wide')
st.title('SimSpeak')
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'spec' not in st.session_state:
    st.session_state.spec = SimulationSpec().model_dump(mode='json')
if 'spec_user_edited' not in st.session_state:
    st.session_state.spec_user_edited = False
with st.sidebar:
    st.subheader('Controls')
    if st.button('Clear chat', use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    if st.button('Reset fields', use_container_width=True):
        st.session_state.spec = SimulationSpec().model_dump(mode='json')
        st.session_state.spec_user_edited = False
        st.rerun()
spec = SimulationSpec.model_validate(st.session_state.spec)
chat_col, form_col = st.columns([1.15, 1], gap='large')
with form_col:
    st.subheader('Simulation fields')
    st.caption('No scientific defaults. Empty fields mean unspecified. JSON parameters must be objects.')
    with st.form('simulation_form'):
        source = st.text_input('Structure file', value=spec.structure.source or '', placeholder='silicon.cif')
        methods = ['', 'classical_md', 'dft']
        method = st.selectbox('Method', methods, index=methods.index(spec.method or ''), format_func=lambda x: x or '— Select —')
        calculator = st.text_input('Calculator name', value=spec.calculator.name or '', placeholder='espresso')
        calc_params = st.text_area('Calculator parameters (JSON)', value=json.dumps(spec.calculator.parameters, indent=2))
        tasks = ['', 'single_point', 'optimize', 'md']
        task = st.selectbox('Task', tasks, index=tasks.index(spec.task.type or ''), format_func=lambda x: x or '— Select —')
        task_params = st.text_area('Task parameters (JSON)', value=json.dumps(spec.task.parameters, indent=2))
        submitted = st.form_submit_button('Apply changes', type='primary')
    if submitted:
        try:
            candidate = parse_form({'source': source, 'method': method, 'calculator': calculator,
                                    'calculator_parameters': calc_params, 'task': task,
                                    'task_parameters': task_params})
        except (ValueError, ValidationError) as exc:
            st.error(f'Changes not saved: {exc}')
        else:
            st.session_state.spec = candidate.model_dump(mode='json')
            st.session_state.spec_user_edited = True
            spec = candidate
            st.success('Draft updated. Validation is independent of Pydantic parsing.')
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
    with st.expander('Validation report (JSON)'):
        st.json(report.as_dict())
with chat_col:
    st.subheader('Chat')
    st.caption('Mock chat backend; it does not populate simulation fields.')
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    if prompt := st.chat_input('Describe your simulation...'):
        history = list(st.session_state.messages)
        st.session_state.messages.append({'role': 'user', 'content': prompt})
        with st.chat_message('user'):
            st.markdown(prompt)
        try:
            reply = send_message(prompt, history=history)
        except Exception as exc:
            st.error(f'Backend error: {exc}')
        else:
            st.session_state.messages.append({'role': 'assistant', 'content': reply})
            with st.chat_message('assistant'):
                st.markdown(reply)
