from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200():
    with patch("alembic.command.upgrade"):
        with TestClient(app) as client:
            r = client.get("/health")
    assert r.status_code == 200


def test_health_body_has_ok_status():
    with patch("alembic.command.upgrade"):
        with TestClient(app) as client:
            r = client.get("/health")
    assert r.json()["status"] == "ok"


def test_health_body_has_env_field():
    with patch("alembic.command.upgrade"):
        with TestClient(app) as client:
            r = client.get("/health")
    data = r.json()
    assert "env" in data
    assert data["env"] in {"development", "production"}
