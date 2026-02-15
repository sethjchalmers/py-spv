"""Tests for auth middleware — authenticate_request, verify_auth_signature."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from spv_wallet.api.middleware.auth import (
    AUTH_SIGNATURE_TTL_SECONDS,
    AuthType,
    UserContext,
    authenticate_request,
    require_admin,
    verify_auth_signature,
)
from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.utils.crypto import sha256

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_engine():
    """Create a mock engine with xpub_service and access_key_service."""
    engine = MagicMock()
    engine.config = MagicMock()
    engine.config.admin_xpub = "xpub_admin_key"
    engine.xpub_service = AsyncMock()
    engine.access_key_service = AsyncMock()
    return engine


# ---------------------------------------------------------------------------
# AuthType + UserContext
# ---------------------------------------------------------------------------


class TestAuthType:
    def test_enum_values(self):
        assert AuthType.XPUB == 0
        assert AuthType.ACCESS_KEY == 1
        assert AuthType.ADMIN == 2


class TestUserContext:
    def test_is_admin_true(self):
        ctx = UserContext(auth_type=AuthType.ADMIN, xpub_id="test")
        assert ctx.is_admin is True

    def test_is_admin_false(self):
        ctx = UserContext(auth_type=AuthType.XPUB, xpub_id="test")
        assert ctx.is_admin is False

    def test_frozen(self):
        ctx = UserContext(auth_type=AuthType.XPUB, xpub_id="test")
        with pytest.raises(AttributeError):
            ctx.xpub_id = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# authenticate_request
# ---------------------------------------------------------------------------


class TestAuthenticateRequest:
    @pytest.mark.asyncio
    async def test_no_headers_raises_unauthorized(self, mock_engine):
        with pytest.raises(SPVError, match="unauthorized"):
            await authenticate_request(mock_engine)

    @pytest.mark.asyncio
    async def test_xpub_admin(self, mock_engine):
        ctx = await authenticate_request(mock_engine, xpub_header="xpub_admin_key")
        assert ctx.auth_type == AuthType.ADMIN
        assert ctx.xpub == "xpub_admin_key"

    @pytest.mark.asyncio
    async def test_xpub_regular_user(self, mock_engine):
        mock_engine.config.admin_xpub = "xpub_admin_key"
        xpub_record = MagicMock()
        xpub_record.id = "hashed_id"
        mock_engine.xpub_service.get_xpub_by_id.return_value = xpub_record

        ctx = await authenticate_request(mock_engine, xpub_header="xpub_user_key")
        assert ctx.auth_type == AuthType.XPUB
        assert ctx.xpub == "xpub_user_key"

    @pytest.mark.asyncio
    async def test_xpub_not_found_raises(self, mock_engine):
        mock_engine.xpub_service.get_xpub_by_id.return_value = None

        with pytest.raises(SPVError, match="unauthorized"):
            await authenticate_request(mock_engine, xpub_header="xpub_unknown")

    @pytest.mark.asyncio
    async def test_access_key_valid(self, mock_engine):
        ak = SimpleNamespace(
            id="ak_id",
            xpub_id="user_xpub_id",
            deleted_at=None,
        )
        mock_engine.access_key_service.get_access_key.return_value = ak

        ctx = await authenticate_request(mock_engine, access_key_header="pubkey_hex")
        assert ctx.auth_type == AuthType.ACCESS_KEY
        assert ctx.xpub_id == "user_xpub_id"
        assert ctx.access_key_id == "ak_id"

    @pytest.mark.asyncio
    async def test_access_key_revoked(self, mock_engine):
        ak = SimpleNamespace(
            id="ak_id",
            xpub_id="user_xpub_id",
            deleted_at="2025-01-01",
        )
        mock_engine.access_key_service.get_access_key.return_value = ak

        with pytest.raises(SPVError, match="unauthorized"):
            await authenticate_request(mock_engine, access_key_header="pubkey_hex")

    @pytest.mark.asyncio
    async def test_access_key_not_found(self, mock_engine):
        mock_engine.access_key_service.get_access_key.return_value = None

        with pytest.raises(SPVError, match="unauthorized"):
            await authenticate_request(mock_engine, access_key_header="pubkey_hex")

    @pytest.mark.asyncio
    async def test_xpub_preferred_over_access_key(self, mock_engine):
        """When both headers are provided, xPub takes priority."""
        mock_engine.config.admin_xpub = "xpub_admin_key"

        ctx = await authenticate_request(
            mock_engine,
            xpub_header="xpub_admin_key",
            access_key_header="some_key",
        )
        assert ctx.auth_type == AuthType.ADMIN


# ---------------------------------------------------------------------------
# verify_auth_signature
# ---------------------------------------------------------------------------


class TestVerifyAuthSignature:
    def test_valid_signature(self):
        body = b'{"test": "data"}'
        body_hash = sha256(body).hex()
        ts = str(int(time.time() * 1000))

        result = verify_auth_signature(
            body_bytes=body,
            auth_hash=body_hash,
            auth_time=ts,
            auth_nonce="nonce123",
            auth_signature="sig123",
        )
        assert result is True

    def test_hash_mismatch(self):
        result = verify_auth_signature(
            body_bytes=b"body",
            auth_hash="wrong_hash",
            auth_time=str(int(time.time() * 1000)),
            auth_nonce="nonce",
            auth_signature="sig",
        )
        assert result is False

    def test_expired_timestamp(self):
        body = b"body"
        body_hash = sha256(body).hex()
        # 30 seconds ago (beyond 20s TTL)
        ts = str(int((time.time() - AUTH_SIGNATURE_TTL_SECONDS - 10) * 1000))

        result = verify_auth_signature(
            body_bytes=body,
            auth_hash=body_hash,
            auth_time=ts,
            auth_nonce="nonce",
            auth_signature="sig",
        )
        assert result is False

    def test_missing_fields(self):
        result = verify_auth_signature(
            body_bytes=b"body",
            auth_hash="",
            auth_time="",
            auth_nonce="",
            auth_signature="",
        )
        assert result is False

    def test_invalid_time_format(self):
        body = b"body"
        body_hash = sha256(body).hex()
        result = verify_auth_signature(
            body_bytes=body,
            auth_hash=body_hash,
            auth_time="not_a_number",
            auth_nonce="nonce",
            auth_signature="sig",
        )
        assert result is False


# ---------------------------------------------------------------------------
# require_admin
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    def test_admin_passes(self):
        ctx = UserContext(auth_type=AuthType.ADMIN, xpub_id="test")
        require_admin(ctx)  # should not raise

    def test_user_fails(self):
        ctx = UserContext(auth_type=AuthType.XPUB, xpub_id="test")
        with pytest.raises(SPVError, match="admin"):
            require_admin(ctx)
