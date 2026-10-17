"""GET /health, GET /demo, CORS."""

import json
from pathlib import Path

FIXTURE = json.loads(
    (Path(__file__).resolve().parents[3] / "fixtures" / "synthetic_case.json").read_text(
        encoding="utf-8"
    )
)


def test_health_reports_demo_mode_without_gemini(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "demo_mode": True}


def test_health_is_live_when_gemini_configured(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    response = client.get("/api/v1/health")
    assert response.json() == {"status": "ok", "demo_mode": False}
    assert "secret-test-key" not in response.text


def test_demo_mode_flag_forces_demo(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "m")
    monkeypatch.setenv("DEMO_MODE", "true")
    assert client.get("/api/v1/health").json()["demo_mode"] is True


def test_demo_returns_the_frozen_fixture_exactly(client):
    response = client.get("/api/v1/demo")
    assert response.status_code == 200
    assert response.json() == FIXTURE
    assert response.json()["is_demo"] is True


def test_cors_allows_local_frontend(client):
    response = client.options(
        "/api/v1/demo",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_origin_is_configurable(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("FRONTEND_ORIGIN", "https://clearbill.example, https://preview.example/")
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health", headers={"Origin": "https://preview.example"})
    assert response.headers["access-control-allow-origin"] == "https://preview.example"
