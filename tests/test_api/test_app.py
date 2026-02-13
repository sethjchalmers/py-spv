"""Tests for the health endpoint and app factory."""

from __future__ import annotations


def test_health_endpoint(test_client):
    """GET /health should return 200 with status ok."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_app_has_openapi(test_client):
    """The app should serve an OpenAPI schema."""
    response = test_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "py-spv"
