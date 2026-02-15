"""Paymail protocol data models.

Dataclasses representing the various paymail protocol structures:
- SanitizedPaymail — parsed and validated alias@domain
- Capabilities — BRFC capability document
- PKIResponse — public key infrastructure response
- PaymentDestination — P2P payment destination (script + satoshis)
- P2PDestinationsResponse — collection of payment destinations
- P2PTransaction — outgoing P2P transaction payload
- P2PSendResponse — server response to P2P send
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# RFC 5322 simplified regex for paymail validation
_PAYMAIL_REGEX = re.compile(r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$")

# Well-known BRFC capability IDs
BRFC_PKI = "pki"
BRFC_PAYMENT_DESTINATION = "paymentDestination"
BRFC_SENDER_VALIDATION = "6745f1a8ee43"
BRFC_VERIFY_PUBLIC_KEY = "a9f510c16bde"
BRFC_PUBLIC_PROFILE = "f12f968c92d6"

# P2P capability IDs
BRFC_P2P_PAYMENT_DESTINATION = "2a40af698840"
BRFC_P2P_SEND_TRANSACTION = "5f1323cddf31"

# BEEF capability
BRFC_BEEF = "5c55a7fdb7bb"

# PIKE capabilities
BRFC_PIKE_INVITE = "7d37fd460120"
BRFC_PIKE_OUTPUTS = "81bfe439380d"


@dataclass(frozen=True, slots=True)
class SanitizedPaymail:
    """A validated and normalized paymail address.

    Attributes:
        alias: The local part (before @), lowercased.
        domain: The domain part (after @), lowercased.
        address: The full ``alias@domain`` string.
    """

    alias: str
    domain: str
    address: str

    @classmethod
    def from_string(cls, raw: str) -> SanitizedPaymail:
        """Parse and sanitize a paymail address string.

        Args:
            raw: A paymail address like "user@example.com".

        Returns:
            A validated SanitizedPaymail instance.

        Raises:
            ValueError: If the address format is invalid.
        """
        raw = raw.strip().lower()
        if not _PAYMAIL_REGEX.match(raw):
            msg = f"invalid paymail address: {raw}"
            raise ValueError(msg)

        alias, domain = raw.split("@", 1)
        if not alias or not domain:
            msg = f"invalid paymail address: {raw}"
            raise ValueError(msg)

        return cls(alias=alias, domain=domain, address=f"{alias}@{domain}")


@dataclass(slots=True)
class Capabilities:
    """BSV Alias (paymail) capability discovery document.

    Returned from ``/.well-known/bsvalias`` endpoint.

    Attributes:
        bsvalias: Protocol version (typically "1.0").
        capabilities: Map of BRFC ID → URL template.
    """

    bsvalias: str = "1.0"
    capabilities: dict[str, str] = field(default_factory=dict)

    def get_url(self, brfc_id: str) -> str | None:
        """Get the URL template for a specific BRFC capability.

        Args:
            brfc_id: The BRFC ID to look up.

        Returns:
            URL template string, or None if not supported.
        """
        return self.capabilities.get(brfc_id)

    @property
    def has_p2p(self) -> bool:
        """Check if the server supports P2P payment destinations."""
        return BRFC_P2P_PAYMENT_DESTINATION in self.capabilities

    @property
    def has_pike(self) -> bool:
        """Check if the server supports PIKE contact invitations."""
        return BRFC_PIKE_INVITE in self.capabilities

    @property
    def has_beef(self) -> bool:
        """Check if the server supports BEEF format."""
        return BRFC_BEEF in self.capabilities

    @classmethod
    def from_dict(cls, data: dict) -> Capabilities:
        """Parse capabilities from a JSON response dict.

        Args:
            data: The parsed JSON from ``.well-known/bsvalias``.

        Returns:
            A Capabilities instance.
        """
        return cls(
            bsvalias=data.get("bsvalias", "1.0"),
            capabilities=data.get("capabilities", {}),
        )


@dataclass(frozen=True, slots=True)
class PKIResponse:
    """Public Key Infrastructure response for a paymail address.

    Attributes:
        bsvalias: Protocol version.
        handle: The paymail address.
        pub_key: The public key hex string.
    """

    bsvalias: str
    handle: str
    pub_key: str

    @classmethod
    def from_dict(cls, data: dict) -> PKIResponse:
        """Parse a PKI response from JSON."""
        return cls(
            bsvalias=data.get("bsvalias", "1.0"),
            handle=data.get("handle", ""),
            pub_key=data.get("pubkey", ""),
        )


@dataclass(frozen=True, slots=True)
class PaymentDestination:
    """A single payment destination in a P2P response.

    Attributes:
        script: The locking script hex.
        satoshis: The amount requested at this destination.
    """

    script: str
    satoshis: int

    @classmethod
    def from_dict(cls, data: dict) -> PaymentDestination:
        """Parse from JSON dict."""
        return cls(
            script=data.get("script", ""),
            satoshis=data.get("satoshis", 0),
        )


@dataclass(slots=True)
class P2PDestinationsResponse:
    """Response from a P2P payment destination request.

    Attributes:
        outputs: List of payment destination outputs.
        reference: Server-assigned reference ID for the payment.
    """

    outputs: list[PaymentDestination] = field(default_factory=list)
    reference: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> P2PDestinationsResponse:
        """Parse a P2P destinations response from JSON."""
        outputs = [PaymentDestination.from_dict(o) for o in data.get("outputs", [])]
        return cls(
            outputs=outputs,
            reference=data.get("reference", ""),
        )


@dataclass(frozen=True, slots=True)
class P2PTransaction:
    """Outgoing P2P transaction payload.

    Sent to the recipient's P2P send endpoint.

    Attributes:
        hex: The raw transaction hex.
        reference: The reference from the destination response.
        metadata: Optional sender metadata.
        beef: BEEF-encoded transaction (alternative to hex).
    """

    hex: str = ""
    reference: str = ""
    metadata: P2PSenderMetadata | None = None
    beef: str = ""

    def to_dict(self) -> dict:
        """Serialize to a dict for JSON payload."""
        d: dict = {"reference": self.reference}
        if self.beef:
            d["beef"] = self.beef
        elif self.hex:
            d["hex"] = self.hex
        if self.metadata:
            d["metadata"] = self.metadata.to_dict()
        return d


@dataclass(frozen=True, slots=True)
class P2PSenderMetadata:
    """Sender metadata attached to a P2P transaction.

    Attributes:
        sender: The sender's paymail address.
        pub_key: The sender's public key hex.
        signature: Signature proving sender identity.
        note: Optional payment note/memo.
    """

    sender: str = ""
    pub_key: str = ""
    signature: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict."""
        d: dict = {}
        if self.sender:
            d["sender"] = self.sender
        if self.pub_key:
            d["pubkey"] = self.pub_key
        if self.signature:
            d["signature"] = self.signature
        if self.note:
            d["note"] = self.note
        return d


@dataclass(frozen=True, slots=True)
class P2PSendResponse:
    """Server response after receiving a P2P transaction.

    Attributes:
        txid: The accepted transaction ID.
        note: Optional response note from the receiver.
    """

    txid: str
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> P2PSendResponse:
        """Parse from JSON response."""
        return cls(
            txid=data.get("txid", ""),
            note=data.get("note", ""),
        )
