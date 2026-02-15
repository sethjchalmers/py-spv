"""Authentication middleware — xPub, AccessKey, Admin.

Mirrors the Go ``mappings/auth.go`` and ``mappings/check_signature.go``:
- Reads ``x-auth-xpub`` or ``x-auth-key`` headers
- Resolves the user's xPubID and auth type
- Optionally verifies body signature (``x-auth-signature``, ``x-auth-hash``,
  ``x-auth-nonce``, ``x-auth-time``)
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from spv_wallet.bsv.keys import xpub_id
from spv_wallet.errors.definitions import ErrAdminRequired, ErrUnauthorized
from spv_wallet.utils.crypto import sha256

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine

# ---------------------------------------------------------------------------
# Constants — mirror Go ``models/auth.go``
# ---------------------------------------------------------------------------

AUTH_HEADER_XPUB = "x-auth-xpub"
AUTH_HEADER_ACCESS_KEY = "x-auth-key"
AUTH_HEADER_SIGNATURE = "x-auth-signature"
AUTH_HEADER_HASH = "x-auth-hash"
AUTH_HEADER_NONCE = "x-auth-nonce"
AUTH_HEADER_TIME = "x-auth-time"

AUTH_SIGNATURE_TTL_SECONDS = 20


class AuthType(enum.IntEnum):
    """Authentication type for the current request."""

    XPUB = 0
    ACCESS_KEY = 1
    ADMIN = 2


# ---------------------------------------------------------------------------
# UserContext — passed through request state after auth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserContext:
    """Authenticated user context attached to the request."""

    auth_type: AuthType
    xpub_id: str
    xpub: str = ""
    access_key_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return self.auth_type == AuthType.ADMIN


# ---------------------------------------------------------------------------
# Authentication logic
# ---------------------------------------------------------------------------


async def authenticate_request(
    engine: SPVWalletEngine,
    *,
    xpub_header: str = "",
    access_key_header: str = "",
) -> UserContext:
    """Authenticate a request based on auth headers.

    This is a simplified V1 auth flow (no signature verification).
    Signature verification can be layered on top via ``verify_signature()``.

    Args:
        engine: The SPV wallet engine.
        xpub_header: Value of ``x-auth-xpub`` header.
        access_key_header: Value of ``x-auth-key`` header.

    Returns:
        UserContext with resolved auth type and xPubID.

    Raises:
        SPVError: If no valid auth header or user not found.
    """
    if xpub_header:
        return await _auth_by_xpub(engine, xpub_header)

    if access_key_header:
        return await _auth_by_access_key(engine, access_key_header)

    raise ErrUnauthorized


async def _auth_by_xpub(engine: SPVWalletEngine, raw_xpub: str) -> UserContext:
    """Authenticate by raw xPub string.

    Checks if the xPub matches the admin key first, then looks it up in the DB.
    """
    # Check admin
    admin_xpub = engine.config.admin_xpub
    if admin_xpub and raw_xpub == admin_xpub:
        return UserContext(
            auth_type=AuthType.ADMIN,
            xpub_id=xpub_id(raw_xpub),
            xpub=raw_xpub,
        )

    # Look up in DB
    xpub_hash = xpub_id(raw_xpub)
    xpub_record = await engine.xpub_service.get_xpub_by_id(xpub_hash)
    if xpub_record is None:
        raise ErrUnauthorized

    return UserContext(
        auth_type=AuthType.XPUB,
        xpub_id=xpub_hash,
        xpub=raw_xpub,
    )


async def _auth_by_access_key(engine: SPVWalletEngine, access_pubkey: str) -> UserContext:
    """Authenticate by access key public key hex."""
    # Look up by public key
    key_id = sha256(access_pubkey.encode("utf-8")).hex()
    ak = await engine.access_key_service.get_access_key(key_id)
    if ak is None:
        raise ErrUnauthorized

    # Verify the key is active (not revoked)
    if ak.deleted_at is not None:
        raise ErrUnauthorized

    return UserContext(
        auth_type=AuthType.ACCESS_KEY,
        xpub_id=ak.xpub_id,
        access_key_id=ak.id,
    )


# ---------------------------------------------------------------------------
# Signature verification (optional layer)
# ---------------------------------------------------------------------------


def verify_auth_signature(
    *,
    body_bytes: bytes,
    auth_hash: str,
    auth_time: str,
    auth_nonce: str,
    auth_signature: str,
) -> bool:
    """Verify the body hash and timestamp for auth signature.

    This validates the hash matches the body and the timestamp is within TTL.
    Full BSM signature verification requires the signing key, which is handled
    at a higher level.

    Args:
        body_bytes: Raw request body bytes.
        auth_hash: Value of ``x-auth-hash`` header.
        auth_time: Value of ``x-auth-time`` header (Unix ms string).
        auth_nonce: Value of ``x-auth-nonce`` header.
        auth_signature: Value of ``x-auth-signature`` header.

    Returns:
        True if basic validation passes.
    """
    if not all([auth_hash, auth_time, auth_nonce, auth_signature]):
        return False

    # Verify hash matches body
    body_hash = sha256(body_bytes).hex()
    if body_hash != auth_hash:
        return False

    # Verify timestamp is within TTL
    try:
        ts = int(auth_time) / 1000  # Convert ms to seconds
    except (ValueError, TypeError):
        return False

    now = time.time()
    return not abs(now - ts) > AUTH_SIGNATURE_TTL_SECONDS


def require_admin(ctx: UserContext) -> None:
    """Raise if the user context is not admin.

    Args:
        ctx: The authenticated user context.

    Raises:
        SPVError: If not admin.
    """
    if not ctx.is_admin:
        raise ErrAdminRequired
