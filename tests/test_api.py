import pytest
from fastapi.testclient import TestClient

from simspeak import api


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Keep tests isolated from the developer's real SQLite database."""
    monkeypatch.setattr(api, "DB_PATH", tmp_path / "test_simspeak.db")
    api.init_database()
    with TestClient(api.app) as test_client:
        yield test_client


@pytest.fixture
def silicon_spec():
    return {
        "element": "Si",
        "crystal_structure": "diamond",
        "lattice_parameter": 5.43,
        "calculation": "single_point",
        "xc_functional": "PBE",
        "cutoff_ev": 400,
        "kpoints": [4, 4, 4],
        "engine": "gpaw",
    }


def test_publish_and_retrieve(client, silicon_spec):
    response = client.post("/specs", json=silicon_spec)
    assert response.status_code == 201
    created = response.json()
    assert created["id"]
    assert created["specification"]["element"] == "Si"
    assert created["generation_issues"] == []

    retrieved = client.get(f"/specs/{created['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json() == created


def test_missing_specification(client):
    response = client.get("/specs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "patch",
    [
        {"cutoff_ev": -10},
        {"lattice_parameter": 0},
        {"kpoints": [4, 0, 4]},
        {"engine": "not-a-real-engine"},
        {"unknown_field": "not-supported"},
    ],
)
def test_invalid_specification_is_rejected(client, silicon_spec, patch):
    response = client.post("/specs", json={**silicon_spec, **patch})
    assert response.status_code == 422


def test_incomplete_draft_can_be_published(client):
    response = client.post("/specs", json={})
    assert response.status_code == 201
    data = response.json()
    assert data["generation_issues"]
    assert "Element" in data["generation_issues"]


def test_qe_reports_missing_pseudopotential(client, silicon_spec):
    response = client.post(
        "/specs", json={**silicon_spec, "engine": "quantum_espresso"}
    )
    assert response.status_code == 201
    assert any(
        "pseudopotential" in issue.lower()
        for issue in response.json()["generation_issues"]
    )


def test_snapshots_are_independent(client, silicon_spec):
    first = client.post("/specs", json=silicon_spec).json()
    second = client.post("/specs", json={**silicon_spec, "cutoff_ev": 500}).json()
    assert first["id"] != second["id"]
    assert (
        client.get(f"/specs/{first['id']}").json()["specification"]["cutoff_ev"] == 400
    )
    assert (
        client.get(f"/specs/{second['id']}").json()["specification"]["cutoff_ev"] == 500
    )
