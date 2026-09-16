from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck_returns_technical_status() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
        "version": "1.0.0",
    }
