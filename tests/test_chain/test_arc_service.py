"""Tests for ARC HTTP service — uses httpx mock transport."""

from __future__ import annotations

import httpx
import pytest

from spv_wallet.chain.arc.models import TXStatus
from spv_wallet.chain.arc.service import ARCService
from spv_wallet.config.settings import ARCConfig
from spv_wallet.errors.chain_errors import ARCError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arc_config(**overrides) -> ARCConfig:
    defaults = {
        "url": "https://arc.test.com",
        "token": "test-token",
        "deployment_id": "dep-1",
        "callback_url": "",
        "callback_token": "",
    }
    defaults.update(overrides)
    return ARCConfig(**defaults)


def _mock_transport(handler):
    """Create an httpx MockTransport from a handler function."""
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestARCServiceLifecycle:
    async def test_not_connected_by_default(self):
        arc = ARCService(_arc_config())
        assert arc.is_connected is False

    async def test_connect_and_close(self):
        arc = ARCService(_arc_config())
        await arc.connect()
        assert arc.is_connected is True
        await arc.close()
        assert arc.is_connected is False

    async def test_close_idempotent(self):
        arc = ARCService(_arc_config())
        await arc.close()  # Should not raise
        assert arc.is_connected is False

    async def test_not_connected_raises(self):
        arc = ARCService(_arc_config())
        with pytest.raises(ARCError, match="not connected"):
            await arc.broadcast("deadbeef")


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


class TestARCBroadcast:
    async def test_broadcast_success(self):
        def handler(request: httpx.Request):
            assert request.url.path == "/v1/tx"
            assert "X-WaitFor" in request.headers
            return httpx.Response(
                200,
                json={
                    "txid": "abc123",
                    "txStatus": "SEEN_ON_NETWORK",
                },
            )

        arc = ARCService(_arc_config())
        await arc.connect()
        # Replace internal client with mock
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        info = await arc.broadcast("deadbeef")
        assert info.txid == "abc123"
        assert info.status == TXStatus.SEEN_ON_NETWORK
        await arc.close()

    async def test_broadcast_201(self):
        def handler(request: httpx.Request):
            return httpx.Response(
                201,
                json={
                    "txid": "new_tx",
                    "txStatus": "QUEUED",
                },
            )

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        info = await arc.broadcast("beef")
        assert info.txid == "new_tx"
        await arc.close()

    async def test_broadcast_with_callback(self):
        def handler(request: httpx.Request):
            assert request.headers.get("X-CallbackUrl") == "https://callback.test"
            assert request.headers.get("X-CallbackToken") == "cb-token"
            return httpx.Response(200, json={"txid": "x", "txStatus": "SEEN_ON_NETWORK"})

        config = _arc_config(callback_url="https://callback.test", callback_token="cb-token")
        arc = ARCService(config)
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        await arc.broadcast("hex")
        await arc.close()

    async def test_broadcast_fee_too_low(self):
        def handler(request: httpx.Request):
            return httpx.Response(465, json={"detail": "fee too low"})

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        with pytest.raises(ARCError, match="Fee too low"):
            await arc.broadcast("hex")
        await arc.close()

    async def test_broadcast_conflict(self):
        def handler(request: httpx.Request):
            return httpx.Response(409, json={"title": "conflict"})

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        with pytest.raises(ARCError, match="conflict"):
            await arc.broadcast("hex")
        await arc.close()

    async def test_broadcast_malformed(self):
        def handler(request: httpx.Request):
            return httpx.Response(461, text="bad tx")

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        with pytest.raises(ARCError, match="malformed"):
            await arc.broadcast("hex")
        await arc.close()

    async def test_broadcast_unknown_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="internal error")

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        with pytest.raises(ARCError, match="500"):
            await arc.broadcast("hex")
        await arc.close()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class TestARCQuery:
    async def test_query_success(self):
        def handler(request: httpx.Request):
            assert "/v1/tx/abc123" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "txid": "abc123",
                    "txStatus": "MINED",
                    "blockHeight": 800000,
                },
            )

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        info = await arc.query_transaction("abc123")
        assert info.txid == "abc123"
        assert info.is_mined is True
        assert info.block_height == 800000
        await arc.close()

    async def test_query_not_found(self):
        def handler(request: httpx.Request):
            return httpx.Response(404, json={"detail": "not found"})

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        with pytest.raises(ARCError, match="404"):
            await arc.query_transaction("missing")
        await arc.close()


# ---------------------------------------------------------------------------
# Policy / Fee
# ---------------------------------------------------------------------------


class TestARCPolicy:
    async def test_get_policy(self):
        def handler(request: httpx.Request):
            return httpx.Response(
                200,
                json={
                    "policy": {
                        "maxScriptSizePolicy": 50_000_000,
                        "maxTxSizePolicy": 5_000_000,
                        "miningFee": {"satoshis": 2, "bytes": 1000},
                    }
                },
            )

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        policy = await arc.get_policy()
        assert policy.max_tx_size_policy == 5_000_000
        assert policy.mining_fee.satoshis == 2
        await arc.close()

    async def test_get_fee_unit_caches(self):
        call_count = 0

        def handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200, json={"policy": {"miningFee": {"satoshis": 3, "bytes": 1000}}}
            )

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        fee1 = await arc.get_fee_unit()
        fee2 = await arc.get_fee_unit()
        assert fee1.satoshis == 3
        assert fee2.satoshis == 3
        assert call_count == 1  # Cached after first call
        await arc.close()

    async def test_get_fee_unit_fallback_on_error(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="error")

        arc = ARCService(_arc_config())
        await arc.connect()
        arc._client = httpx.AsyncClient(
            transport=_mock_transport(handler), base_url="https://arc.test.com"
        )

        fee = await arc.get_fee_unit()
        assert fee.satoshis == 1  # Default fallback
        assert fee.bytes == 1000
        await arc.close()

    async def test_auth_header_set(self):
        def handler(request: httpx.Request):
            assert request.headers.get("Authorization") == "Bearer test-token"
            return httpx.Response(200, json={"policy": {}})

        arc = ARCService(_arc_config())
        await arc.connect()
        # The original client should have auth headers
        assert "Authorization" in arc._client.headers
        await arc.close()

    async def test_deployment_id_header(self):
        arc = ARCService(_arc_config(deployment_id="my-deploy"))
        await arc.connect()
        assert arc._client.headers.get("XDeployment-ID") == "my-deploy"
        await arc.close()
