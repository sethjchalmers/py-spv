"""Tests for ContactService — contact CRUD and status transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from spv_wallet.engine.services.contact_service import (
    CONTACT_STATUS_AWAITING,
    CONTACT_STATUS_CONFIRMED,
    CONTACT_STATUS_REJECTED,
    CONTACT_STATUS_UNCONFIRMED,
    ContactService,
)
from spv_wallet.errors.definitions import (
    ErrContactInvalidStatus,
    ErrContactNotFound,
)

if TYPE_CHECKING:
    from spv_wallet.engine.models.contact import Contact

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_engine():
    """Create a mock engine with in-memory contact storage."""
    engine = MagicMock()
    storage: dict[str, Contact] = {}

    class FakeSession:
        def __init__(self):
            self._added = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def add(self, obj):
            self._added.append(obj)
            storage[obj.id] = obj

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

        async def execute(self, stmt):
            result = MagicMock()

            # For delete — check rowcount
            if hasattr(stmt, "is_delete") and stmt.is_delete:
                deleted = 0
                # Simple match by ID from whereclause
                for key in list(storage.keys()):
                    deleted += 1
                    del storage[key]
                    break
                result.rowcount = deleted
                return result

            # For select — find matching contacts
            matches = list(storage.values())

            # Return first match or None
            result.scalar_one_or_none = MagicMock(return_value=matches[0] if matches else None)
            result.scalar_one = MagicMock(return_value=matches[0] if matches else None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=matches)
            return result

    engine.datastore.session = FakeSession
    return engine, storage


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateContact:
    async def test_create_success(self):
        engine, _storage = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact(
            "xpub1",
            "alice@example.com",
            full_name="Alice",
            pub_key="02aabb",
        )
        assert contact.xpub_id == "xpub1"
        assert contact.paymail == "alice@example.com"
        assert contact.full_name == "Alice"
        assert contact.pub_key == "02aabb"
        assert contact.status == CONTACT_STATUS_UNCONFIRMED

    async def test_create_with_status(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "bob@test.com", status=CONTACT_STATUS_AWAITING)
        assert contact.status == CONTACT_STATUS_AWAITING

    async def test_create_with_metadata(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact(
            "xpub1",
            "carol@test.com",
            metadata={"source": "pike"},
        )
        assert contact.metadata_ == {"source": "pike"}

    async def test_create_invalid_status(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        with pytest.raises(type(ErrContactInvalidStatus)):
            await svc.create_contact("xpub1", "user@test.com", status="bogus")

    async def test_create_generates_uuid_id(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com")
        assert len(contact.id) == 32  # uuid4().hex = 32 chars


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    async def test_unconfirmed_to_awaiting(self):
        engine, _storage = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com")

        # Mock the select to return this contact
        updated = await svc.update_status(contact.id, CONTACT_STATUS_AWAITING)
        assert updated.status == CONTACT_STATUS_AWAITING

    async def test_unconfirmed_to_rejected(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com")
        updated = await svc.update_status(contact.id, CONTACT_STATUS_REJECTED)
        assert updated.status == CONTACT_STATUS_REJECTED

    async def test_awaiting_to_confirmed(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com", status=CONTACT_STATUS_AWAITING)
        updated = await svc.update_status(contact.id, CONTACT_STATUS_CONFIRMED)
        assert updated.status == CONTACT_STATUS_CONFIRMED

    async def test_confirmed_to_rejected(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact(
            "xpub1", "user@test.com", status=CONTACT_STATUS_CONFIRMED
        )
        # confirmed can only go to rejected
        updated = await svc.update_status(contact.id, CONTACT_STATUS_REJECTED)
        assert updated.status == CONTACT_STATUS_REJECTED

    async def test_invalid_transition_rejected_terminal(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com", status=CONTACT_STATUS_REJECTED)
        with pytest.raises(type(ErrContactInvalidStatus)):
            await svc.update_status(contact.id, CONTACT_STATUS_CONFIRMED)

    async def test_invalid_status_value(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com")
        with pytest.raises(type(ErrContactInvalidStatus)):
            await svc.update_status(contact.id, "bogus_status")

    async def test_update_not_found(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        with pytest.raises(type(ErrContactNotFound)):
            await svc.update_status("nonexistent", CONTACT_STATUS_AWAITING)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


class TestUpsertContact:
    async def test_upsert_creates_new(self):
        engine, _storage = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.upsert_contact("xpub1", "new@test.com", full_name="New User")
        assert contact.paymail == "new@test.com"
        assert contact.full_name == "New User"

    async def test_upsert_updates_existing(self):
        engine, _storage = _mock_engine()
        svc = ContactService(engine)

        # Create first
        await svc.create_contact("xpub1", "user@test.com", full_name="Old")

        # Upsert should update
        contact = await svc.upsert_contact("xpub1", "user@test.com", full_name="Updated")
        assert contact.full_name == "Updated"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestContactSearch:
    async def test_search_all(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        await svc.create_contact("xpub1", "user@test.com")
        results = await svc.search_contacts()
        assert len(results) >= 1

    async def test_search_by_xpub(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        await svc.create_contact("xpub1", "user@test.com")
        results = await svc.search_contacts(xpub_id="xpub1")
        assert len(results) >= 1

    async def test_search_by_status(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        await svc.create_contact("xpub1", "user@test.com", status=CONTACT_STATUS_CONFIRMED)
        results = await svc.search_contacts(status=CONTACT_STATUS_CONFIRMED)
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteContact:
    async def test_delete_success(self):
        engine, storage = _mock_engine()
        svc = ContactService(engine)
        contact = await svc.create_contact("xpub1", "user@test.com")
        await svc.delete_contact(contact.id)
        # Storage should be empty after delete
        assert len(storage) == 0

    async def test_delete_not_found(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        with pytest.raises(type(ErrContactNotFound)):
            await svc.delete_contact("nonexistent")


# ---------------------------------------------------------------------------
# Get by paymail
# ---------------------------------------------------------------------------


class TestGetByPaymail:
    async def test_found(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        await svc.create_contact("xpub1", "alice@test.com")
        result = await svc.get_contact_by_paymail("xpub1", "alice@test.com")
        assert result is not None
        assert result.paymail == "alice@test.com"

    async def test_not_found(self):
        engine, _ = _mock_engine()
        svc = ContactService(engine)
        result = await svc.get_contact_by_paymail("xpub1", "nobody@test.com")
        assert result is None
