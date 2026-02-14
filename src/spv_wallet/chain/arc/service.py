"""ARC HTTP client — broadcast, query, get policy.

Provides an async HTTP client for the ARC v1 API:
- POST /v1/tx — Broadcast a transaction (raw/EF/BEEF hex)
- GET /v1/tx/{txid} — Query transaction status
- GET /v1/policy — Get current mining fee policy
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from spv_wallet.chain.arc.models import FeeUnit, PolicyResponse, TXInfo
from spv_wallet.errors.chain_errors import ARCError

if TYPE_CHECKING:
    from spv_wallet.config.settings import ARCConfig

# Default fee unit used when ARC is unreachable
_DEFAULT_FEE_UNIT = FeeUnit(satoshis=1, bytes=1000)


class ARCService:
    """Async HTTP client for the ARC transaction broadcasting API.

    Usage::

        arc = ARCService(config)
        await arc.connect()
        try:
            info = await arc.broadcast("raw_hex_here")
        finally:
            await arc.close()
    """

    def __init__(self, config: ARCConfig) -> None:
        """Initialize the ARC service.

        Args:
            config: ARC configuration (url, token, deployment_id, etc.).
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._cached_fee_unit: FeeUnit | None = None

    async def connect(self) -> None:
        """Create the underlying HTTP client."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        if self._config.deployment_id:
            headers["XDeployment-ID"] = self._config.deployment_id

        self._client = httpx.AsyncClient(
            base_url=self._config.url.rstrip("/"),
            headers=headers,
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if the HTTP client is active."""
        return self._client is not None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def broadcast(
        self,
        raw_tx: str,
        *,
        wait_for: str | None = None,
    ) -> TXInfo:
        """Broadcast a transaction to the ARC network.

        Args:
            raw_tx: Transaction hex (raw, EF, or BEEF format).
            wait_for: Override the wait strategy (e.g. 'SEEN_ON_NETWORK').

        Returns:
            TXInfo with the broadcast result.

        Raises:
            ARCError: On HTTP or API errors.
        """
        client = self._ensure_connected()

        headers: dict[str, str] = {}
        effective_wait = wait_for or self._config.wait_for.value
        if effective_wait:
            headers["X-WaitFor"] = effective_wait
        if self._config.callback_url:
            headers["X-CallbackUrl"] = self._config.callback_url
        if self._config.callback_token:
            headers["X-CallbackToken"] = self._config.callback_token

        try:
            response = await client.post(
                "/v1/tx",
                json={"rawTx": raw_tx},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ARCError(f"ARC broadcast failed: {exc}") from exc

        if response.status_code in (200, 201):
            return TXInfo.from_dict(response.json())

        # Map ARC-specific error codes
        self._raise_for_status(response, "broadcast")
        return TXInfo()  # unreachable, satisfies type checker

    async def query_transaction(self, txid: str) -> TXInfo:
        """Query the status of a transaction by txid.

        Args:
            txid: The 64-character hex transaction ID.

        Returns:
            TXInfo with the current status.

        Raises:
            ARCError: On HTTP or API errors.
        """
        client = self._ensure_connected()

        try:
            response = await client.get(f"/v1/tx/{txid}")
        except httpx.HTTPError as exc:
            raise ARCError(f"ARC query failed: {exc}") from exc

        if response.status_code == 200:
            return TXInfo.from_dict(response.json())

        self._raise_for_status(response, "query")
        return TXInfo()  # unreachable

    async def get_policy(self) -> PolicyResponse:
        """Get the current ARC mining policy (fee unit, limits).

        Returns:
            PolicyResponse with fee and size limits.

        Raises:
            ARCError: On HTTP or API errors.
        """
        client = self._ensure_connected()

        try:
            response = await client.get("/v1/policy")
        except httpx.HTTPError as exc:
            raise ARCError(f"ARC policy request failed: {exc}") from exc

        if response.status_code == 200:
            policy = PolicyResponse.from_dict(response.json())
            self._cached_fee_unit = policy.mining_fee
            return policy

        self._raise_for_status(response, "get_policy")
        return PolicyResponse()  # unreachable

    async def get_fee_unit(self) -> FeeUnit:
        """Get the current mining fee unit.

        Returns the cached value if available, otherwise fetches from ARC.

        Returns:
            FeeUnit with satoshis/bytes rate.
        """
        if self._cached_fee_unit is not None:
            return self._cached_fee_unit

        try:
            policy = await self.get_policy()
            return policy.mining_fee
        except ARCError:
            return _DEFAULT_FEE_UNIT

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> httpx.AsyncClient:
        """Return the HTTP client, raising if not connected."""
        if self._client is None:
            msg = "ARC service not connected. Call connect() first."
            raise ARCError(msg, status_code=500)
        return self._client

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        """Raise an ARCError from a non-2xx response."""
        status = response.status_code
        try:
            body = response.json()
            detail = body.get("detail", body.get("title", response.text))
        except Exception:
            detail = response.text

        # Map ARC-specific status codes
        error_map = {
            401: "ARC authentication failed",
            409: "Transaction already exists (conflict)",
            460: "Transaction is not in extended format",
            461: "Transaction is malformed",
            465: "Fee too low",
            473: "Cumulative fee validation failed",
        }

        message = error_map.get(status, f"ARC {operation} failed ({status}): {detail}")
        raise ARCError(message, status_code=status)
