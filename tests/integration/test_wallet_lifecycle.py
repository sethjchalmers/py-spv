"""Integration test — full wallet lifecycle with real engine.

Flow:
  1. Initialize engine
  2. Register xPub
  3. Derive a destination (receiving address)
  4. Seed UTXOs
  5. Check balance
  6. Create a transaction draft
  7. Record a transaction
  8. Query transaction history
  9. Close engine
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from .conftest import RAW_XPUB, XPUB_ID, seed_utxos

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


@pytest.mark.integration
class TestWalletLifecycle:
    """End-to-end wallet lifecycle using a real engine (in-memory SQLite)."""

    async def test_engine_initializes_and_closes(self, engine: SPVWalletEngine) -> None:
        """Engine can initialize and close cleanly."""
        assert engine.is_initialized
        health = await engine.health_check()
        assert health["engine"] == "ok"
        assert health["datastore"] == "ok"
        assert health["cache"] == "ok"

    async def test_register_xpub(self, engine: SPVWalletEngine) -> None:
        """Register an xPub and retrieve it."""
        xpub = await engine.xpub_service.new_xpub(RAW_XPUB)
        assert xpub.id == XPUB_ID

        fetched = await engine.xpub_service.get_xpub(RAW_XPUB)
        assert fetched is not None
        assert fetched.id == XPUB_ID

    async def test_derive_destination(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """Derive a receiving address from the registered xPub."""
        dest = await engine_with_xpub.destination_service.new_destination(
            RAW_XPUB,
            chain=0,
        )
        assert dest.address  # non-empty
        assert dest.chain == 0
        assert dest.num == 0  # first derivation

        # Derive a second — index should increment
        dest2 = await engine_with_xpub.destination_service.new_destination(
            RAW_XPUB,
            chain=0,
        )
        assert dest2.num == 1
        assert dest2.address != dest.address

    async def test_balance_with_seeded_utxos(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """Balance reflects seeded UTXOs."""
        await seed_utxos(engine_with_xpub, count=3, sats=25_000)
        balance = await engine_with_xpub.utxo_service.get_balance(XPUB_ID)
        assert balance == 75_000

    async def test_create_and_query_transaction(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """Create a draft transaction and query it back."""
        # Seed enough UTXOs
        await seed_utxos(engine_with_xpub, count=5, sats=10_000)

        # Create draft
        outputs = [{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 5_000}]
        draft = await engine_with_xpub.transaction_service.new_transaction(
            XPUB_ID,
            outputs=outputs,
        )
        assert draft.status == "draft"
        assert draft.id

        # Query draft back
        fetched = await engine_with_xpub.transaction_service.get_draft(draft.id)
        assert fetched is not None
        assert fetched.id == draft.id

    async def test_draft_appears_in_draft_query(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """Created drafts can be queried back."""
        await seed_utxos(engine_with_xpub, count=5, sats=10_000)

        outputs = [{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1_000}]
        draft = await engine_with_xpub.transaction_service.new_transaction(
            XPUB_ID,
            outputs=outputs,
        )

        fetched = await engine_with_xpub.transaction_service.get_draft(draft.id)
        assert fetched is not None
        assert fetched.id == draft.id

    async def test_utxo_count_and_list(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """UTXO count and list match seeded data."""
        await seed_utxos(engine_with_xpub, count=4, sats=8_000)

        count = await engine_with_xpub.utxo_service.count_utxos(xpub_id=XPUB_ID)
        assert count == 4

        utxos = await engine_with_xpub.utxo_service.get_utxos(xpub_id=XPUB_ID)
        assert len(utxos) == 4
        assert all(u.satoshis == 8_000 for u in utxos)

    async def test_double_close_is_safe(self, engine: SPVWalletEngine) -> None:
        """Closing the engine twice does not raise."""
        await engine.close()
        await engine.close()  # should be idempotent

    async def test_access_key_lifecycle(
        self,
        engine_with_xpub: SPVWalletEngine,
    ) -> None:
        """Create and retrieve an access key."""
        key, privkey_hex = await engine_with_xpub.access_key_service.new_access_key(
            XPUB_ID,
        )
        assert key.id
        assert privkey_hex  # private key returned only at creation

        fetched = await engine_with_xpub.access_key_service.get_access_key(key.id)
        assert fetched is not None
        assert fetched.id == key.id
