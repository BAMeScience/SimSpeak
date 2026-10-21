from pathlib import Path
from streamlit.testing.v1 import AppTest
APP_PATH = Path(__file__).resolve().parents[1] / 'app.py'

def test_app_starts():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert len(at.exception) == 0
    assert any(w.label == 'Structure file' for w in at.text_input)
    assert any(w.label == 'Method' for w in at.selectbox)

def test_chat_still_works():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.chat_input[0].set_value('Hello').run()
    assert len(at.exception) == 0
    assert len(at.session_state['messages']) == 2

def test_reset():
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    at.session_state['spec'] = {'structure':{'source':'si.cif'},'method':'dft','calculator':{'name':None,'parameters':{}},'task':{'type':None,'parameters':{}}}
    next(b for b in at.sidebar.button if b.label == 'Reset fields').click().run()
    assert at.session_state['spec']['method'] is None
