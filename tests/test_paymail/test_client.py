"""Tests for PaymailClient — uses httpx mock transport."""

from __future__ import annotations

import httpx
import pytest

from spv_wallet.errors.definitions import (
    ErrPaymailCapabilitiesNotFound,
    ErrPaymailP2PFailed,
    ErrPaymailP2PSendFailed,
    ErrPaymailPKIFailed,
)
from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.paymail.client import _DEFAULT_PORT, PaymailClient
from spv_wallet.paymail.models import (
    BRFC_P2P_PAYMENT_DESTINATION,
    BRFC_P2P_SEND_TRANSACTION,
    BRFC_PKI,
    P2PTransaction,
    SanitizedPaymail,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CAPS_RESPONSE = {
    "bsvalias": "1.0",
    "capabilities": {
        BRFC_PKI: "https://example.com/v1/bsvalias/id/{alias}@{domain.tld}",
        BRFC_P2P_PAYMENT_DESTINATION: "https://example.com/v1/bsvalias/p2p-payment-destination/{alias}@{domain.tld}",
        BRFC_P2P_SEND_TRANSACTION: "https://example.com/v1/bsvalias/receive-transaction/{alias}@{domain.tld}",
    },
}

_PKI_RESPONSE = {
    "bsvalias": "1.0",
    "handle": "user@example.com",
    "pubkey": "02" + "ab" * 32,
}

_P2P_DEST_RESPONSE = {
    "outputs": [{"script": "76a914aabb88ac", "satoshis": 1000}],
    "reference": "ref-abc",
}

_P2P_SEND_RESPONSE = {
    "txid": "deadbeef" * 8,
    "note": "received",
}


def _mock_handler(request: httpx.Request) -> httpx.Response:
    """Route mock requests based on URL path."""
    path = request.url.path

    if path == "/.well-known/bsvalias":
        return httpx.Response(200, json=_CAPS_RESPONSE)

    if path.startswith("/v1/bsvalias/id/"):
        return httpx.Response(200, json=_PKI_RESPONSE)

    if "p2p-payment-destination" in path:
        return httpx.Response(200, json=_P2P_DEST_RESPONSE)

    if "receive-transaction" in path:
        return httpx.Response(200, json=_P2P_SEND_RESPONSE)

    return httpx.Response(404, json={"error": "not found"})


def _error_handler(_request: httpx.Request) -> httpx.Response:
    """Always return 500."""
    return httpx.Response(500, json={"error": "internal"})


async def _create_client_with_transport(
    handler=_mock_handler,
) -> PaymailClient:
    """Create a PaymailClient with a mock transport injected."""
    client = PaymailClient()
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    return client


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestPaymailClientLifecycle:
    async def test_not_connected_by_default(self):
        client = PaymailClient()
        assert client.is_connected is False

    async def test_connect_and_close(self):
        client = PaymailClient()
        await client.connect()
        assert client.is_connected is True
        await client.close()
        assert client.is_connected is False

    async def test_connect_idempotent(self):
        client = PaymailClient()
        await client.connect()
        first = client._client
        await client.connect()  # Should not create new client
        assert client._client is first
        await client.close()

    async def test_close_clears_cache(self):
        client = PaymailClient()
        client._capabilities_cache["test"] = (None, 0)  # type: ignore[assignment]
        await client.close()
        assert client._capabilities_cache == {}

    async def test_not_connected_raises(self):
        client = PaymailClient()
        with pytest.raises(SPVError):
            client._ensure_connected()


# ---------------------------------------------------------------------------
# SRV Lookup
# ---------------------------------------------------------------------------


class TestSRVLookup:
    async def test_fallback_to_default(self):
        """SRV lookup falls back to domain:443 when dnspython is unavailable or lookup fails."""
        client = PaymailClient()
        host, port = await client.resolve_srv("nonexistent.invalid.test")
        assert host == "nonexistent.invalid.test"
        assert port == _DEFAULT_PORT

    def test_sync_srv_fallback(self):
        """Synchronous SRV lookup falls back gracefully."""
        host, port = PaymailClient._srv_lookup_sync("nonexistent.invalid.test")
        assert host == "nonexistent.invalid.test"
        assert port == _DEFAULT_PORT


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    async def test_fetch_capabilities(self):
        client = await _create_client_with_transport()
        caps = await client.get_capabilities("example.com")
        assert caps.bsvalias == "1.0"
        assert caps.has_p2p is True
        assert BRFC_PKI in caps.capabilities
        await client.close()

    async def test_capabilities_cached(self):
        """Second call should use the cache."""
        call_count = 0

        def counting_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            if request.url.path == "/.well-known/bsvalias":
                call_count += 1
            return _mock_handler(request)

        client = await _create_client_with_transport(counting_handler)
        await client.get_capabilities("example.com")
        await client.get_capabilities("example.com")
        assert call_count == 1  # Only one HTTP call
        await client.close()

    async def test_capabilities_error(self):
        client = await _create_client_with_transport(_error_handler)
        with pytest.raises(type(ErrPaymailCapabilitiesNotFound)):
            await client.get_capabilities("example.com")
        await client.close()


# ---------------------------------------------------------------------------
# PKI
# ---------------------------------------------------------------------------


class TestPKI:
    async def test_get_pki(self):
        client = await _create_client_with_transport()
        pm = SanitizedPaymail.from_string("user@example.com")
        pki = await client.get_pki(pm)
        assert pki.pub_key == "02" + "ab" * 32
        assert pki.handle == "user@example.com"
        await client.close()

    async def test_pki_no_capability(self):
        """Should raise when PKI capability not advertised."""

        def no_pki_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(
                    200,
                    json={"bsvalias": "1.0", "capabilities": {}},
                )
            return httpx.Response(404)

        client = await _create_client_with_transport(no_pki_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        with pytest.raises(type(ErrPaymailPKIFailed)):
            await client.get_pki(pm)
        await client.close()

    async def test_pki_http_error(self):
        def pki_error_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(200, json=_CAPS_RESPONSE)
            return httpx.Response(500)

        client = await _create_client_with_transport(pki_error_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        with pytest.raises(type(ErrPaymailPKIFailed)):
            await client.get_pki(pm)
        await client.close()


# ---------------------------------------------------------------------------
# P2P Destinations
# ---------------------------------------------------------------------------


class TestP2PDestinations:
    async def test_get_destinations(self):
        client = await _create_client_with_transport()
        pm = SanitizedPaymail.from_string("user@example.com")
        dests = await client.get_p2p_destinations(pm, satoshis=1000)
        assert len(dests.outputs) == 1
        assert dests.reference == "ref-abc"
        assert dests.outputs[0].satoshis == 1000
        await client.close()

    async def test_destinations_no_capability(self):
        def no_p2p_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(
                    200, json={"bsvalias": "1.0", "capabilities": {}}
                )
            return httpx.Response(404)

        client = await _create_client_with_transport(no_p2p_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        with pytest.raises(type(ErrPaymailP2PFailed)):
            await client.get_p2p_destinations(pm, satoshis=1000)
        await client.close()

    async def test_destinations_http_error(self):
        def dest_error_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(200, json=_CAPS_RESPONSE)
            return httpx.Response(500)

        client = await _create_client_with_transport(dest_error_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        with pytest.raises(type(ErrPaymailP2PFailed)):
            await client.get_p2p_destinations(pm, satoshis=1000)
        await client.close()


# ---------------------------------------------------------------------------
# P2P Send
# ---------------------------------------------------------------------------


class TestP2PSend:
    async def test_send_transaction(self):
        client = await _create_client_with_transport()
        pm = SanitizedPaymail.from_string("user@example.com")
        tx = P2PTransaction(hex="deadbeef", reference="ref-abc")
        resp = await client.send_p2p_transaction(pm, tx)
        assert resp.txid == "deadbeef" * 8
        assert resp.note == "received"
        await client.close()

    async def test_send_no_capability(self):
        def no_send_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(
                    200, json={"bsvalias": "1.0", "capabilities": {}}
                )
            return httpx.Response(404)

        client = await _create_client_with_transport(no_send_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        tx = P2PTransaction(hex="ff", reference="ref")
        with pytest.raises(type(ErrPaymailP2PSendFailed)):
            await client.send_p2p_transaction(pm, tx)
        await client.close()

    async def test_send_http_error(self):
        def send_error_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/.well-known/bsvalias":
                return httpx.Response(200, json=_CAPS_RESPONSE)
            return httpx.Response(500)

        client = await _create_client_with_transport(send_error_handler)
        pm = SanitizedPaymail.from_string("user@example.com")
        tx = P2PTransaction(hex="ff", reference="ref")
        with pytest.raises(type(ErrPaymailP2PSendFailed)):
            await client.send_p2p_transaction(pm, tx)
        await client.close()


# ---------------------------------------------------------------------------
# URL Template Resolution
# ---------------------------------------------------------------------------


class TestURLTemplateResolution:
    def test_resolve_template(self):
        template = "https://example.com/v1/bsvalias/id/{alias}@{domain.tld}"
        pm = SanitizedPaymail.from_string("alice@test.com")
        url = PaymailClient._resolve_url_template(template, pm)
        assert url == "https://example.com/v1/bsvalias/id/alice@test.com"

    def test_resolve_template_no_placeholders(self):
        template = "https://example.com/v1/static-url"
        pm = SanitizedPaymail.from_string("user@domain.com")
        url = PaymailClient._resolve_url_template(template, pm)
        assert url == "https://example.com/v1/static-url"
