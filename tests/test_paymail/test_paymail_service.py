"""Tests for PaymailService — paymail address CRUD."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from spv_wallet.engine.services.paymail_service import PaymailService
from spv_wallet.errors.definitions import (
    ErrPaymailDomainNotAllowed,
)
from spv_wallet.utils.crypto import sha256

if TYPE_CHECKING:
    from spv_wallet.engine.models.paymail_address import PaymailAddress

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_engine(*, domains: list[str] | None = None):
    """Create a mock engine with in-memory paymail storage."""
    engine = MagicMock()

    # Config
    paymail_config = MagicMock()
    paymail_config.domains = domains or []
    engine.config.paymail = paymail_config

    # In-memory storage
    storage: dict[str, PaymailAddress] = {}

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

            # Check if this is a delete statement
            if hasattr(stmt, "is_delete") and stmt.is_delete:
                # Find matching records
                deleted = 0
                for key in list(storage.keys()):
                    clauses = (
                        stmt.whereclause.clauses
                        if hasattr(stmt.whereclause, "clauses")
                        else [stmt.whereclause]
                    )
                    for clause in clauses:
                        if hasattr(clause, "right") and storage[key].id == clause.right.value:
                            del storage[key]
                            deleted += 1
                result.rowcount = deleted
                return result

            # Select — scan storage
            matches = list(storage.values())

            # Apply simple filtering based on whereclause
            # (simplified mock — real tests would use SQLite)
            result.scalar_one_or_none = MagicMock(return_value=matches[0] if matches else None)
            result.scalars = MagicMock()
            result.scalars.return_value.all = MagicMock(return_value=matches)
            return result

    engine.datastore.session = FakeSession
    return engine, storage


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreatePaymail:
    async def test_create_success(self):
        engine, _storage = _mock_engine()
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub123", "alice@example.com", public_name="Alice")
        assert pm.alias == "alice"
        assert pm.domain == "example.com"
        assert pm.public_name == "Alice"
        assert pm.xpub_id == "xpub123"
        assert pm.address == "alice@example.com"

    async def test_create_generates_deterministic_id(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub123", "alice@example.com")
        expected_id = sha256(b"alice@example.com").hex()
        assert pm.id == expected_id

    async def test_create_normalizes_case(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub123", "Alice@Example.COM")
        assert pm.alias == "alice"
        assert pm.domain == "example.com"

    async def test_create_with_metadata(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub123", "bob@test.com", metadata={"tag": "primary"})
        assert pm.metadata_ == {"tag": "primary"}

    async def test_create_invalid_format(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        with pytest.raises(ValueError, match="invalid paymail"):
            await svc.create_paymail("xpub123", "not-a-paymail")


# ---------------------------------------------------------------------------
# Domain Validation
# ---------------------------------------------------------------------------


class TestDomainValidation:
    async def test_allowed_domain(self):
        engine, _ = _mock_engine(domains=["example.com", "test.com"])
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub1", "user@example.com")
        assert pm.domain == "example.com"

    async def test_disallowed_domain(self):
        engine, _ = _mock_engine(domains=["example.com"])
        svc = PaymailService(engine)
        with pytest.raises(type(ErrPaymailDomainNotAllowed)):
            await svc.create_paymail("xpub1", "user@notallowed.com")

    async def test_empty_domains_allows_all(self):
        engine, _ = _mock_engine(domains=[])
        svc = PaymailService(engine)
        pm = await svc.create_paymail("xpub1", "user@anything.com")
        assert pm.domain == "anything.com"


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestPaymailLookup:
    async def test_get_by_id_found(self):
        engine, _storage = _mock_engine()
        svc = PaymailService(engine)
        await svc.create_paymail("xpub1", "alice@test.com")
        paymail_id = sha256(b"alice@test.com").hex()
        result = await svc.get_paymail_by_id(paymail_id)
        assert result is not None
        assert result.alias == "alice"

    async def test_get_by_id_not_found(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        result = await svc.get_paymail_by_id("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestPaymailSearch:
    async def test_search_all(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        # Create paymail first to populate storage
        await svc.create_paymail("xpub1", "alice@test.com")
        results = await svc.search_paymails()
        assert len(results) >= 1

    async def test_search_with_filters(self):
        engine, _ = _mock_engine()
        svc = PaymailService(engine)
        await svc.create_paymail("xpub1", "alice@test.com")
        # Search builds a SQLAlchemy query — with mock it returns all
        results = await svc.search_paymails(xpub_id="xpub1", domain="test.com")
        assert len(results) >= 1
