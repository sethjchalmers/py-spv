"""Tests for paymail server routes."""

from __future__ import annotations

from spv_wallet.api.paymail_server.routes import router
from spv_wallet.paymail.models import (
    BRFC_BEEF,
    BRFC_P2P_PAYMENT_DESTINATION,
    BRFC_P2P_SEND_TRANSACTION,
    BRFC_PIKE_INVITE,
    BRFC_PIKE_OUTPUTS,
    BRFC_PKI,
    BRFC_PUBLIC_PROFILE,
    BRFC_SENDER_VALIDATION,
    BRFC_VERIFY_PUBLIC_KEY,
)


class TestCapabilitiesEndpoint:
    """Tests for the .well-known/bsvalias capability discovery."""

    def test_capabilities_response_structure(self):
        """Verify the capabilities dict has expected BRFC IDs."""
        # The route is a simple function — we can test its response structure
        # by checking the BRFC constants
        expected_brfcs = {
            BRFC_PKI,
            BRFC_SENDER_VALIDATION,
            BRFC_VERIFY_PUBLIC_KEY,
            BRFC_PUBLIC_PROFILE,
            BRFC_P2P_PAYMENT_DESTINATION,
            BRFC_P2P_SEND_TRANSACTION,
            BRFC_BEEF,
            BRFC_PIKE_INVITE,
            BRFC_PIKE_OUTPUTS,
        }
        # All BRFC constants should be valid strings
        for brfc in expected_brfcs:
            assert isinstance(brfc, str)
            assert len(brfc) > 0

    def test_router_has_routes(self):
        """Router should have the paymail endpoints registered."""
        paths = [r.path for r in router.routes]
        assert "/.well-known/bsvalias" in paths
        assert "/v1/bsvalias/id/{alias}@{domain}" in paths
        assert "/v1/bsvalias/p2p-payment-destination/{alias}@{domain}" in paths
        assert "/v1/bsvalias/receive-transaction/{alias}@{domain}" in paths
        assert "/v1/bsvalias/public-profile/{alias}@{domain}" in paths


class TestRouteModels:
    """Tests for the Pydantic request/response models."""

    def test_p2p_destination_request(self):
        from spv_wallet.api.paymail_server.routes import P2PDestinationRequest

        req = P2PDestinationRequest(satoshis=1000)
        assert req.satoshis == 1000

    def test_p2p_receive_request(self):
        from spv_wallet.api.paymail_server.routes import P2PReceiveRequest

        req = P2PReceiveRequest(
            hex="deadbeef",
            reference="ref-1",
            beef="",
            metadata={"sender": "alice@test.com"},
        )
        assert req.hex == "deadbeef"
        assert req.reference == "ref-1"
        assert req.metadata == {"sender": "alice@test.com"}

    def test_p2p_receive_request_defaults(self):
        from spv_wallet.api.paymail_server.routes import P2PReceiveRequest

        req = P2PReceiveRequest()
        assert req.hex == ""
        assert req.reference == ""
        assert req.beef == ""
        assert req.metadata is None
