"""Tests for AccessKeyService — key pair generation, lookup, revocation."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.engine.services.access_key_service import (
    ErrAccessKeyNotFound,
)

_XPUB_ID = "x" * 64


@pytest.fixture
async def engine():
    config = AppConfig(
        db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


class TestNewAccessKey:
    """Test key pair generation."""

    async def test_create_key(self, engine: SPVWalletEngine) -> None:
        key, privkey_hex = await engine.access_key_service.new_access_key(_XPUB_ID)
        assert key.id  # SHA-256 hash
        assert key.xpub_id == _XPUB_ID
        assert key.key  # Compressed public key hex (66 chars)
        assert len(key.key) == 66
        assert privkey_hex  # Private key returned
        assert len(privkey_hex) == 64

    async def test_keys_are_unique(self, engine: SPVWalletEngine) -> None:
        k1, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        k2, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        assert k1.id != k2.id

    async def test_pubkey_derives_from_privkey(self, engine: SPVWalletEngine) -> None:
        from spv_wallet.bsv.keys import private_key_to_public_key

        key, privkey_hex = await engine.access_key_service.new_access_key(_XPUB_ID)
        expected_pubkey = private_key_to_public_key(
            bytes.fromhex(privkey_hex), compressed=True
        ).hex()
        assert key.key == expected_pubkey


class TestGetAccessKey:
    """Test key lookups."""

    async def test_get_by_id(self, engine: SPVWalletEngine) -> None:
        key, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        found = await engine.access_key_service.get_access_key(key.id)
        assert found is not None
        assert found.key == key.key

    async def test_get_by_pubkey(self, engine: SPVWalletEngine) -> None:
        key, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        found = await engine.access_key_service.get_access_key_by_pubkey(key.key)
        assert found is not None
        assert found.id == key.id

    async def test_get_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.access_key_service.get_access_key("nonexistent")
        assert result is None

    async def test_get_by_pubkey_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.access_key_service.get_access_key_by_pubkey("nope")
        assert result is None


class TestRevokeAccessKey:
    """Test key revocation."""

    async def test_revoke(self, engine: SPVWalletEngine) -> None:
        key, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.revoke_access_key(key.id)
        # Should no longer be found
        result = await engine.access_key_service.get_access_key(key.id)
        assert result is None

    async def test_revoke_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrAccessKeyNotFound)):
            await engine.access_key_service.revoke_access_key("nope")


class TestListAccessKeys:
    """Test listing and counting."""

    async def test_list_by_xpub(self, engine: SPVWalletEngine) -> None:
        for _ in range(3):
            await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.new_access_key("y" * 64)

        keys = await engine.access_key_service.get_access_keys_by_xpub(_XPUB_ID)
        assert len(keys) == 3

    async def test_list_excludes_revoked(self, engine: SPVWalletEngine) -> None:
        k1, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.revoke_access_key(k1.id)

        keys = await engine.access_key_service.get_access_keys_by_xpub(_XPUB_ID)
        assert len(keys) == 1

    async def test_count(self, engine: SPVWalletEngine) -> None:
        for _ in range(4):
            await engine.access_key_service.new_access_key(_XPUB_ID)
        count = await engine.access_key_service.count_access_keys(_XPUB_ID)
        assert count == 4

    async def test_count_excludes_revoked(self, engine: SPVWalletEngine) -> None:
        k1, _ = await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.new_access_key(_XPUB_ID)
        await engine.access_key_service.revoke_access_key(k1.id)
        count = await engine.access_key_service.count_access_keys(_XPUB_ID)
        assert count == 1
