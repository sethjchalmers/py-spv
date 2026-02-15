"""Tests for CORS middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from spv_wallet.api.middleware.cors import setup_cors


class TestCORSMiddleware:
    def test_cors_headers_present(self):
        app = FastAPI()
        setup_cors(app)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        resp = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-auth-xpub",
            },
        )
        # CORS preflight should return 200
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_allows_auth_headers(self):
        app = FastAPI()
        setup_cors(app)

        @app.get("/test")
        async def test_route():
            return {"ok": True}

        client = TestClient(app)
        resp = client.get(
            "/test",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200
        # Auth headers should be exposed
        expose_headers = resp.headers.get("access-control-expose-headers", "")
        assert "x-auth-xpub" in expose_headers
