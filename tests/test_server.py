from fastapi.testclient import TestClient
from hermes_meeting.server import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "diarization_loaded" in data


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Hermes Meeting" in response.text


def test_list_profiles():
    response = client.get("/api/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "profiles" in data
    # Check that remote beti gateway profiles are included
    profile_ids = [p["id"] for p in data["profiles"]]
    assert any("beti:" in pid for pid in profile_ids)

