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
