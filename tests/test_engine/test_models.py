"""Tests for V1 ORM models — CRUD operations with in-memory SQLite."""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from spv_wallet.engine.models import (
    ALL_MODELS,
    AccessKey,
    Base,
    Contact,
    Destination,
    DraftTransaction,
    PaymailAddress,
    Transaction,
    UTXO,
    Webhook,
    Xpub,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    """Create an in-memory SQLite async engine with tables."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    """Provide an async session for testing."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------


class TestTableCreation:
    """Verify all 9 tables are created."""

    async def test_all_tables_exist(self, engine) -> None:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = {row[0] for row in result.fetchall()}
        expected_tables = {
            "xpubs",
            "access_keys",
            "destinations",
            "draft_transactions",
            "transactions",
            "utxos",
            "paymail_addresses",
            "contacts",
            "webhooks",
        }
        assert expected_tables.issubset(tables)

    def test_all_models_list_length(self) -> None:
        assert len(ALL_MODELS) == 9


# ---------------------------------------------------------------------------
# Xpub CRUD
# ---------------------------------------------------------------------------


class TestXpub:
    """Xpub model operations."""

    async def test_create_xpub(self, session: AsyncSession) -> None:
        xpub = Xpub(
            id="a" * 64,
            current_balance=0,
            next_internal_num=0,
            next_external_num=0,
        )
        session.add(xpub)
        await session.commit()
        result = await session.get(Xpub, "a" * 64)
        assert result is not None
        assert result.current_balance == 0

    async def test_update_balance(self, session: AsyncSession) -> None:
        xpub = Xpub(id="b" * 64, current_balance=0)
        session.add(xpub)
        await session.commit()
        xpub.current_balance = 100000
        await session.commit()
        result = await session.get(Xpub, "b" * 64)
        assert result is not None
        assert result.current_balance == 100000

    async def test_xpub_repr(self) -> None:
        xpub = Xpub(id="c" * 64, current_balance=500)
        assert "balance=500" in repr(xpub)

    async def test_xpub_metadata(self, session: AsyncSession) -> None:
        xpub = Xpub(
            id="d" * 64,
            metadata_={"label": "test wallet"},
        )
        session.add(xpub)
        await session.commit()
        result = await session.get(Xpub, "d" * 64)
        assert result is not None
        assert result.metadata_["label"] == "test wallet"


# ---------------------------------------------------------------------------
# AccessKey CRUD
# ---------------------------------------------------------------------------


class TestAccessKey:
    """AccessKey model operations."""

    async def test_create_access_key(self, session: AsyncSession) -> None:
        ak = AccessKey(
            id="ak" + "0" * 62,
            xpub_id="x" * 64,
            key="02" + "ab" * 32,
        )
        session.add(ak)
        await session.commit()
        result = await session.get(AccessKey, "ak" + "0" * 62)
        assert result is not None
        assert result.xpub_id == "x" * 64

    async def test_access_key_repr(self) -> None:
        ak = AccessKey(id="z" * 64, xpub_id="y" * 64, key="pub_hex")
        assert "xpub=" in repr(ak)


# ---------------------------------------------------------------------------
# Destination CRUD
# ---------------------------------------------------------------------------


class TestDestination:
    """Destination model operations."""

    async def test_create_destination(self, session: AsyncSession) -> None:
        dest = Destination(
            id="d" * 64,
            xpub_id="x" * 64,
            locking_script="76a914" + "ab" * 20 + "88ac",
            type="pubkeyhash",
            chain=0,
            num=0,
            address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        )
        session.add(dest)
        await session.commit()
        result = await session.get(Destination, "d" * 64)
        assert result is not None
        assert result.chain == 0

    async def test_destination_repr(self) -> None:
        dest = Destination(
            id="d" * 64,
            xpub_id="x" * 64,
            locking_script="abc",
            chain=1,
            num=5,
            address="test_addr",
        )
        assert "chain=1/5" in repr(dest)


# ---------------------------------------------------------------------------
# DraftTransaction CRUD
# ---------------------------------------------------------------------------


class TestDraftTransaction:
    """DraftTransaction model operations."""

    async def test_create_draft(self, session: AsyncSession) -> None:
        draft = DraftTransaction(
            id="dt" + "0" * 62,
            xpub_id="x" * 64,
            configuration={"outputs": [{"to": "addr", "satoshis": 1000}]},
            status="draft",
            total_value=1000,
            fee=100,
        )
        session.add(draft)
        await session.commit()
        result = await session.get(DraftTransaction, "dt" + "0" * 62)
        assert result is not None
        assert result.status == "draft"
        assert result.configuration["outputs"][0]["satoshis"] == 1000

    async def test_draft_repr(self) -> None:
        draft = DraftTransaction(
            id="dt" + "1" * 62,
            xpub_id="x" * 64,
            status="complete",
        )
        assert "status=complete" in repr(draft)


# ---------------------------------------------------------------------------
# Transaction CRUD
# ---------------------------------------------------------------------------


class TestTransaction:
    """Transaction model operations."""

    async def test_create_transaction(self, session: AsyncSession) -> None:
        tx = Transaction(
            id="tx" + "a" * 62,
            xpub_id="x" * 64,
            hex_body="01000000" + "0" * 100,
            status="broadcast",
            direction="outgoing",
            fee=200,
            total_value=50000,
            number_of_inputs=1,
            number_of_outputs=2,
        )
        session.add(tx)
        await session.commit()
        result = await session.get(Transaction, "tx" + "a" * 62)
        assert result is not None
        assert result.status == "broadcast"
        assert result.direction == "outgoing"

    async def test_transaction_repr(self) -> None:
        tx = Transaction(id="tx" + "b" * 62, xpub_id="x" * 64, status="mined")
        assert "status=mined" in repr(tx)


# ---------------------------------------------------------------------------
# Utxo CRUD
# ---------------------------------------------------------------------------


class TestUtxo:
    """Utxo model operations."""

    async def test_create_utxo(self, session: AsyncSession) -> None:
        utxo = UTXO(
            id="txid:0",
            xpub_id="x" * 64,
            transaction_id="tx" * 32,
            output_index=0,
            satoshis=50000,
            script_pub_key="76a914" + "ab" * 20 + "88ac",
            type="pubkeyhash",
        )
        session.add(utxo)
        await session.commit()
        result = await session.get(UTXO, "txid:0")
        assert result is not None
        assert result.satoshis == 50000
        assert not result.is_spent

    async def test_utxo_is_spent(self) -> None:
        utxo = UTXO(
            id="txid:1",
            xpub_id="x" * 64,
            transaction_id="tx" * 32,
            output_index=1,
            satoshis=1000,
            script_pub_key="script",
            spending_tx_id="spending_tx_id",
        )
        assert utxo.is_spent

    async def test_utxo_not_spent(self) -> None:
        utxo = UTXO(
            id="txid:2",
            xpub_id="x" * 64,
            transaction_id="tx" * 32,
            output_index=2,
            satoshis=1000,
            script_pub_key="script",
        )
        assert not utxo.is_spent

    async def test_utxo_repr(self) -> None:
        utxo = UTXO(
            id="test:0",
            xpub_id="x" * 64,
            transaction_id="abcdef1234567890" * 4,
            output_index=3,
            satoshis=99999,
            script_pub_key="s",
        )
        assert "sats=99999" in repr(utxo)


# ---------------------------------------------------------------------------
# PaymailAddress CRUD
# ---------------------------------------------------------------------------


class TestPaymailAddress:
    """PaymailAddress model operations."""

    async def test_create_paymail(self, session: AsyncSession) -> None:
        pm = PaymailAddress(
            id="pm" + "0" * 62,
            xpub_id="x" * 64,
            alias="alice",
            domain="example.com",
            public_name="Alice",
            avatar="https://example.com/alice.png",
        )
        session.add(pm)
        await session.commit()
        result = await session.get(PaymailAddress, "pm" + "0" * 62)
        assert result is not None
        assert result.alias == "alice"
        assert result.domain == "example.com"
        assert result.address == "alice@example.com"

    async def test_paymail_repr(self) -> None:
        pm = PaymailAddress(
            id="pm" + "1" * 62,
            xpub_id="x" * 64,
            alias="bob",
            domain="test.com",
        )
        assert "bob@test.com" in repr(pm)


# ---------------------------------------------------------------------------
# Contact CRUD
# ---------------------------------------------------------------------------


class TestContact:
    """Contact model operations."""

    async def test_create_contact(self, session: AsyncSession) -> None:
        contact = Contact(
            id="ct" + "0" * 62,
            xpub_id="x" * 64,
            full_name="Charlie",
            paymail="charlie@example.com",
            status="unconfirmed",
        )
        session.add(contact)
        await session.commit()
        result = await session.get(Contact, "ct" + "0" * 62)
        assert result is not None
        assert result.full_name == "Charlie"
        assert result.status == "unconfirmed"

    async def test_contact_repr(self) -> None:
        contact = Contact(
            id="ct" + "1" * 62,
            xpub_id="x" * 64,
            paymail="test@test.com",
            status="confirmed",
        )
        assert "test@test.com" in repr(contact)
        assert "confirmed" in repr(contact)


# ---------------------------------------------------------------------------
# Webhook CRUD
# ---------------------------------------------------------------------------


class TestWebhook:
    """Webhook model operations."""

    async def test_create_webhook(self, session: AsyncSession) -> None:
        wh = Webhook(
            id="wh" + "0" * 62,
            url="https://example.com/callback",
            token_header="X-Token",
            token_value="secret123",
        )
        session.add(wh)
        await session.commit()
        result = await session.get(Webhook, "wh" + "0" * 62)
        assert result is not None
        assert result.url == "https://example.com/callback"
        assert result.banned is False

    async def test_webhook_banned(self, session: AsyncSession) -> None:
        wh = Webhook(
            id="wh" + "1" * 62,
            url="https://example.com/bad",
            banned=True,
        )
        session.add(wh)
        await session.commit()
        result = await session.get(Webhook, "wh" + "1" * 62)
        assert result is not None
        assert result.banned is True

    async def test_webhook_repr(self) -> None:
        wh = Webhook(id="wh" + "2" * 62, url="https://long-url.example.com/webhook/path")
        assert "long-url" in repr(wh)


# ---------------------------------------------------------------------------
# Query patterns
# ---------------------------------------------------------------------------


class TestQueries:
    """Test common query patterns across models."""

    async def test_filter_utxos_by_xpub(self, session: AsyncSession) -> None:
        xpub_id = "x" * 64
        for i in range(3):
            session.add(
                UTXO(
                    id=f"txid:{i}",
                    xpub_id=xpub_id,
                    transaction_id="tx" * 32,
                    output_index=i,
                    satoshis=1000 * (i + 1),
                    script_pub_key="script",
                )
            )
        # Add one for a different xpub
        session.add(
            UTXO(
                id="other:0",
                xpub_id="y" * 64,
                transaction_id="tx" * 32,
                output_index=0,
                satoshis=9999,
                script_pub_key="script",
            )
        )
        await session.commit()

        result = await session.execute(
            select(UTXO).where(UTXO.xpub_id == xpub_id)
        )
        utxos = result.scalars().all()
        assert len(utxos) == 3

    async def test_filter_contacts_by_status(self, session: AsyncSession) -> None:
        for i, status in enumerate(["unconfirmed", "confirmed", "unconfirmed"]):
            session.add(
                Contact(
                    id=f"ct{i}" + "0" * 61,
                    xpub_id="x" * 64,
                    paymail=f"user{i}@test.com",
                    status=status,
                )
            )
        await session.commit()

        result = await session.execute(
            select(Contact).where(Contact.status == "unconfirmed")
        )
        contacts = result.scalars().all()
        assert len(contacts) == 2

    async def test_soft_delete_via_deleted_at(self, session: AsyncSession) -> None:
        """Verify deleted_at is None by default and can be set."""
        from datetime import datetime, timezone

        xpub = Xpub(id="del" + "0" * 61, current_balance=0)
        session.add(xpub)
        await session.commit()

        result = await session.get(Xpub, "del" + "0" * 61)
        assert result is not None
        assert result.deleted_at is None

        # "Soft delete"
        result.deleted_at = datetime.now(tz=timezone.utc)
        await session.commit()

        result = await session.get(Xpub, "del" + "0" * 61)
        assert result is not None
        assert result.deleted_at is not None
