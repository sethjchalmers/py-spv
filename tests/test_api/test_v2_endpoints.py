"""Tests for V2 REST API endpoints.

All service methods are mocked — we test HTTP routing, auth injection,
request validation, and response serialisation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from spv_wallet.api.app import create_app
from spv_wallet.bsv.keys import xpub_id
from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine

pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ADMIN_XPUB = "xpub_test_admin"
USER_XPUB = "xpub_test_user"
USER_XPUB_ID = xpub_id(USER_XPUB)

NOW = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_xpub_record(raw: str = USER_XPUB, balance: int = 1000):
    return SimpleNamespace(
        id=xpub_id(raw),
        current_balance=balance,
        next_internal_num=0,
        next_external_num=1,
        metadata_={"raw_xpub": raw},
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def _make_v2_user(user_id: str = "1BitcoinAddr34chars_____________"):
    return SimpleNamespace(
        id=user_id,
        pub_key="02" + "ab" * 32,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_v2_paymail(pm_id: int = 1, user_id: str = "uid1"):
    return SimpleNamespace(
        id=pm_id,
        alias="alice",
        domain="example.com",
        public_name="Alice",
        avatar="",
        user_id=user_id,
        created_at=NOW,
    )


def _make_v2_contact(contact_id: int = 1, user_id: str = "uid1"):
    return SimpleNamespace(
        id=contact_id,
        full_name="Bob",
        status="unconfirmed",
        paymail="bob@test.com",
        pub_key="",
        user_id=user_id,
        created_at=NOW,
        deleted_at=None,
    )


def _make_v2_transaction(txid: str = "aa" * 32):
    return SimpleNamespace(
        id=txid,
        tx_status="CREATED",
        block_height=None,
        block_hash=None,
        created_at=NOW,
    )


def _make_v2_operation(txid: str = "aa" * 32, user_id: str = "uid1"):
    return SimpleNamespace(
        tx_id=txid,
        user_id=user_id,
        type="outgoing",
        value=5000,
        counterparty="bob@test.com",
        created_at=NOW,
    )


def _make_v2_data(txid: str = "aa" * 32):
    return SimpleNamespace(
        tx_id=txid,
        vout=0,
        user_id="uid1",
        blob=b"\x01\x02\x03",
    )


# ---------------------------------------------------------------------------
# Mock engine
# ---------------------------------------------------------------------------


def _mock_engine():
    """Create a comprehensive mock engine with V2 services."""
    engine = MagicMock()
    engine.config = MagicMock()
    engine.config.admin_xpub = ADMIN_XPUB
    engine.config.paymail = MagicMock()
    engine.config.paymail.default_domain = "example.com"

    # V1 services (needed for auth middleware)
    engine.xpub_service = AsyncMock()
    engine.destination_service = AsyncMock()
    engine.utxo_service = AsyncMock()
    engine.access_key_service = AsyncMock()
    engine.transaction_service = AsyncMock()
    engine.contact_service = AsyncMock()
    engine.paymail_service = AsyncMock()
    engine.health_check = AsyncMock(
        return_value={"engine": "ok", "datastore": "ok", "cache": "ok", "chain": "ok"},
    )

    # V2 services
    v2 = MagicMock()
    v2.users = AsyncMock()
    v2.paymails = AsyncMock()
    v2.contacts = AsyncMock()
    v2.outlines = AsyncMock()
    v2.record = AsyncMock()
    v2.tx_sync = AsyncMock()
    engine.v2 = v2

    return engine


@pytest.fixture
def client_with_engine():
    """Create a test client with a mock engine attached to app.state."""
    config = AppConfig(
        debug=True,
        admin_xpub=ADMIN_XPUB,
        encryption_key="test-encryption-key-32bytes!!!!!",
        db=DatabaseConfig(
            engine=DatabaseEngine.SQLITE,
            dsn="sqlite+aiosqlite:///:memory:",
        ),
    )
    app = create_app(config=config)
    engine = _mock_engine()
    app.state.engine = engine

    # Default: xpub_service returns a valid user record for any lookup
    engine.xpub_service.get_xpub_by_id.return_value = _make_xpub_record()

    client = TestClient(app, raise_server_exceptions=False)
    return client, engine


def _admin_headers() -> dict[str, str]:
    return {"x-auth-xpub": ADMIN_XPUB}


def _user_headers(xpub: str = USER_XPUB) -> dict[str, str]:
    return {"x-auth-xpub": xpub}


# ===================================================================
# Users (admin-only)
# ===================================================================


class TestV2Users:
    def test_create_user(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.users.create_user.return_value = _make_v2_user()
        resp = client.post(
            "/api/v2/users",
            json={"pubKey": "02" + "ab" * 32},
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        assert "id" in resp.json()
        engine.v2.users.create_user.assert_awaited_once()

    def test_create_user_requires_admin(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.post(
            "/api/v2/users",
            json={"pubKey": "02" + "ab" * 32},
            headers=_user_headers(),
        )
        assert resp.status_code == 403

    def test_get_user(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.users.get_user.return_value = _make_v2_user("uid1")
        resp = client.get("/api/v2/users/uid1", headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == "uid1"

    def test_list_users(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.users.list_users.return_value = [_make_v2_user()]
        resp = client.get("/api/v2/users", headers=_admin_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_user(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.users.delete_user.return_value = None
        resp = client.delete("/api/v2/users/uid1", headers=_admin_headers())
        assert resp.status_code == 204

    def test_no_auth_returns_401(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/users")
        assert resp.status_code == 401


# ===================================================================
# Contacts
# ===================================================================


class TestV2Contacts:
    def test_create_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.contacts.create_contact.return_value = _make_v2_contact()
        resp = client.post(
            "/api/v2/contacts",
            json={"fullName": "Bob", "paymail": "bob@test.com"},
            headers=_user_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["fullName"] == "Bob"

    def test_list_contacts(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.contacts.list_for_user.return_value = [_make_v2_contact()]
        resp = client.get("/api/v2/contacts", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.contacts.get_contact.return_value = _make_v2_contact(42)
        resp = client.get("/api/v2/contacts/42", headers=_user_headers())
        assert resp.status_code == 200
        assert resp.json()["id"] == 42

    def test_update_contact_status(self, client_with_engine):
        client, engine = client_with_engine
        updated = _make_v2_contact(42)
        updated.status = "awaiting"
        engine.v2.contacts.update_status.return_value = updated
        resp = client.patch(
            "/api/v2/contacts/42/status",
            json={"status": "awaiting"},
            headers=_user_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting"

    def test_delete_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.contacts.delete_contact.return_value = None
        resp = client.delete("/api/v2/contacts/42", headers=_user_headers())
        assert resp.status_code == 204


# ===================================================================
# Transactions
# ===================================================================


class TestV2Transactions:
    def test_create_outline(self, client_with_engine):
        client, engine = client_with_engine
        from spv_wallet.engine.v2.transaction.outlines.models import (
            OutlineInput,
            OutlineOutput,
            TransactionOutline,
        )

        outline = TransactionOutline(
            user_id="uid1",
            inputs=[
                OutlineInput(tx_id="aa" * 32, vout=0, satoshis=10000, estimated_size=148),
            ],
            outputs=[
                OutlineOutput(to="1Address", satoshis=5000),
            ],
            fee=200,
            total_input=10000,
            total_output=5000,
            change=4800,
        )
        engine.v2.outlines.create.return_value = outline

        resp = client.post(
            "/api/v2/transactions/outlines",
            json={"outputs": [{"to": "1Address", "satoshis": 5000}]},
            headers=_user_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["fee"] == 200
        assert len(body["inputs"]) == 1

    def test_record_transaction(self, client_with_engine):
        client, engine = client_with_engine
        result = SimpleNamespace(
            tracked_tx=_make_v2_transaction(),
        )
        engine.v2.record.record_transaction_outline.return_value = result
        resp = client.post(
            "/api/v2/transactions/record",
            json={"rawHex": "0100000001..."},
            headers=_user_headers(),
        )
        assert resp.status_code == 201

    def test_list_transactions_no_auth(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/transactions")
        assert resp.status_code == 401


# ===================================================================
# Operations
# ===================================================================


class TestV2Operations:
    def test_list_operations(self, client_with_engine):
        client, _engine = client_with_engine

        # Operations endpoint likely calls repo directly
        resp = client.get("/api/v2/operations", headers=_user_headers())
        # Route exists
        assert resp.status_code != 404

    def test_operations_no_auth(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/operations")
        assert resp.status_code == 401


# ===================================================================
# Data
# ===================================================================


class TestV2Data:
    def test_data_no_auth(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/data")
        assert resp.status_code == 401

    def test_data_route_exists(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/data", headers=_user_headers())
        assert resp.status_code != 404


# ===================================================================
# Callbacks (no auth)
# ===================================================================


class TestV2Callbacks:
    def test_arc_callback(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.tx_sync.handle_arc_callback.return_value = None
        resp = client.post(
            "/api/v2/transactions/broadcast/callback",
            json={
                "txid": "aa" * 32,
                "txStatus": "MINED",
                "blockHeight": 800000,
                "blockHash": "bb" * 32,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        engine.v2.tx_sync.handle_arc_callback.assert_awaited_once()

    def test_arc_callback_no_auth_required(self, client_with_engine):
        """ARC callbacks don't require auth headers."""
        client, engine = client_with_engine
        engine.v2.tx_sync.handle_arc_callback.return_value = None
        resp = client.post(
            "/api/v2/transactions/broadcast/callback",
            json={"txid": "cc" * 32, "txStatus": "BROADCASTED"},
        )
        assert resp.status_code == 200


# ===================================================================
# Admin endpoints
# ===================================================================


class TestV2Admin:
    def test_admin_list_paymails(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.paymails.list_all.return_value = [_make_v2_paymail()]
        resp = client.get("/api/v2/admin/paymails", headers=_admin_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_admin_list_paymails_requires_admin(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/admin/paymails", headers=_user_headers())
        assert resp.status_code == 403

    def test_admin_delete_paymail(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.paymails.delete_paymail.return_value = None
        resp = client.delete("/api/v2/admin/paymails/1", headers=_admin_headers())
        assert resp.status_code == 204

    def test_admin_create_paymail_for_user(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.paymails.create_paymail.return_value = _make_v2_paymail()
        resp = client.post(
            "/api/v2/admin/users/uid1/paymails",
            json={"alias": "alice", "domain": "example.com"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["alias"] == "alice"

    def test_admin_list_user_paymails(self, client_with_engine):
        client, engine = client_with_engine
        engine.v2.paymails.list_for_user.return_value = [_make_v2_paymail()]
        resp = client.get(
            "/api/v2/admin/users/uid1/paymails",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_admin_webhooks_placeholder(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/admin/webhooks", headers=_admin_headers())
        assert resp.status_code == 200
        assert resp.json() == []

    def test_admin_webhooks_requires_admin(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v2/admin/webhooks", headers=_user_headers())
        assert resp.status_code == 403


# ===================================================================
# V2 routes are mounted at /api/v2
# ===================================================================


class TestV2Routing:
    def test_v2_prefix(self, client_with_engine):
        """All V2 routes are under /api/v2."""
        client, _ = client_with_engine
        # Verify a known V2 route responds (even if 401 without auth)
        resp = client.get("/api/v2/users")
        assert resp.status_code in (401, 403)

    def test_v1_still_works(self, client_with_engine):
        """V1 routes still function alongside V2."""
        client, _ = client_with_engine
        resp = client.get("/api/v1/xpub", headers=_user_headers())
        # Should not 404 — the route exists
        assert resp.status_code != 404
