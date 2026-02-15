"""Tests for PaymailServiceProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from spv_wallet.api.paymail_server.provider import PaymailServiceProvider
from spv_wallet.engine.models.paymail_address import PaymailAddress
from spv_wallet.errors.definitions import ErrPaymailNotFound


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_engine_with_paymail(
    *,
    alias: str = "alice",
    domain: str = "example.com",
    xpub_id: str = "xpub_abc",
) -> MagicMock:
    """Create a mock engine that has a paymail address registered."""
    engine = MagicMock()

    paymail = PaymailAddress(
        id="pm_id_123",
        xpub_id=xpub_id,
        alias=alias,
        domain=domain,
        public_name="Alice",
        avatar="https://example.com/avatar.png",
    )

    # Mock paymail_service
    engine.paymail_service = MagicMock()
    engine.paymail_service.get_paymail_by_alias = AsyncMock(return_value=paymail)

    # Mock xpub_service
    xpub_mock = MagicMock()
    xpub_mock.id = xpub_id
    engine.xpub_service = MagicMock()
    engine.xpub_service.get_xpub_by_id = AsyncMock(return_value=xpub_mock)

    return engine


def _mock_engine_no_paymail() -> MagicMock:
    """Create a mock engine with no paymail addresses."""
    engine = MagicMock()
    engine.paymail_service = MagicMock()
    engine.paymail_service.get_paymail_by_alias = AsyncMock(return_value=None)
    return engine


# ---------------------------------------------------------------------------
# GetPaymailByAlias
# ---------------------------------------------------------------------------


class TestGetPaymailByAlias:
    async def test_found(self):
        engine = _mock_engine_with_paymail()
        provider = PaymailServiceProvider(engine)
        pm = await provider.get_paymail_by_alias("alice", "example.com")
        assert pm.alias == "alice"
        assert pm.domain == "example.com"

    async def test_not_found(self):
        engine = _mock_engine_no_paymail()
        provider = PaymailServiceProvider(engine)
        with pytest.raises(type(ErrPaymailNotFound)):
            await provider.get_paymail_by_alias("nobody", "example.com")


# ---------------------------------------------------------------------------
# RecordTransaction
# ---------------------------------------------------------------------------


class TestRecordTransaction:
    async def test_record_with_hex(self):
        engine = _mock_engine_with_paymail()
        provider = PaymailServiceProvider(engine)
        result = await provider.record_transaction(
            "alice",
            "example.com",
            hex="aabbccdd",
            reference="ref-1",
        )
        assert "txid" in result
        assert result["note"] == "transaction received"

    async def test_record_with_beef(self):
        engine = _mock_engine_with_paymail()
        provider = PaymailServiceProvider(engine)
        result = await provider.record_transaction(
            "alice",
            "example.com",
            beef="beef_data",
            reference="ref-2",
        )
        assert "txid" in result

    async def test_record_no_data(self):
        engine = _mock_engine_with_paymail()
        provider = PaymailServiceProvider(engine)
        result = await provider.record_transaction(
            "alice",
            "example.com",
        )
        assert result["txid"] == ""
        assert "no transaction data" in result["note"]

    async def test_record_not_found(self):
        engine = _mock_engine_no_paymail()
        provider = PaymailServiceProvider(engine)
        with pytest.raises(type(ErrPaymailNotFound)):
            await provider.record_transaction(
                "nobody",
                "example.com",
                hex="ff",
            )


# ---------------------------------------------------------------------------
# VerifyMerkleRoots
# ---------------------------------------------------------------------------


class TestVerifyMerkleRoots:
    async def test_verify_no_chain_service(self):
        """When chain service is None, verification is permissive."""
        engine = _mock_engine_with_paymail()
        engine.chain_service = None
        provider = PaymailServiceProvider(engine)
        result = await provider.verify_merkle_roots(["abc123"])
        assert result is True

    async def test_verify_with_chain_service(self):
        engine = _mock_engine_with_paymail()
        bhs = AsyncMock()
        bhs.verify_merkle_roots = AsyncMock(return_value=True)
        chain = MagicMock()
        chain.bhs = bhs
        engine.chain_service = chain
        provider = PaymailServiceProvider(engine)
        result = await provider.verify_merkle_roots(["abc123"])
        assert result is True

    async def test_verify_fails_gracefully(self):
        engine = _mock_engine_with_paymail()
        bhs = AsyncMock()
        bhs.verify_merkle_roots = AsyncMock(side_effect=Exception("network error"))
        chain = MagicMock()
        chain.bhs = bhs
        engine.chain_service = chain
        provider = PaymailServiceProvider(engine)
        result = await provider.verify_merkle_roots(["abc123"])
        assert result is False
