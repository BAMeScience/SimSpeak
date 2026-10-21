"""SimSpeak step 2: mock chat + manual form editing of a shared Pydantic draft."""

import streamlit as st
from pydantic import ValidationError

from simspeak.chat_backend import send_message
from simspeak.form import parse_form
from simspeak.models import SimulationSpec, generation_issues

st.set_page_config(page_title="SimSpeak", page_icon="⚛️", layout="wide")
st.title("SimSpeak")
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            width: 230px !important;
            min-width: 230px !important;
            max-width: 230px !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: 230px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "spec" not in st.session_state:
    st.session_state.spec = SimulationSpec().model_dump(mode="json")

with st.sidebar:
    st.subheader("Controls")

    if st.button(
        "Clear chat",
        help="Delete the current conversation. Simulation fields are preserved.",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.rerun()

    if st.button(
        "Reset fields",
        help="Restore the default simulation specification. Chat history is preserved.",
        use_container_width=True,
    ):
        st.session_state.spec = SimulationSpec().model_dump(mode="json")
        st.rerun()

spec = SimulationSpec.model_validate(st.session_state.spec)
chat_col, form_col = st.columns([1.15, 1], gap="large")

with form_col:
    st.subheader("Simulation fields")
    st.caption(
        "Edit values manually and select **Apply changes**. Empty numeric fields are allowed in a draft."
    )
    structures = ["", "fcc", "bcc", "diamond"]
    with st.form("simulation_form"):
        element = st.text_input("Element", value=spec.element or "", placeholder="Si")
        structure = st.selectbox(
            "Crystal structure",
            structures,
            index=structures.index(spec.crystal_structure or ""),
            format_func=lambda x: "— Select —" if not x else x,
        )
        lattice = st.text_input(
            "Lattice parameter (Å)",
            value="" if spec.lattice_parameter is None else str(spec.lattice_parameter),
            placeholder="5.43",
        )
        calculation = st.selectbox(
            "Calculation",
            ["single_point", "relaxation"],
            index=["single_point", "relaxation"].index(spec.calculation),
        )
        xc = st.selectbox(
            "XC functional",
            ["PBE", "LDA"],
            index=["PBE", "LDA"].index(spec.xc_functional),
        )
        cutoff = st.text_input(
            "Plane-wave cutoff (eV)",
            value="" if spec.cutoff_ev is None else str(spec.cutoff_ev),
            placeholder="400",
        )
        mesh = st.text_input(
            "K-point grid (three integers)",
            value="" if spec.kpoints is None else " ".join(map(str, spec.kpoints)),
            placeholder="4 4 4",
        )
        engine = st.selectbox(
            "DFT engine",
            ["quantum_espresso", "gpaw"],
            index=["quantum_espresso", "gpaw"].index(spec.engine),
        )
        _, button_col = st.columns([2, 1])

        with button_col:
            submitted = st.form_submit_button(
                "Apply changes",
                type="primary",
                use_container_width=True,
            )

    if submitted:
        try:
            candidate = parse_form(
                {
                    "element": element,
                    "crystal_structure": structure,
                    "lattice_parameter": lattice,
                    "calculation": calculation,
                    "xc_functional": xc,
                    "cutoff_ev": cutoff,
                    "kpoints": mesh,
                    "engine": engine,
                }
            )
        except (ValueError, ValidationError) as exc:
            st.error(f"Changes not saved: {exc}")
        else:
            st.session_state.spec = candidate.model_dump(mode="json")
            st.success("Simulation draft updated.")
            spec = candidate

    with st.expander(
        "Current specification (JSON)",
        expanded=False,
    ):
        st.caption(
            "This is the structured representation of your simulation, "
            "validated using Pydantic. It will be used to generate "
            "simulation input files."
        )
        st.json(spec.model_dump(mode="json"))
    issues = generation_issues(spec)
    if issues:
        st.info("Not ready for file generation yet: " + "; ".join(issues))
    else:
        st.success(
            "Required draft fields are filled. Input generation will be added later."
        )

with chat_col:
    st.subheader("Chat")
    st.caption(
        "Messages go to `simspeak.chat_backend.send_message()` (mock for now). Chat does not edit fields yet."
    )
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("Describe your simulation..."):
        prior_history = list(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            reply = send_message(prompt, history=prior_history)
        except Exception as exc:
            st.error(f"Backend error: {exc}")
        else:
            st.session_state.messages.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.markdown(reply)
