"""Shared fixtures for integration tests.

These fixtures create a REAL SPVWalletEngine with an in-memory SQLite
database — no mocks.  They provide a fully initialized engine, a
registered xPub, and seeded UTXOs for transaction lifecycle testing.
"""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from spv_wallet.bsv.keys import ExtendedKey, xpub_id
from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine

# Deterministic test keys (from known seed)
SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
MASTER = ExtendedKey.from_seed(SEED)
RAW_XPUB = MASTER.neuter().to_string()
XPUB_ID = xpub_id(RAW_XPUB)


@pytest.fixture
async def engine() -> AsyncIterator[SPVWalletEngine]:
    """Provide a fully initialized engine with in-memory SQLite."""
    config = AppConfig(
        db=DatabaseConfig(
            engine=DatabaseEngine.SQLITE,
            dsn="sqlite+aiosqlite:///:memory:",
        ),
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


@pytest.fixture
async def engine_with_xpub(engine: SPVWalletEngine) -> AsyncIterator[SPVWalletEngine]:
    """Engine with a registered xPub (ready for destinations & transactions)."""
    await engine.xpub_service.new_xpub(RAW_XPUB)
    yield engine


async def seed_utxos(
    engine: SPVWalletEngine,
    count: int = 5,
    sats: int = 10_000,
) -> list[str]:
    """Seed UTXOs for the test xPub and return their IDs.

    Args:
        engine: Initialized engine with registered xPub.
        count: Number of UTXOs to create.
        sats: Satoshi value per UTXO.

    Returns:
        List of UTXO IDs.
    """
    p2pkh = "76a914" + "ab" * 20 + "88ac"
    ids = []
    for i in range(count):
        utxo = await engine.utxo_service.new_utxo(
            xpub_id=XPUB_ID,
            transaction_id="a" * 63 + f"{i:01x}",
            output_index=0,
            satoshis=sats,
            script_pub_key=p2pkh,
        )
        ids.append(utxo.id)
    return ids
