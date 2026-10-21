from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def create_app():
    return AppTest.from_file(
        str(APP_PATH),
        default_timeout=10,
    ).run()


def test_app_starts():
    at = create_app()

    assert len(at.exception) == 0


def test_app_has_chat_input():
    at = create_app()

    assert len(at.chat_input) == 1


def test_app_has_simulation_form():
    at = create_app()

    labels = [widget.label for widget in at.text_input]

    assert "Element" in labels
    assert "Lattice parameter (Å)" in labels
    assert "Plane-wave cutoff (eV)" in labels


def test_chat_message():
    at = create_app()

    at.chat_input[0].set_value("Calculate silicon using PBE").run()

    assert len(at.exception) == 0

    messages = at.session_state["messages"]

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_form_update():
    at = create_app()

    element_widget = next(w for w in at.text_input if w.label == "Element")

    element_widget.set_value("Si")

    submit_button = next(b for b in at.button if b.label == "Apply changes")

    submit_button.click().run()

    assert len(at.exception) == 0

    spec = at.session_state["spec"]

    assert spec["element"] == "Si"


def test_clear_chat():
    at = create_app()

    at.chat_input[0].set_value("Hello").run()

    clear_button = next(b for b in at.sidebar.button if b.label == "Clear chat")

    clear_button.click().run()

    assert at.session_state["messages"] == []


def test_reset_simulation_fields():
    at = create_app()

    at.session_state["spec"] = {
        **at.session_state["spec"],
        "element": "Si",
    }

    reset_button = next(b for b in at.sidebar.button if b.label == "Reset fields")

    reset_button.click().run()

    assert at.session_state["spec"]["element"] is None
