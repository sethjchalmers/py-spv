"""Tests for PIKE protocol — contact exchange."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from spv_wallet.engine.models.contact import Contact
from spv_wallet.engine.models.paymail_address import PaymailAddress
from spv_wallet.engine.services.contact_service import (
    CONTACT_STATUS_AWAITING,
    CONTACT_STATUS_UNCONFIRMED,
)
from spv_wallet.errors.definitions import ErrPaymailNotFound
from spv_wallet.paymail.pike import (
    PikeContactInvite,
    PikeContactService,
    PikeOutputsRequest,
    PikePaymentService,
)

# ---------------------------------------------------------------------------
# PikeContactInvite model
# ---------------------------------------------------------------------------


class TestPikeContactInvite:
    def test_from_dict(self):
        data = {
            "fullName": "Alice",
            "paymail": "alice@example.com",
            "pubkey": "02aabb",
        }
        invite = PikeContactInvite.from_dict(data)
        assert invite.full_name == "Alice"
        assert invite.paymail == "alice@example.com"
        assert invite.pub_key == "02aabb"

    def test_from_dict_snake_case(self):
        data = {
            "full_name": "Bob",
            "paymail": "bob@test.com",
            "pub_key": "03ccdd",
        }
        invite = PikeContactInvite.from_dict(data)
        assert invite.full_name == "Bob"
        assert invite.pub_key == "03ccdd"

    def test_to_dict(self):
        invite = PikeContactInvite(
            full_name="Alice",
            paymail="alice@example.com",
            pub_key="02aabb",
        )
        d = invite.to_dict()
        assert d["fullName"] == "Alice"
        assert d["paymail"] == "alice@example.com"
        assert d["pubkey"] == "02aabb"


# ---------------------------------------------------------------------------
# PikeOutputsRequest model
# ---------------------------------------------------------------------------


class TestPikeOutputsRequest:
    def test_from_dict(self):
        data = {"senderPaymail": "sender@test.com", "satoshis": 5000}
        req = PikeOutputsRequest.from_dict(data)
        assert req.sender_paymail == "sender@test.com"
        assert req.satoshis == 5000

    def test_from_dict_defaults(self):
        req = PikeOutputsRequest.from_dict({})
        assert req.sender_paymail == ""
        assert req.satoshis == 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_engine_for_pike():
    """Create a mock engine suitable for PIKE tests."""
    engine = MagicMock()

    # Paymail service
    paymail = PaymailAddress(
        id="pm_id",
        xpub_id="xpub_1",
        alias="recipient",
        domain="example.com",
        public_name="Recipient User",
        avatar="",
    )
    engine.paymail_service = MagicMock()
    engine.paymail_service.get_paymail_by_alias = AsyncMock(return_value=paymail)

    # Contact service
    contact = Contact(
        id="contact_1",
        xpub_id="xpub_1",
        paymail="sender@remote.com",
        full_name="Sender",
        pub_key="02aabb",
        status=CONTACT_STATUS_UNCONFIRMED,
    )
    engine.contact_service = MagicMock()
    engine.contact_service.upsert_contact = AsyncMock(return_value=contact)
    engine.contact_service.create_contact = AsyncMock(return_value=contact)

    return engine


# ---------------------------------------------------------------------------
# PikeContactService
# ---------------------------------------------------------------------------


class TestPikeContactService:
    async def test_handle_invite_success(self):
        engine = _mock_engine_for_pike()
        svc = PikeContactService(engine)
        invite = PikeContactInvite(
            full_name="Sender",
            paymail="sender@remote.com",
            pub_key="02aabb",
        )
        contact = await svc.handle_invite("recipient", "example.com", invite)
        assert contact.paymail == "sender@remote.com"
        assert contact.status == CONTACT_STATUS_UNCONFIRMED

        # Verify upsert was called with correct args
        engine.contact_service.upsert_contact.assert_called_once_with(
            xpub_id="xpub_1",
            paymail="sender@remote.com",
            full_name="Sender",
            pub_key="02aabb",
            status=CONTACT_STATUS_UNCONFIRMED,
        )

    async def test_handle_invite_paymail_not_found(self):
        engine = _mock_engine_for_pike()
        engine.paymail_service.get_paymail_by_alias = AsyncMock(return_value=None)
        svc = PikeContactService(engine)
        invite = PikeContactInvite(
            full_name="Sender",
            paymail="sender@remote.com",
            pub_key="02aabb",
        )
        with pytest.raises(type(ErrPaymailNotFound)):
            await svc.handle_invite("nobody", "example.com", invite)

    async def test_handle_invite_invalid_sender_paymail(self):
        engine = _mock_engine_for_pike()
        svc = PikeContactService(engine)
        invite = PikeContactInvite(
            full_name="Bad",
            paymail="not-a-valid-paymail",
            pub_key="02aabb",
        )
        with pytest.raises(ValueError, match="invalid paymail"):
            await svc.handle_invite("recipient", "example.com", invite)


class TestPikeContactServiceSendInvite:
    async def test_send_invite_success(self):
        engine = _mock_engine_for_pike()

        # Mock paymail client
        mock_client = MagicMock()
        mock_caps = MagicMock()
        mock_caps.get_url = MagicMock(
            return_value="https://remote.com/pike/invite/{alias}@{domain.tld}"
        )
        mock_client.get_capabilities = AsyncMock(return_value=mock_caps)
        mock_client._resolve_url_template = MagicMock(
            return_value="https://remote.com/pike/invite/target@remote.com"
        )
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_client._ensure_connected = MagicMock(return_value=mock_http)
        engine.paymail_client = mock_client

        # Update mock to return awaiting contact
        awaiting_contact = Contact(
            id="contact_2",
            xpub_id="xpub_1",
            paymail="target@remote.com",
            full_name="",
            pub_key="",
            status=CONTACT_STATUS_AWAITING,
        )
        engine.contact_service.upsert_contact = AsyncMock(return_value=awaiting_contact)

        svc = PikeContactService(engine)
        contact = await svc.send_invite(
            "recipient", "example.com", "target@remote.com", pub_key="02aabb"
        )
        assert contact.status == CONTACT_STATUS_AWAITING

    async def test_send_invite_sender_not_found(self):
        engine = _mock_engine_for_pike()
        engine.paymail_service.get_paymail_by_alias = AsyncMock(return_value=None)
        svc = PikeContactService(engine)
        with pytest.raises(type(ErrPaymailNotFound)):
            await svc.send_invite("nobody", "example.com", "target@remote.com")


# ---------------------------------------------------------------------------
# PikePaymentService
# ---------------------------------------------------------------------------


class TestPikePaymentService:
    async def test_get_outputs_delegates(self):
        engine = _mock_engine_for_pike()

        # Mock the xpub and destination services used by provider
        xpub_mock = MagicMock()
        xpub_mock.id = "xpub_1"
        xpub_mock.metadata_ = {"raw_xpub": "xpub_fake_key"}
        engine.xpub_service = MagicMock()
        engine.xpub_service.get_xpub_by_id = AsyncMock(return_value=xpub_mock)

        dest_mock = MagicMock()
        dest_mock.locking_script = "76a914aabb88ac"
        dest_mock.id = "dest_1"
        engine.destination_service = MagicMock()
        engine.destination_service.new_destination = AsyncMock(return_value=dest_mock)

        svc = PikePaymentService(engine)
        req = PikeOutputsRequest(sender_paymail="sender@test.com", satoshis=1000)
        result = await svc.get_outputs("recipient", "example.com", req)

        assert "outputs" in result
        assert "reference" in result
