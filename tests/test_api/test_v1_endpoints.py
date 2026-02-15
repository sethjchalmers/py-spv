"""Tests for V1 REST API endpoints.

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

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ADMIN_XPUB = "xpub_test_admin"
USER_XPUB = "xpub_test_user"
USER_XPUB_ID = xpub_id(USER_XPUB)

NOW = datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Fixtures
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


def _make_destination(dest_id: str = "dest1"):
    return SimpleNamespace(
        id=dest_id,
        xpub_id=USER_XPUB_ID,
        locking_script="76a914...88ac",
        type="pubkeyhash",
        chain=0,
        num=0,
        address="1Address",
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_utxo(utxo_id: str = "utxo1"):
    return SimpleNamespace(
        id=utxo_id,
        xpub_id=USER_XPUB_ID,
        transaction_id="tx1",
        output_index=0,
        satoshis=5000,
        script_pub_key="76a914...88ac",
        type="pubkeyhash",
        destination_id="dest1",
        spending_tx_id="",
        draft_id="",
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_transaction(txid: str = "tx1"):
    return SimpleNamespace(
        id=txid,
        xpub_id=USER_XPUB_ID,
        hex_body="0100...",
        block_hash="",
        block_height=0,
        merkle_path="",
        total_value=5000,
        fee=200,
        status="created",
        direction="outgoing",
        num_inputs=1,
        num_outputs=1,
        draft_id="draft1",
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_draft(draft_id: str = "draft1"):
    return SimpleNamespace(
        id=draft_id,
        xpub_id=USER_XPUB_ID,
        config={"outputs": []},
        status="draft",
        final_tx_id=None,
        hex_body="",
        reference_id="ref1",
        total_value=5000,
        fee=200,
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_contact(contact_id: str = "contact1"):
    return SimpleNamespace(
        id=contact_id,
        xpub_id=USER_XPUB_ID,
        full_name="Test User",
        paymail="user@example.com",
        pub_key="",
        status="unconfirmed",
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _make_access_key(key_id: str = "ak1"):
    return SimpleNamespace(
        id=key_id,
        xpub_id=USER_XPUB_ID,
        key="02abcdef...",
        metadata_={},
        created_at=NOW,
        deleted_at=None,
    )


def _make_paymail(pm_id: str = "pm1"):
    return SimpleNamespace(
        id=pm_id,
        xpub_id=USER_XPUB_ID,
        alias="user",
        domain="example.com",
        public_name="Test User",
        avatar="",
        metadata_={},
        created_at=NOW,
        updated_at=NOW,
    )


def _mock_engine():
    """Create a comprehensive mock engine."""
    engine = MagicMock()
    engine.config = MagicMock()
    engine.config.admin_xpub = ADMIN_XPUB
    engine.config.paymail = MagicMock()
    engine.config.paymail.default_domain = "example.com"

    engine.xpub_service = AsyncMock()
    engine.destination_service = AsyncMock()
    engine.utxo_service = AsyncMock()
    engine.access_key_service = AsyncMock()
    engine.transaction_service = AsyncMock()
    engine.contact_service = AsyncMock()
    engine.paymail_service = AsyncMock()
    engine.health_check = AsyncMock(
        return_value={"engine": "ok", "datastore": "ok", "cache": "ok", "chain": "ok"}
    )

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


def _user_headers(xpub: str = USER_XPUB) -> dict[str, str]:
    return {"x-auth-xpub": xpub}


def _admin_headers() -> dict[str, str]:
    return {"x-auth-xpub": ADMIN_XPUB}


# ===================================================================
# Health + OpenAPI
# ===================================================================


class TestBaseRoutes:
    def test_health(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_openapi(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["title"] == "py-spv"


# ===================================================================
# Auth / Unauthorized
# ===================================================================


class TestAuthErrors:
    def test_no_auth_header_returns_401(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v1/xpub")
        assert resp.status_code == 401
        assert resp.json()["code"] == "unauthorized"

    def test_unknown_xpub_returns_401(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.get_xpub_by_id.return_value = None
        resp = client.get("/api/v1/xpub", headers=_user_headers("xpub_unknown"))
        assert resp.status_code == 401

    def test_non_admin_on_admin_route_returns_403(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.get_xpub_by_id.return_value = _make_xpub_record()
        resp = client.get(
            "/api/v1/admin/health",
            headers=_user_headers(),
        )
        assert resp.status_code == 403


# ===================================================================
# User Endpoints
# ===================================================================


class TestUserXPub:
    def test_get_xpub(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.get_xpub_by_id.return_value = _make_xpub_record()

        resp = client.get("/api/v1/xpub", headers=_user_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_balance"] == 1000


class TestUserDestinations:
    def test_list_destinations(self, client_with_engine):
        client, engine = client_with_engine
        engine.destination_service.get_destinations_by_xpub.return_value = [
            _make_destination("d1"),
            _make_destination("d2"),
        ]
        resp = client.get("/api/v1/destination", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_create_destination(self, client_with_engine):
        client, engine = client_with_engine
        engine.destination_service.new_destination.return_value = _make_destination()

        resp = client.post(
            "/api/v1/destination",
            headers=_user_headers(),
            json={"metadata": {"label": "test"}},
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "dest1"

    def test_get_destination_not_found(self, client_with_engine):
        client, engine = client_with_engine
        engine.destination_service.get_destination.return_value = None

        resp = client.get(
            "/api/v1/destination/nonexistent",
            headers=_user_headers(),
        )
        assert resp.status_code == 404


class TestUserBalance:
    def test_get_balance(self, client_with_engine):
        client, engine = client_with_engine
        engine.utxo_service.get_balance.return_value = 50000

        resp = client.get("/api/v1/utxo/balance", headers=_user_headers())
        assert resp.status_code == 200
        assert resp.json()["satoshis"] == 50000


# ===================================================================
# Transaction Endpoints
# ===================================================================


class TestTransactions:
    def test_create_draft(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.new_transaction.return_value = _make_draft()

        resp = client.post(
            "/api/v1/transaction",
            headers=_user_headers(),
            json={"outputs": [{"to": "addr1", "satoshis": 1000}]},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    def test_record_transaction(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.record_transaction.return_value = _make_transaction()

        resp = client.post(
            "/api/v1/transaction/record",
            headers=_user_headers(),
            json={"hex": "0100..."},
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "tx1"

    def test_list_transactions(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.get_transactions.return_value = [
            _make_transaction("tx1"),
            _make_transaction("tx2"),
        ]

        resp = client.get("/api/v1/transaction", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_transaction(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.get_transaction.return_value = _make_transaction()

        resp = client.get("/api/v1/transaction/tx1", headers=_user_headers())
        assert resp.status_code == 200
        assert resp.json()["total_value"] == 5000

    def test_get_transaction_wrong_user(self, client_with_engine):
        client, engine = client_with_engine
        tx = _make_transaction()
        tx.xpub_id = "other_user"
        engine.transaction_service.get_transaction.return_value = tx

        resp = client.get("/api/v1/transaction/tx1", headers=_user_headers())
        assert resp.status_code == 404


class TestArcCallback:
    def test_arc_callback(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.handle_arc_callback.return_value = None

        resp = client.post(
            "/api/v1/transaction/broadcast/callback",
            json={
                "txID": "abc123",
                "txStatus": "SEEN_ON_NETWORK",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ===================================================================
# UTXO Endpoints
# ===================================================================


class TestUTXOs:
    def test_list_utxos(self, client_with_engine):
        client, engine = client_with_engine
        engine.utxo_service.get_utxos.return_value = [_make_utxo()]

        resp = client.get("/api/v1/utxo", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["satoshis"] == 5000

    def test_count_utxos(self, client_with_engine):
        client, engine = client_with_engine
        engine.utxo_service.count_utxos.return_value = 42

        resp = client.get("/api/v1/utxo/count", headers=_user_headers())
        assert resp.status_code == 200
        assert resp.json()["count"] == 42

    def test_get_utxo_not_found(self, client_with_engine):
        client, engine = client_with_engine
        engine.utxo_service.get_utxo.return_value = None

        resp = client.get("/api/v1/utxo/missing", headers=_user_headers())
        assert resp.status_code == 404


# ===================================================================
# Contact Endpoints
# ===================================================================


class TestContacts:
    def test_create_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.contact_service.create_contact.return_value = _make_contact()

        resp = client.post(
            "/api/v1/contact",
            headers=_user_headers(),
            json={"paymail": "user@example.com", "full_name": "Test User"},
        )
        assert resp.status_code == 201
        assert resp.json()["paymail"] == "user@example.com"

    def test_list_contacts(self, client_with_engine):
        client, engine = client_with_engine
        engine.contact_service.search_contacts.return_value = [
            _make_contact("c1"),
            _make_contact("c2"),
        ]

        resp = client.get("/api/v1/contact", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.contact_service.get_contact.return_value = _make_contact()

        resp = client.get(
            "/api/v1/contact/contact1",
            headers=_user_headers(),
        )
        assert resp.status_code == 200

    def test_update_contact_status(self, client_with_engine):
        client, engine = client_with_engine
        engine.contact_service.get_contact.return_value = _make_contact()
        updated = _make_contact()
        updated.status = "awaiting"
        engine.contact_service.update_status.return_value = updated

        resp = client.patch(
            "/api/v1/contact/contact1/status",
            headers=_user_headers(),
            json={"status": "awaiting"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting"

    def test_delete_contact(self, client_with_engine):
        client, engine = client_with_engine
        engine.contact_service.get_contact.return_value = _make_contact()
        engine.contact_service.delete_contact.return_value = None

        resp = client.delete(
            "/api/v1/contact/contact1",
            headers=_user_headers(),
        )
        assert resp.status_code == 204

    def test_get_contact_wrong_user(self, client_with_engine):
        client, engine = client_with_engine
        c = _make_contact()
        c.xpub_id = "other_user"
        engine.contact_service.get_contact.return_value = c

        resp = client.get(
            "/api/v1/contact/contact1",
            headers=_user_headers(),
        )
        assert resp.status_code == 404


# ===================================================================
# Access Key Endpoints
# ===================================================================


class TestAccessKeys:
    def test_create_access_key(self, client_with_engine):
        client, engine = client_with_engine
        ak = _make_access_key()
        engine.access_key_service.new_access_key.return_value = (
            ak,
            "private_key_hex_value",
        )

        resp = client.post(
            "/api/v1/access-key",
            headers=_user_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "ak1"
        assert data["private_key"] == "private_key_hex_value"

    def test_list_access_keys(self, client_with_engine):
        client, engine = client_with_engine
        engine.access_key_service.get_access_keys_by_xpub.return_value = [
            _make_access_key("ak1"),
            _make_access_key("ak2"),
        ]

        resp = client.get("/api/v1/access-key", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_count_access_keys(self, client_with_engine):
        client, engine = client_with_engine
        engine.access_key_service.count_access_keys.return_value = 5

        resp = client.get("/api/v1/access-key/count", headers=_user_headers())
        assert resp.status_code == 200
        assert resp.json()["count"] == 5

    def test_get_access_key(self, client_with_engine):
        client, engine = client_with_engine
        engine.access_key_service.get_access_key.return_value = _make_access_key()

        resp = client.get(
            "/api/v1/access-key/ak1",
            headers=_user_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "ak1"

    def test_revoke_access_key(self, client_with_engine):
        client, engine = client_with_engine
        engine.access_key_service.get_access_key.return_value = _make_access_key()
        engine.access_key_service.revoke_access_key.return_value = None

        resp = client.delete(
            "/api/v1/access-key/ak1",
            headers=_user_headers(),
        )
        assert resp.status_code == 204


# ===================================================================
# Paymail Endpoints
# ===================================================================


class TestPaymails:
    def test_create_paymail(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.create_paymail.return_value = _make_paymail()

        resp = client.post(
            "/api/v1/paymail",
            headers=_user_headers(),
            json={"address": "user@example.com", "public_name": "Test User"},
        )
        assert resp.status_code == 201
        assert resp.json()["alias"] == "user"

    def test_list_paymails(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.get_paymails_by_xpub.return_value = [_make_paymail()]

        resp = client.get("/api/v1/paymail", headers=_user_headers())
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_paymail(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.get_paymail_by_id.return_value = _make_paymail()

        resp = client.get("/api/v1/paymail/pm1", headers=_user_headers())
        assert resp.status_code == 200

    def test_delete_paymail(self, client_with_engine):
        client, engine = client_with_engine
        pm = _make_paymail()
        engine.paymail_service.get_paymail_by_alias.return_value = pm
        engine.paymail_service.delete_paymail.return_value = None

        resp = client.delete(
            "/api/v1/paymail/user@example.com",
            headers=_user_headers(),
        )
        assert resp.status_code == 204

    def test_delete_paymail_wrong_user(self, client_with_engine):
        client, engine = client_with_engine
        pm = _make_paymail()
        pm.xpub_id = "other_user"
        engine.paymail_service.get_paymail_by_alias.return_value = pm

        resp = client.delete(
            "/api/v1/paymail/user@example.com",
            headers=_user_headers(),
        )
        assert resp.status_code == 404


# ===================================================================
# Shared Config
# ===================================================================


class TestSharedConfig:
    def test_get_shared_config(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get(
            "/api/v1/shared-config",
            headers=_user_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "example.com" in data["paymail_domains"]


# ===================================================================
# Merkle Roots (placeholder)
# ===================================================================


class TestMerkleRoots:
    def test_get_merkle_roots(self, client_with_engine):
        client, _ = client_with_engine
        resp = client.get("/api/v1/merkleroots")
        assert resp.status_code == 200


# ===================================================================
# Admin Endpoints
# ===================================================================


class TestAdminXPub:
    def test_register_xpub(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.new_xpub.return_value = _make_xpub_record()

        resp = client.post(
            "/api/v1/admin/xpub",
            headers=_admin_headers(),
            json={"xpub": USER_XPUB},
        )
        assert resp.status_code == 201

    def test_get_xpub_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.get_xpub_by_id.return_value = _make_xpub_record()

        resp = client.get(
            f"/api/v1/admin/xpub/{USER_XPUB_ID}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

    def test_update_xpub_metadata(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.update_metadata.return_value = _make_xpub_record()

        resp = client.patch(
            f"/api/v1/admin/xpub/{USER_XPUB_ID}/metadata",
            headers=_admin_headers(),
            json={"metadata": {"key": "value"}},
        )
        assert resp.status_code == 200

    def test_delete_xpub(self, client_with_engine):
        client, engine = client_with_engine
        engine.xpub_service.delete_xpub.return_value = None

        resp = client.delete(
            f"/api/v1/admin/xpub/{USER_XPUB_ID}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 204


class TestAdminTransactions:
    def test_list_transactions_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.get_transactions.return_value = [_make_transaction()]

        resp = client.get(
            "/api/v1/admin/transaction",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_transaction_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.transaction_service.get_transaction.return_value = _make_transaction()

        resp = client.get(
            "/api/v1/admin/transaction/tx1",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200


class TestAdminUTXOs:
    def test_list_utxos_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.utxo_service.get_utxos.return_value = [_make_utxo()]

        resp = client.get(
            "/api/v1/admin/utxo",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200


class TestAdminPaymails:
    def test_create_paymail_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.create_paymail.return_value = _make_paymail()

        resp = client.post(
            "/api/v1/admin/paymail",
            headers=_admin_headers(),
            json={"address": "admin@example.com"},
        )
        assert resp.status_code == 201

    def test_list_paymails_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.search_paymails.return_value = [_make_paymail()]

        resp = client.get(
            "/api/v1/admin/paymail",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200

    def test_delete_paymail_admin(self, client_with_engine):
        client, engine = client_with_engine
        engine.paymail_service.delete_paymail.return_value = None

        resp = client.delete(
            "/api/v1/admin/paymail/user@example.com",
            headers=_admin_headers(),
        )
        assert resp.status_code == 204


class TestAdminHealth:
    def test_admin_health(self, client_with_engine):
        client, _ = client_with_engine

        resp = client.get(
            "/api/v1/admin/health",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "ok"


# ===================================================================
# Error Handler
# ===================================================================


class TestErrorHandler:
    def test_spv_error_response_format(self, client_with_engine):
        """SPVError should produce {"code": "...", "message": "..."}."""
        client, engine = client_with_engine
        engine.xpub_service.get_xpub_by_id.return_value = None

        resp = client.get("/api/v1/xpub", headers=_user_headers("xpub_unknown"))
        assert resp.status_code == 401
        data = resp.json()
        assert "code" in data
        assert "message" in data
