import sqlite3
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from simspeak.models import SimulationSpec, generation_issues

app = FastAPI(
    title="SimSpeak API",
    description="API for sharing validated simulation specifications.",
    version="0.1.0",
)

DB_PATH = Path("simspeak.db")


class SpecResponse(BaseModel):
    id: str
    specification: SimulationSpec
    generation_issues: list[str]


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_database():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS specifications (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )


init_database()


@app.post("/specs", response_model=SpecResponse, status_code=201)
def create_specification(spec: SimulationSpec):
    spec_id = str(uuid4())

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO specifications (id, data)
            VALUES (?, ?)
            """,
            (spec_id, spec.model_dump_json()),
        )

    return SpecResponse(
        id=spec_id,
        specification=spec,
        generation_issues=generation_issues(spec),
    )


@app.get("/specs/{spec_id}", response_model=SpecResponse)
def get_specification(spec_id: str):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT data FROM specifications WHERE id = ?",
            (spec_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Specification not found",
        )

    spec = SimulationSpec.model_validate_json(row[0])

    return SpecResponse(
        id=spec_id,
        specification=spec,
        generation_issues=generation_issues(spec),
    )
