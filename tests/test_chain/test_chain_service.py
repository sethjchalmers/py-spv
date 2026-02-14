"""Tests for ChainService — composed ARC + BHS, delegation, healthcheck."""

from __future__ import annotations

from unittest.mock import AsyncMock

from spv_wallet.chain.arc.models import FeeUnit, TXInfo
from spv_wallet.chain.bhs.models import (
    ConfirmationState,
    MerkleRootVerification,
    VerifyMerkleRootsResponse,
)
from spv_wallet.chain.service import ChainService
from spv_wallet.config.settings import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides) -> AppConfig:
    defaults: dict = {}
    defaults.update(overrides)
    return AppConfig(**defaults)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestChainServiceLifecycle:
    async def test_not_connected_by_default(self):
        cs = ChainService(_config())
        assert cs.is_connected is False

    async def test_connect_and_close(self):
        cs = ChainService(_config())
        cs._arc.connect = AsyncMock()
        cs._bhs.connect = AsyncMock()
        cs._arc._client = True  # Fake connected state
        cs._bhs._client = True

        await cs.connect()
        cs._arc.connect.assert_called_once()
        cs._bhs.connect.assert_called_once()

        cs._arc.close = AsyncMock()
        cs._bhs.close = AsyncMock()
        await cs.close()
        cs._arc.close.assert_called_once()
        cs._bhs.close.assert_called_once()

    async def test_arc_property(self):
        cs = ChainService(_config())
        assert cs.arc is cs._arc

    async def test_bhs_property(self):
        cs = ChainService(_config())
        assert cs.bhs is cs._bhs


# ---------------------------------------------------------------------------
# ARC delegation
# ---------------------------------------------------------------------------


class TestChainServiceARC:
    async def test_broadcast_delegates(self):
        cs = ChainService(_config())
        expected = TXInfo(txid="abc", tx_status="SEEN_ON_NETWORK")
        cs._arc.broadcast = AsyncMock(return_value=expected)

        result = await cs.broadcast("deadbeef", wait_for="SEEN_ON_NETWORK")
        cs._arc.broadcast.assert_called_once_with("deadbeef", wait_for="SEEN_ON_NETWORK")
        assert result.txid == "abc"

    async def test_query_transaction_delegates(self):
        cs = ChainService(_config())
        expected = TXInfo(txid="xyz", tx_status="MINED")
        cs._arc.query_transaction = AsyncMock(return_value=expected)

        result = await cs.query_transaction("xyz")
        cs._arc.query_transaction.assert_called_once_with("xyz")
        assert result.is_mined is True

    async def test_get_fee_unit_delegates(self):
        cs = ChainService(_config())
        expected = FeeUnit(satoshis=2, bytes=1000)
        cs._arc.get_fee_unit = AsyncMock(return_value=expected)

        result = await cs.get_fee_unit()
        assert result.satoshis == 2


# ---------------------------------------------------------------------------
# BHS delegation
# ---------------------------------------------------------------------------


class TestChainServiceBHS:
    async def test_verify_merkle_roots_delegates(self):
        cs = ChainService(_config())
        expected = VerifyMerkleRootsResponse(confirmation_state=ConfirmationState.CONFIRMED)
        cs._bhs.verify_merkle_roots = AsyncMock(return_value=expected)

        roots = [MerkleRootVerification(merkle_root="aabb", block_height=100)]
        result = await cs.verify_merkle_roots(roots)
        assert result.all_confirmed is True
        cs._bhs.verify_merkle_roots.assert_called_once_with(roots)

    async def test_is_valid_root_delegates(self):
        cs = ChainService(_config())
        cs._bhs.is_valid_root = AsyncMock(return_value=True)

        result = await cs.is_valid_root("aabb", 100)
        assert result is True
        cs._bhs.is_valid_root.assert_called_once_with("aabb", 100)


# ---------------------------------------------------------------------------
# Healthcheck
# ---------------------------------------------------------------------------


class TestChainServiceHealthcheck:
    async def test_healthcheck_all_ok(self):
        cs = ChainService(_config())
        cs._arc._client = True  # Fake connected
        cs._bhs._client = True
        cs._bhs.healthcheck = AsyncMock(return_value=True)

        result = await cs.healthcheck()
        assert result == {"arc": "ok", "bhs": "ok"}

    async def test_healthcheck_arc_down(self):
        cs = ChainService(_config())
        cs._arc._client = None  # Not connected
        cs._bhs._client = True
        cs._bhs.healthcheck = AsyncMock(return_value=True)

        result = await cs.healthcheck()
        assert result["arc"] == "not_connected"
        assert result["bhs"] == "ok"

    async def test_healthcheck_bhs_down(self):
        cs = ChainService(_config())
        cs._arc._client = True
        cs._bhs._client = True
        cs._bhs.healthcheck = AsyncMock(return_value=False)

        result = await cs.healthcheck()
        assert result["arc"] == "ok"
        assert result["bhs"] == "error"

    async def test_healthcheck_bhs_not_connected(self):
        cs = ChainService(_config())
        cs._arc._client = True
        cs._bhs._client = None  # Not connected

        result = await cs.healthcheck()
        assert result["bhs"] == "error"
