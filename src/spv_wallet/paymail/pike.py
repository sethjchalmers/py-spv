"""PIKE protocol — contact exchange between paymail providers.

Implements the PIKE (Paymail Inter-Key Exchange) protocol for
establishing trusted contacts between paymail users:

- PikeContactService: Handle incoming contact invitations
- PikePaymentService: Provide PIKE-specific payment outputs
- PIKE invite/response flow

Mirrors the Go ``engine/pike.go`` and PIKE service providers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from spv_wallet.engine.services.contact_service import (
    CONTACT_STATUS_AWAITING,
    CONTACT_STATUS_UNCONFIRMED,
)
from spv_wallet.errors.definitions import ErrPaymailNotFound
from spv_wallet.paymail.models import SanitizedPaymail

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine
    from spv_wallet.engine.models.contact import Contact

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PikeContactInvite:
    """An incoming PIKE contact invitation.

    Attributes:
        full_name: The sender's display name.
        paymail: The sender's paymail address.
        pub_key: The sender's public key hex.
    """

    full_name: str
    paymail: str
    pub_key: str

    @classmethod
    def from_dict(cls, data: dict) -> PikeContactInvite:
        """Parse from JSON dict."""
        return cls(
            full_name=data.get("fullName", data.get("full_name", "")),
            paymail=data.get("paymail", ""),
            pub_key=data.get("pubkey", data.get("pub_key", "")),
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON payload."""
        return {
            "fullName": self.full_name,
            "paymail": self.paymail,
            "pubkey": self.pub_key,
        }


@dataclass(frozen=True, slots=True)
class PikeOutputsRequest:
    """Request for PIKE payment outputs.

    Attributes:
        sender_paymail: The requesting sender's paymail.
        satoshis: Amount requested.
    """

    sender_paymail: str
    satoshis: int

    @classmethod
    def from_dict(cls, data: dict) -> PikeOutputsRequest:
        """Parse from JSON dict."""
        return cls(
            sender_paymail=data.get("senderPaymail", ""),
            satoshis=data.get("satoshis", 0),
        )


class PikeContactService:
    """Handle incoming PIKE contact invitations.

    When a remote paymail server sends a contact invite,
    this service creates or updates the contact record
    on the receiving side.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    async def handle_invite(
        self,
        recipient_alias: str,
        recipient_domain: str,
        invite: PikeContactInvite,
    ) -> Contact:
        """Process an incoming PIKE contact invitation.

        Creates a new contact with status ``unconfirmed`` for the
        recipient, or updates an existing one.

        Args:
            recipient_alias: The recipient's paymail alias.
            recipient_domain: The recipient's paymail domain.
            invite: The incoming invitation data.

        Returns:
            The created or updated Contact record.

        Raises:
            SPVError: If the recipient paymail is not found.
        """
        # Verify the recipient paymail exists on this server
        paymail = await self._engine.paymail_service.get_paymail_by_alias(
            recipient_alias, recipient_domain
        )
        if paymail is None:
            raise ErrPaymailNotFound

        # Validate the sender's paymail format
        SanitizedPaymail.from_string(invite.paymail)

        # Create or update the contact
        contact = await self._engine.contact_service.upsert_contact(
            xpub_id=paymail.xpub_id,
            paymail=invite.paymail,
            full_name=invite.full_name,
            pub_key=invite.pub_key,
            status=CONTACT_STATUS_UNCONFIRMED,
        )

        logger.info(
            "PIKE invite received: %s → %s@%s (contact %s)",
            invite.paymail,
            recipient_alias,
            recipient_domain,
            contact.id,
        )

        return contact

    async def send_invite(
        self,
        sender_alias: str,
        sender_domain: str,
        recipient_paymail: str,
        *,
        pub_key: str = "",
    ) -> Contact:
        """Send a PIKE contact invitation to a remote paymail server.

        Creates a local contact record in ``awaiting`` status and
        sends the invitation via the paymail client.

        Args:
            sender_alias: The sender's paymail alias.
            sender_domain: The sender's paymail domain.
            recipient_paymail: The recipient's paymail address.
            pub_key: The sender's public key to share.

        Returns:
            The local Contact record in ``awaiting`` status.
        """
        # Verify the sender paymail exists on this server
        paymail = await self._engine.paymail_service.get_paymail_by_alias(
            sender_alias, sender_domain
        )
        if paymail is None:
            raise ErrPaymailNotFound

        # Parse recipient
        recipient = SanitizedPaymail.from_string(recipient_paymail)

        # Build the invite payload
        invite = PikeContactInvite(
            full_name=paymail.public_name,
            paymail=paymail.address,
            pub_key=pub_key,
        )

        # Send via paymail client
        client = self._engine.paymail_client
        caps = await client.get_capabilities(recipient.domain)

        from spv_wallet.paymail.models import BRFC_PIKE_INVITE

        url_template = caps.get_url(BRFC_PIKE_INVITE)
        if url_template:
            url = client._resolve_url_template(url_template, recipient)
            http = client._ensure_connected()
            try:
                response = await http.post(url, json=invite.to_dict())
                response.raise_for_status()
            except Exception:
                logger.exception("Failed to send PIKE invite to %s", recipient_paymail)

        # Create local contact in awaiting status
        contact = await self._engine.contact_service.upsert_contact(
            xpub_id=paymail.xpub_id,
            paymail=recipient_paymail,
            status=CONTACT_STATUS_AWAITING,
        )

        return contact


class PikePaymentService:
    """Provide PIKE-specific payment outputs.

    When a PIKE-connected sender requests payment outputs,
    this service provides destinations linked to the contact
    relationship.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    async def get_outputs(
        self,
        recipient_alias: str,
        recipient_domain: str,
        request: PikeOutputsRequest,
    ) -> dict:
        """Provide payment outputs for a PIKE sender.

        Args:
            recipient_alias: The recipient's paymail alias.
            recipient_domain: The recipient's paymail domain.
            request: The PIKE outputs request.

        Returns:
            Dict with ``outputs`` and ``reference``.
        """
        # Delegate to the standard P2P destination provider
        from spv_wallet.api.paymail_server.provider import PaymailServiceProvider

        provider = PaymailServiceProvider(self._engine)
        return await provider.create_p2p_destination_response(
            recipient_alias,
            recipient_domain,
            request.satoshis,
        )
