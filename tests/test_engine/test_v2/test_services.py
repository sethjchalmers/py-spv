"""Tests for V2 services — users, paymails, contacts."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.errors.definitions import (
    ErrContactDuplicate,
    ErrContactInvalidStatus,
    ErrContactNotFound,
    ErrInvalidPubKey,
    ErrMissingFieldPubKey,
    ErrPaymailDuplicate,
    ErrPaymailNotFound,
    ErrUserAlreadyExists,
    ErrUserNotFound,
)

# Deterministic compressed public key (starts with 02, 66 hex chars)
_PUB_KEY = "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
_PUB_KEY_2 = "03c6047f9441ed7d6d3045406e95c07cd85c778e4b8cef3ca7abac09b95c709ee5"


@pytest.fixture
async def engine():
    """Create an initialized engine with in-memory SQLite."""
    config = AppConfig(
        db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


# ===================================================================
# Users Service
# ===================================================================


class TestUsersService:
    """Tests for V2 UsersService."""

    async def test_create_user(self, engine: SPVWalletEngine) -> None:
        user = await engine.v2.users.create_user(_PUB_KEY)
        assert user.pub_key == _PUB_KEY
        assert len(user.id) == 34  # Base58Check address length

    async def test_create_user_missing_pubkey(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrMissingFieldPubKey)):
            await engine.v2.users.create_user("")

    async def test_create_user_invalid_pubkey_short(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrInvalidPubKey)):
            await engine.v2.users.create_user("02abcdef")

    async def test_create_user_invalid_prefix(self, engine: SPVWalletEngine) -> None:
        bad_key = "04" + "a" * 64  # Uncompressed prefix
        with pytest.raises(type(ErrInvalidPubKey)):
            await engine.v2.users.create_user(bad_key)

    async def test_create_user_duplicate(self, engine: SPVWalletEngine) -> None:
        await engine.v2.users.create_user(_PUB_KEY)
        with pytest.raises(type(ErrUserAlreadyExists)):
            await engine.v2.users.create_user(_PUB_KEY)

    async def test_get_user(self, engine: SPVWalletEngine) -> None:
        created = await engine.v2.users.create_user(_PUB_KEY)
        found = await engine.v2.users.get_user(created.id)
        assert found.pub_key == _PUB_KEY

    async def test_get_user_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrUserNotFound)):
            await engine.v2.users.get_user("nonexistent")

    async def test_get_by_pub_key(self, engine: SPVWalletEngine) -> None:
        await engine.v2.users.create_user(_PUB_KEY)
        found = await engine.v2.users.get_user_by_pub_key(_PUB_KEY)
        assert found is not None
        assert found.pub_key == _PUB_KEY

    async def test_get_by_pub_key_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.v2.users.get_user_by_pub_key(_PUB_KEY)
        assert result is None

    async def test_list_users(self, engine: SPVWalletEngine) -> None:
        await engine.v2.users.create_user(_PUB_KEY)
        await engine.v2.users.create_user(_PUB_KEY_2)
        users = await engine.v2.users.list_users()
        assert len(users) == 2

    async def test_list_users_pagination(self, engine: SPVWalletEngine) -> None:
        await engine.v2.users.create_user(_PUB_KEY)
        await engine.v2.users.create_user(_PUB_KEY_2)
        page1 = await engine.v2.users.list_users(page=1, page_size=1)
        assert len(page1) == 1
        page2 = await engine.v2.users.list_users(page=2, page_size=1)
        assert len(page2) == 1

    async def test_delete_user(self, engine: SPVWalletEngine) -> None:
        created = await engine.v2.users.create_user(_PUB_KEY)
        await engine.v2.users.delete_user(created.id)
        with pytest.raises(type(ErrUserNotFound)):
            await engine.v2.users.get_user(created.id)

    async def test_delete_user_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrUserNotFound)):
            await engine.v2.users.delete_user("nonexistent")


# ===================================================================
# Paymails Service
# ===================================================================


class TestPaymailsServiceV2:
    """Tests for V2 PaymailsServiceV2."""

    async def _create_user(self, engine: SPVWalletEngine) -> str:
        user = await engine.v2.users.create_user(_PUB_KEY)
        return user.id

    async def test_create_paymail(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        pm = await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")
        assert pm.alias == "alice"
        assert pm.domain == "example.com"
        assert pm.user_id == user_id

    async def test_create_paymail_with_details(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        pm = await engine.v2.paymails.create_paymail(
            user_id,
            "alice",
            "example.com",
            public_name="Alice",
            avatar="https://example.com/avatar.png",
        )
        assert pm.public_name == "Alice"
        assert pm.avatar == "https://example.com/avatar.png"

    async def test_create_paymail_missing_alias(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        from spv_wallet.errors.definitions import ErrInvalidPaymail

        with pytest.raises(type(ErrInvalidPaymail)):
            await engine.v2.paymails.create_paymail(user_id, "", "example.com")

    async def test_create_paymail_user_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrUserNotFound)):
            await engine.v2.paymails.create_paymail("no-such-user", "alice", "example.com")

    async def test_create_paymail_duplicate(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")
        with pytest.raises(type(ErrPaymailDuplicate)):
            await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")

    async def test_get_paymail(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        pm = await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")
        found = await engine.v2.paymails.get_paymail(pm.id)
        assert found.alias == "alice"

    async def test_get_paymail_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrPaymailNotFound)):
            await engine.v2.paymails.get_paymail(99999)

    async def test_get_by_address(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")
        found = await engine.v2.paymails.get_by_address("alice", "example.com")
        assert found is not None
        assert found.alias == "alice"

    async def test_get_by_address_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.v2.paymails.get_by_address("noone", "nowhere.com")
        assert result is None

    async def test_list_for_user(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.paymails.create_paymail(user_id, "a1", "d.com")
        await engine.v2.paymails.create_paymail(user_id, "a2", "d.com")
        result = await engine.v2.paymails.list_for_user(user_id)
        assert len(result) == 2

    async def test_list_all(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.paymails.create_paymail(user_id, "a1", "d.com")
        result = await engine.v2.paymails.list_all()
        assert len(result) >= 1

    async def test_delete_paymail(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        pm = await engine.v2.paymails.create_paymail(user_id, "alice", "example.com")
        await engine.v2.paymails.delete_paymail(pm.id)
        with pytest.raises(type(ErrPaymailNotFound)):
            await engine.v2.paymails.get_paymail(pm.id)

    async def test_delete_paymail_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrPaymailNotFound)):
            await engine.v2.paymails.delete_paymail(99999)


# ===================================================================
# Contacts Service
# ===================================================================


class TestContactsServiceV2:
    """Tests for V2 ContactsServiceV2."""

    async def _create_user(self, engine: SPVWalletEngine) -> str:
        user = await engine.v2.users.create_user(_PUB_KEY)
        return user.id

    async def test_create_contact(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(
            user_id,
            full_name="Bob",
            paymail="bob@test.com",
        )
        assert c.full_name == "Bob"
        assert c.status == "unconfirmed"
        assert c.user_id == user_id

    async def test_create_contact_duplicate(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.contacts.create_contact(
            user_id,
            full_name="Bob",
            paymail="bob@test.com",
        )
        with pytest.raises(type(ErrContactDuplicate)):
            await engine.v2.contacts.create_contact(
                user_id,
                full_name="Bob2",
                paymail="bob@test.com",
            )

    async def test_create_contact_no_paymail_allows_duplicates(
        self,
        engine: SPVWalletEngine,
    ) -> None:
        user_id = await self._create_user(engine)
        c1 = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        c2 = await engine.v2.contacts.create_contact(user_id, full_name="Bob2")
        assert c1.id != c2.id

    async def test_get_contact(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        found = await engine.v2.contacts.get_contact(c.id)
        assert found.full_name == "Bob"

    async def test_get_contact_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrContactNotFound)):
            await engine.v2.contacts.get_contact(99999)

    async def test_list_for_user(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.contacts.create_contact(user_id, full_name="A")
        await engine.v2.contacts.create_contact(user_id, full_name="B")
        contacts = await engine.v2.contacts.list_for_user(user_id)
        assert len(contacts) == 2

    async def test_list_for_user_with_status_filter(
        self,
        engine: SPVWalletEngine,
    ) -> None:
        user_id = await self._create_user(engine)
        await engine.v2.contacts.create_contact(user_id, full_name="A")
        c2 = await engine.v2.contacts.create_contact(user_id, full_name="B")
        await engine.v2.contacts.update_status(c2.id, "awaiting")

        unconf = await engine.v2.contacts.list_for_user(user_id, status="unconfirmed")
        assert len(unconf) == 1
        assert unconf[0].full_name == "A"

    async def test_update_status_valid_transition(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        assert c.status == "unconfirmed"

        updated = await engine.v2.contacts.update_status(c.id, "awaiting")
        assert updated.status == "awaiting"

    async def test_update_status_to_confirmed(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        await engine.v2.contacts.update_status(c.id, "awaiting")
        updated = await engine.v2.contacts.update_status(c.id, "confirmed")
        assert updated.status == "confirmed"

    async def test_update_status_invalid_transition(
        self,
        engine: SPVWalletEngine,
    ) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        # unconfirmed → confirmed is not a valid direct transition
        with pytest.raises(type(ErrContactInvalidStatus)):
            await engine.v2.contacts.update_status(c.id, "confirmed")

    async def test_update_status_rejected_is_terminal(
        self,
        engine: SPVWalletEngine,
    ) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        await engine.v2.contacts.update_status(c.id, "rejected")
        with pytest.raises(type(ErrContactInvalidStatus)):
            await engine.v2.contacts.update_status(c.id, "unconfirmed")

    async def test_delete_contact(self, engine: SPVWalletEngine) -> None:
        user_id = await self._create_user(engine)
        c = await engine.v2.contacts.create_contact(user_id, full_name="Bob")
        await engine.v2.contacts.delete_contact(c.id)
        with pytest.raises(type(ErrContactNotFound)):
            await engine.v2.contacts.get_contact(c.id)

    async def test_delete_contact_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrContactNotFound)):
            await engine.v2.contacts.delete_contact(99999)
