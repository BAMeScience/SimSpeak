"""Convert manual Streamlit form fields into the universal draft."""
import json
from simspeak.models import SimulationSpec

def parse_form(raw: dict) -> SimulationSpec:
    def mapping(s: str, label: str) -> dict:
        if not s.strip():
            return {}
        value = json.loads(s)
        if not isinstance(value, dict):
            raise ValueError(f'{label} must be a JSON object')
        return value
    return SimulationSpec.model_validate({
        'structure': {'source': raw['source'].strip() or None},
        'method': raw['method'] or None,
        'calculator': {'name': raw['calculator'].strip() or None,
                       'parameters': mapping(raw['calculator_parameters'], 'Calculator parameters')},
        'task': {'type': raw['task'] or None,
                 'parameters': mapping(raw['task_parameters'], 'Task parameters')},
    })
