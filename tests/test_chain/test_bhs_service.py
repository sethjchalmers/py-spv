"""Tests for BHS HTTP service — uses httpx mock transport."""

from __future__ import annotations

import httpx
import pytest

from spv_wallet.chain.bhs.models import ConfirmationState, MerkleRootVerification
from spv_wallet.chain.bhs.service import BHSService
from spv_wallet.config.settings import BHSConfig
from spv_wallet.errors.chain_errors import BHSError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bhs_config(**overrides) -> BHSConfig:
    defaults = {"url": "https://bhs.test.com", "auth_token": "test-token"}
    defaults.update(overrides)
    return BHSConfig(**defaults)


def _mock_transport(handler):
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestBHSServiceLifecycle:
    async def test_not_connected_by_default(self):
        bhs = BHSService(_bhs_config())
        assert bhs.is_connected is False

    async def test_connect_and_close(self):
        bhs = BHSService(_bhs_config())
        await bhs.connect()
        assert bhs.is_connected is True
        await bhs.close()
        assert bhs.is_connected is False

    async def test_close_idempotent(self):
        bhs = BHSService(_bhs_config())
        await bhs.close()

    async def test_not_connected_raises(self):
        bhs = BHSService(_bhs_config())
        with pytest.raises(BHSError, match="not connected"):
            await bhs.verify_merkle_roots([])


# ---------------------------------------------------------------------------
# Verify Merkle Roots
# ---------------------------------------------------------------------------


class TestBHSVerify:
    async def test_verify_confirmed(self):
        def handler(request: httpx.Request):
            assert "merkleroot/verify" in str(request.url)
            return httpx.Response(200, json={
                "confirmationState": "CONFIRMED",
                "confirmations": [
                    {"merkleRoot": "aabb", "blockHeight": 100, "confirmation": "CONFIRMED"}
                ],
            })

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        roots = [MerkleRootVerification(merkle_root="aabb", block_height=100)]
        result = await bhs.verify_merkle_roots(roots)
        assert result.all_confirmed is True
        assert len(result.confirmations) == 1
        await bhs.close()

    async def test_verify_invalid(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={
                "confirmationState": "INVALID",
                "confirmations": [],
            })

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        roots = [MerkleRootVerification(merkle_root="bad", block_height=1)]
        result = await bhs.verify_merkle_roots(roots)
        assert result.all_confirmed is False
        await bhs.close()

    async def test_verify_http_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="server error")

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        with pytest.raises(BHSError, match="500"):
            await bhs.verify_merkle_roots([])
        await bhs.close()


# ---------------------------------------------------------------------------
# Get Merkle Roots
# ---------------------------------------------------------------------------


class TestBHSGetRoots:
    async def test_get_merkle_roots(self):
        def handler(request: httpx.Request):
            assert "page=0" in str(request.url)
            return httpx.Response(200, json={
                "content": [
                    {"merkleRoot": "aaa", "blockHeight": 1, "confirmation": "CONFIRMED"},
                ],
                "page": {"number": 0, "totalPages": 5, "totalElements": 50},
            })

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        result = await bhs.get_merkle_roots(page=0, size=10)
        assert len(result.content) == 1
        assert result.total_pages == 5
        await bhs.close()

    async def test_get_merkle_roots_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(403, json={"detail": "forbidden"})

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        with pytest.raises(BHSError, match="403"):
            await bhs.get_merkle_roots()
        await bhs.close()


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


class TestBHSHealthcheck:
    async def test_healthcheck_ok(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, text="ok")

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        assert await bhs.healthcheck() is True
        await bhs.close()

    async def test_healthcheck_fail(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="error")

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        assert await bhs.healthcheck() is False
        await bhs.close()


# ---------------------------------------------------------------------------
# is_valid_root convenience
# ---------------------------------------------------------------------------


class TestBHSIsValidRoot:
    async def test_valid_root(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={
                "confirmationState": "CONFIRMED",
                "confirmations": [],
            })

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        assert await bhs.is_valid_root("aabb", 100) is True
        await bhs.close()

    async def test_invalid_root(self):
        def handler(request: httpx.Request):
            return httpx.Response(200, json={
                "confirmationState": "INVALID",
                "confirmations": [],
            })

        bhs = BHSService(_bhs_config())
        await bhs.connect()
        bhs._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url="https://bhs.test.com")

        assert await bhs.is_valid_root("bad", 1) is False
        await bhs.close()

    async def test_auth_token_header(self):
        bhs = BHSService(_bhs_config(auth_token="my-token"))
        await bhs.connect()
        assert bhs._client.headers.get("Authorization") == "Bearer my-token"
        await bhs.close()
