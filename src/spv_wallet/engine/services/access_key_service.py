"""AccessKey service — ephemeral key pair management."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from spv_wallet.bsv.keys import private_key_to_public_key
from spv_wallet.engine.models.access_key import AccessKey
from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.utils.crypto import sha256

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine

ErrAccessKeyNotFound = SPVError(
    "access key not found", status_code=404, code="access-key-not-found"
)

ErrAccessKeyRevoked = SPVError(
    "access key has been revoked", status_code=403, code="access-key-revoked"
)


class AccessKeyService:
    """Business logic for ephemeral API access key management.

    Mirrors the Go engine access_key.go service:
    - Generate ECDSA key pair (private returned once, public stored)
    - Look up by ID or public key
    - Revoke (soft-delete)
    - List keys per xPub
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def new_access_key(self, xpub_id: str) -> tuple[AccessKey, str]:
        """Generate a new access key pair for an xPub.

        Args:
            xpub_id: The owning xPubID.

        Returns:
            Tuple of (persisted AccessKey model, private key hex).
            The private key is returned ONLY at creation.
        """
        # Generate random key pair
        privkey_bytes = os.urandom(32)
        pubkey_bytes = private_key_to_public_key(privkey_bytes, compressed=True)
        pubkey_hex = pubkey_bytes.hex()
        privkey_hex = privkey_bytes.hex()

        # ID = SHA-256 of compressed public key hex
        key_id = sha256(pubkey_hex.encode("utf-8")).hex()

        access_key = AccessKey(
            id=key_id,
            xpub_id=xpub_id,
            key=pubkey_hex,
        )

        async with self._engine.datastore.session() as session:
            session.add(access_key)
            await session.commit()
            await session.refresh(access_key)

        return access_key, privkey_hex

    async def get_access_key(self, id_: str) -> AccessKey | None:
        """Look up an access key by its ID.

        Args:
            id_: The access key ID (SHA-256 of public key).

        Returns:
            The AccessKey model, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(AccessKey).where(
                    AccessKey.id == id_, AccessKey.deleted_at.is_(None)
                )
            )
            return result.scalar_one_or_none()

    async def get_access_key_by_pubkey(self, pubkey_hex: str) -> AccessKey | None:
        """Look up an access key by its public key.

        Args:
            pubkey_hex: The compressed public key hex string.

        Returns:
            The AccessKey model, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(AccessKey).where(
                    AccessKey.key == pubkey_hex,
                    AccessKey.deleted_at.is_(None),
                )
            )
            return result.scalar_one_or_none()

    async def revoke_access_key(self, id_: str) -> None:
        """Revoke an access key by soft-deleting it.

        Args:
            id_: The access key ID.

        Raises:
            SPVError: If key not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(AccessKey).where(
                    AccessKey.id == id_, AccessKey.deleted_at.is_(None)
                )
            )
            key = result.scalar_one_or_none()
            if key is None:
                raise ErrAccessKeyNotFound

            key.deleted_at = datetime.now(timezone.utc)
            await session.commit()

    async def get_access_keys_by_xpub(
        self, xpub_id: str
    ) -> list[AccessKey]:
        """List all active access keys for an xPub.

        Args:
            xpub_id: The xPubID.

        Returns:
            List of active AccessKey models.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(AccessKey).where(
                    AccessKey.xpub_id == xpub_id,
                    AccessKey.deleted_at.is_(None),
                ).order_by(AccessKey.created_at)
            )
            return list(result.scalars().all())

    async def count_access_keys(self, xpub_id: str) -> int:
        """Count active access keys for an xPub.

        Args:
            xpub_id: The xPubID.

        Returns:
            Count of active keys.
        """
        from sqlalchemy import func

        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(func.count(AccessKey.id)).where(
                    AccessKey.xpub_id == xpub_id,
                    AccessKey.deleted_at.is_(None),
                )
            )
            return result.scalar_one()
