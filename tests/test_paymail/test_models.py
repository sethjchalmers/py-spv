"""Tests for paymail protocol data models."""

from __future__ import annotations

import pytest

from spv_wallet.paymail.models import (
    BRFC_BEEF,
    BRFC_P2P_PAYMENT_DESTINATION,
    BRFC_P2P_SEND_TRANSACTION,
    BRFC_PIKE_INVITE,
    BRFC_PKI,
    Capabilities,
    P2PDestinationsResponse,
    P2PSenderMetadata,
    P2PSendResponse,
    P2PTransaction,
    PaymentDestination,
    PKIResponse,
    SanitizedPaymail,
)

# ---------------------------------------------------------------------------
# SanitizedPaymail
# ---------------------------------------------------------------------------


class TestSanitizedPaymail:
    def test_valid_address(self):
        pm = SanitizedPaymail.from_string("User@Example.COM")
        assert pm.alias == "user"
        assert pm.domain == "example.com"
        assert pm.address == "user@example.com"

    def test_whitespace_stripped(self):
        pm = SanitizedPaymail.from_string("  alice@test.com  ")
        assert pm.alias == "alice"
        assert pm.domain == "test.com"
        assert pm.address == "alice@test.com"

    def test_complex_alias(self):
        pm = SanitizedPaymail.from_string("user.name+tag@sub.domain.com")
        assert pm.alias == "user.name+tag"
        assert pm.domain == "sub.domain.com"

    def test_invalid_no_at(self):
        with pytest.raises(ValueError, match="invalid paymail"):
            SanitizedPaymail.from_string("not-an-address")

    def test_invalid_empty_alias(self):
        with pytest.raises(ValueError, match="invalid paymail"):
            SanitizedPaymail.from_string("@domain.com")

    def test_invalid_empty_domain(self):
        with pytest.raises(ValueError, match="invalid paymail"):
            SanitizedPaymail.from_string("user@")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError, match="invalid paymail"):
            SanitizedPaymail.from_string("")

    def test_frozen(self):
        pm = SanitizedPaymail.from_string("user@example.com")
        with pytest.raises(AttributeError):
            pm.alias = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_from_dict(self):
        data = {
            "bsvalias": "1.0",
            "capabilities": {
                BRFC_PKI: "https://example.com/pki/{alias}@{domain.tld}",
                BRFC_P2P_PAYMENT_DESTINATION: "https://example.com/p2p/{alias}@{domain.tld}",
            },
        }
        caps = Capabilities.from_dict(data)
        assert caps.bsvalias == "1.0"
        assert caps.has_p2p is True
        assert caps.has_pike is False
        assert caps.has_beef is False

    def test_from_dict_empty(self):
        caps = Capabilities.from_dict({})
        assert caps.bsvalias == "1.0"
        assert caps.capabilities == {}
        assert caps.has_p2p is False

    def test_get_url(self):
        caps = Capabilities(capabilities={BRFC_PKI: "https://x.com/pki/{alias}@{domain.tld}"})
        assert caps.get_url(BRFC_PKI) == "https://x.com/pki/{alias}@{domain.tld}"
        assert caps.get_url("nonexistent") is None

    def test_has_p2p(self):
        caps = Capabilities(capabilities={BRFC_P2P_PAYMENT_DESTINATION: "url"})
        assert caps.has_p2p is True

    def test_has_pike(self):
        caps = Capabilities(capabilities={BRFC_PIKE_INVITE: "url"})
        assert caps.has_pike is True

    def test_has_beef(self):
        caps = Capabilities(capabilities={BRFC_BEEF: "url"})
        assert caps.has_beef is True

    def test_full_capabilities(self):
        caps = Capabilities(
            capabilities={
                BRFC_PKI: "pki_url",
                BRFC_P2P_PAYMENT_DESTINATION: "p2p_url",
                BRFC_P2P_SEND_TRANSACTION: "send_url",
                BRFC_BEEF: "beef_url",
                BRFC_PIKE_INVITE: "pike_url",
            }
        )
        assert caps.has_p2p is True
        assert caps.has_pike is True
        assert caps.has_beef is True


# ---------------------------------------------------------------------------
# PKIResponse
# ---------------------------------------------------------------------------


class TestPKIResponse:
    def test_from_dict(self):
        data = {
            "bsvalias": "1.0",
            "handle": "user@example.com",
            "pubkey": "02" + "ab" * 32,
        }
        pki = PKIResponse.from_dict(data)
        assert pki.bsvalias == "1.0"
        assert pki.handle == "user@example.com"
        assert pki.pub_key == "02" + "ab" * 32

    def test_from_dict_defaults(self):
        pki = PKIResponse.from_dict({})
        assert pki.bsvalias == "1.0"
        assert pki.handle == ""
        assert pki.pub_key == ""


# ---------------------------------------------------------------------------
# PaymentDestination
# ---------------------------------------------------------------------------


class TestPaymentDestination:
    def test_from_dict(self):
        data = {"script": "76a914" + "00" * 20 + "88ac", "satoshis": 1000}
        dest = PaymentDestination.from_dict(data)
        assert dest.satoshis == 1000
        assert dest.script.startswith("76a914")

    def test_from_dict_defaults(self):
        dest = PaymentDestination.from_dict({})
        assert dest.script == ""
        assert dest.satoshis == 0


# ---------------------------------------------------------------------------
# P2PDestinationsResponse
# ---------------------------------------------------------------------------


class TestP2PDestinationsResponse:
    def test_from_dict(self):
        data = {
            "outputs": [
                {"script": "aabb", "satoshis": 500},
                {"script": "ccdd", "satoshis": 500},
            ],
            "reference": "ref-123",
        }
        resp = P2PDestinationsResponse.from_dict(data)
        assert len(resp.outputs) == 2
        assert resp.reference == "ref-123"
        assert resp.outputs[0].script == "aabb"
        assert resp.outputs[1].satoshis == 500

    def test_from_dict_empty(self):
        resp = P2PDestinationsResponse.from_dict({})
        assert resp.outputs == []
        assert resp.reference == ""


# ---------------------------------------------------------------------------
# P2PTransaction / P2PSenderMetadata
# ---------------------------------------------------------------------------


class TestP2PTransaction:
    def test_to_dict_hex(self):
        tx = P2PTransaction(hex="deadbeef", reference="ref-1")
        d = tx.to_dict()
        assert d["hex"] == "deadbeef"
        assert d["reference"] == "ref-1"
        assert "beef" not in d

    def test_to_dict_beef(self):
        tx = P2PTransaction(beef="beef_data", reference="ref-2")
        d = tx.to_dict()
        assert d["beef"] == "beef_data"
        assert d["reference"] == "ref-2"
        assert "hex" not in d

    def test_to_dict_with_metadata(self):
        meta = P2PSenderMetadata(
            sender="alice@example.com",
            pub_key="02aabb",
            signature="sig",
            note="payment",
        )
        tx = P2PTransaction(hex="ff", reference="ref-3", metadata=meta)
        d = tx.to_dict()
        assert d["metadata"]["sender"] == "alice@example.com"
        assert d["metadata"]["pubkey"] == "02aabb"
        assert d["metadata"]["signature"] == "sig"
        assert d["metadata"]["note"] == "payment"

    def test_to_dict_metadata_sparse(self):
        meta = P2PSenderMetadata(sender="bob@x.com")
        d = meta.to_dict()
        assert d == {"sender": "bob@x.com"}
        assert "pubkey" not in d
        assert "signature" not in d


# ---------------------------------------------------------------------------
# P2PSendResponse
# ---------------------------------------------------------------------------


class TestP2PSendResponse:
    def test_from_dict(self):
        resp = P2PSendResponse.from_dict({"txid": "abc123", "note": "thanks"})
        assert resp.txid == "abc123"
        assert resp.note == "thanks"

    def test_from_dict_defaults(self):
        resp = P2PSendResponse.from_dict({})
        assert resp.txid == ""
        assert resp.note == ""
