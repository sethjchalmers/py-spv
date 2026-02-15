"""Paymail client — outgoing paymail protocol operations.

Provides an async HTTP client for communicating with remote paymail servers:
- SRV record lookup for paymail domains
- Capability discovery (``.well-known/bsvalias``)
- PKI (public key) resolution
- P2P payment destination fetching
- P2P transaction sending

Mirrors the Go ``engine/paymail/paymail_service_client.go``.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from spv_wallet.errors.definitions import (
    ErrPaymailCapabilitiesNotFound,
    ErrPaymailP2PFailed,
    ErrPaymailP2PSendFailed,
    ErrPaymailPKIFailed,
    ErrPaymailSRVFailed,
)
from spv_wallet.paymail.models import (
    BRFC_P2P_PAYMENT_DESTINATION,
    BRFC_P2P_SEND_TRANSACTION,
    BRFC_PKI,
    Capabilities,
    P2PDestinationsResponse,
    P2PSendResponse,
    P2PTransaction,
    PKIResponse,
    SanitizedPaymail,
)

logger = logging.getLogger(__name__)

# Default ports for SRV lookup
_DEFAULT_PORT = 443
_SRV_PROTOCOL = "_bsvalias._tcp"

# Capability cache TTL
_CAPABILITIES_CACHE_TTL = 300  # 5 minutes


class PaymailClient:
    """Async HTTP client for outgoing paymail protocol operations.

    Usage::

        client = PaymailClient()
        await client.connect()
        try:
            pm = SanitizedPaymail.from_string("user@example.com")
            pki = await client.get_pki(pm)
            dests = await client.get_p2p_destinations(pm, satoshis=1000)
        finally:
            await client.close()
    """

    def __init__(self, *, timeout: float = 30.0) -> None:
        """Initialize the paymail client.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._capabilities_cache: dict[str, tuple[Capabilities, float]] = {}

    async def connect(self) -> None:
        """Create the underlying HTTP client."""
        if self._client is not None:
            return
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": "py-spv/1.0"},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._capabilities_cache.clear()

    @property
    def is_connected(self) -> bool:
        """Check if the HTTP client is active."""
        return self._client is not None

    # ------------------------------------------------------------------
    # SRV Lookup
    # ------------------------------------------------------------------

    async def resolve_srv(self, domain: str) -> tuple[str, int]:
        """Resolve the paymail SRV record for a domain.

        Falls back to the domain itself on port 443 if SRV lookup fails.

        Args:
            domain: The paymail domain (e.g. ``example.com``).

        Returns:
            Tuple of (host, port).
        """
        try:
            loop = asyncio.get_running_loop()
            host, port = await loop.run_in_executor(None, self._srv_lookup_sync, domain)
            return host, port
        except Exception:
            logger.debug("SRV lookup failed for %s, using default", domain)
            return domain, _DEFAULT_PORT

    @staticmethod
    def _srv_lookup_sync(domain: str) -> tuple[str, int]:
        """Synchronous SRV record lookup using dnspython.

        Falls back to default if dnspython is not installed.

        Args:
            domain: The paymail domain.

        Returns:
            Tuple of (target_host, port).
        """
        try:
            import dns.resolver  # type: ignore[import-untyped]

            answers = dns.resolver.resolve(f"{_SRV_PROTOCOL}.{domain}", "SRV")
            # Use the highest priority (lowest value) record
            best = min(answers, key=lambda r: r.priority)
            target = str(best.target).rstrip(".")
            return target, best.port
        except Exception:
            return domain, _DEFAULT_PORT

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    async def get_capabilities(self, domain: str) -> Capabilities:
        """Fetch the capabilities document for a paymail domain.

        Results are cached for 5 minutes.

        Args:
            domain: The paymail domain.

        Returns:
            The Capabilities document.

        Raises:
            SPVError: If capabilities cannot be fetched.
        """
        # Check cache
        now = asyncio.get_event_loop().time()
        cached = self._capabilities_cache.get(domain)
        if cached is not None:
            caps, ts = cached
            if now - ts < _CAPABILITIES_CACHE_TTL:
                return caps

        # Resolve SRV
        host, port = await self.resolve_srv(domain)

        # Build URL
        scheme = "https" if port == 443 else "http"
        port_suffix = "" if port in (443, 80) else f":{port}"
        url = f"{scheme}://{host}{port_suffix}/.well-known/bsvalias"

        client = self._ensure_connected()
        try:
            response = await client.get(url)
            response.raise_for_status()
            caps = Capabilities.from_dict(response.json())
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch capabilities for %s: %s", domain, exc)
            raise ErrPaymailCapabilitiesNotFound from exc

        # Cache
        self._capabilities_cache[domain] = (caps, now)
        return caps

    # ------------------------------------------------------------------
    # PKI
    # ------------------------------------------------------------------

    async def get_pki(self, paymail: SanitizedPaymail) -> PKIResponse:
        """Resolve the public key for a paymail address.

        Args:
            paymail: The sanitized paymail address.

        Returns:
            PKIResponse with the public key.

        Raises:
            SPVError: If PKI lookup fails.
        """
        caps = await self.get_capabilities(paymail.domain)
        url_template = caps.get_url(BRFC_PKI)
        if not url_template:
            raise ErrPaymailPKIFailed

        url = self._resolve_url_template(url_template, paymail)
        client = self._ensure_connected()

        try:
            response = await client.get(url)
            response.raise_for_status()
            return PKIResponse.from_dict(response.json())
        except httpx.HTTPError as exc:
            logger.error("PKI lookup failed for %s: %s", paymail.address, exc)
            raise ErrPaymailPKIFailed from exc

    # ------------------------------------------------------------------
    # P2P Payment Destinations
    # ------------------------------------------------------------------

    async def get_p2p_destinations(
        self,
        paymail: SanitizedPaymail,
        *,
        satoshis: int,
    ) -> P2PDestinationsResponse:
        """Fetch P2P payment destinations from the recipient's paymail server.

        Args:
            paymail: The recipient's sanitized paymail address.
            satoshis: The amount in satoshis to send.

        Returns:
            P2PDestinationsResponse with outputs and reference.

        Raises:
            SPVError: If the request fails.
        """
        caps = await self.get_capabilities(paymail.domain)
        url_template = caps.get_url(BRFC_P2P_PAYMENT_DESTINATION)
        if not url_template:
            raise ErrPaymailP2PFailed

        url = self._resolve_url_template(url_template, paymail)
        client = self._ensure_connected()

        try:
            response = await client.post(url, json={"satoshis": satoshis})
            response.raise_for_status()
            return P2PDestinationsResponse.from_dict(response.json())
        except httpx.HTTPError as exc:
            logger.error("P2P destinations failed for %s: %s", paymail.address, exc)
            raise ErrPaymailP2PFailed from exc

    # ------------------------------------------------------------------
    # P2P Send Transaction
    # ------------------------------------------------------------------

    async def send_p2p_transaction(
        self,
        paymail: SanitizedPaymail,
        transaction: P2PTransaction,
    ) -> P2PSendResponse:
        """Send a P2P transaction to the recipient's paymail server.

        Args:
            paymail: The recipient's sanitized paymail address.
            transaction: The transaction payload.

        Returns:
            P2PSendResponse with the accepted txid.

        Raises:
            SPVError: If the send fails.
        """
        caps = await self.get_capabilities(paymail.domain)
        url_template = caps.get_url(BRFC_P2P_SEND_TRANSACTION)
        if not url_template:
            raise ErrPaymailP2PSendFailed

        url = self._resolve_url_template(url_template, paymail)
        client = self._ensure_connected()

        try:
            response = await client.post(url, json=transaction.to_dict())
            response.raise_for_status()
            return P2PSendResponse.from_dict(response.json())
        except httpx.HTTPError as exc:
            logger.error("P2P send failed for %s: %s", paymail.address, exc)
            raise ErrPaymailP2PSendFailed from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> httpx.AsyncClient:
        """Return the HTTP client, raising if not connected."""
        if self._client is None:
            raise ErrPaymailSRVFailed  # reuse as "not connected" error
        return self._client

    @staticmethod
    def _resolve_url_template(template: str, paymail: SanitizedPaymail) -> str:
        """Replace ``{alias}`` and ``{domain.tld}`` placeholders in URL templates.

        Args:
            template: URL template from capabilities document.
            paymail: The target paymail address.

        Returns:
            Resolved URL string.
        """
        url = template.replace("{alias}", paymail.alias)
        url = url.replace("{domain.tld}", paymail.domain)
        return url
