"""Smoke tests for the app factory and health endpoints."""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "finpilot-backend"


def test_root_has_disclaimer() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "educational" in res.json()["disclaimer"].lower()
