"""Small, engine-neutral draft specification. No scientific defaults."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

class Structure(StrictModel):
    source: str | None = None

class Calculator(StrictModel):
    name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

class Task(StrictModel):
    type: Literal['single_point', 'optimize', 'md'] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

class SimulationSpec(StrictModel):
    structure: Structure = Field(default_factory=Structure)
    method: Literal['classical_md', 'dft'] | None = None
    calculator: Calculator = Field(default_factory=Calculator)
    task: Task = Field(default_factory=Task)

    @model_validator(mode='after')
    def reject_nested_non_json(self):
        import json
        json.dumps(self.model_dump(mode='python'), allow_nan=False)
        return self
