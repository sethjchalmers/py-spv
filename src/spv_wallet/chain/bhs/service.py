"""BHS HTTP client — verify Merkle roots, get roots, health check.

Provides an async HTTP client for the Block Headers Service (BHS) API:
- POST /api/v1/chain/merkleroot/verify — Verify Merkle roots against block headers
- GET /api/v1/chain/merkleroot — Get known Merkle roots (paginated)
- GET /api/v1/chain/healthcheck — Health check
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from spv_wallet.chain.bhs.models import (
    ConfirmationState,
    MerkleRootVerification,
    MerkleRootsResponse,
    VerifyMerkleRootsResponse,
)
from spv_wallet.errors.chain_errors import BHSError

if TYPE_CHECKING:
    from spv_wallet.config.settings import BHSConfig


class BHSService:
    """Async HTTP client for the Block Headers Service.

    Usage::

        bhs = BHSService(config)
        await bhs.connect()
        try:
            result = await bhs.verify_merkle_roots([...])
        finally:
            await bhs.close()
    """

    def __init__(self, config: BHSConfig) -> None:
        """Initialize the BHS service.

        Args:
            config: BHS configuration (url, auth_token).
        """
        self._config = config
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:  # noqa: ASYNC910
        """Create the underlying HTTP client."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.auth_token:
            headers["Authorization"] = f"Bearer {self._config.auth_token}"

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

    async def verify_merkle_roots(
        self, roots: list[MerkleRootVerification]
    ) -> VerifyMerkleRootsResponse:
        """Verify a list of Merkle roots against BHS.

        Args:
            roots: List of MerkleRootVerification objects.

        Returns:
            VerifyMerkleRootsResponse with confirmation states.

        Raises:
            BHSError: On HTTP or API errors.
        """
        client = self._ensure_connected()

        body = [root.to_dict() for root in roots]

        try:
            response = await client.post(
                "/api/v1/chain/merkleroot/verify",
                json=body,
            )
        except httpx.HTTPError as exc:
            raise BHSError(f"BHS verify failed: {exc}") from exc

        if response.status_code == 200:
            return VerifyMerkleRootsResponse.from_dict(response.json())

        self._raise_for_status(response, "verify_merkle_roots")
        return VerifyMerkleRootsResponse()  # unreachable

    async def get_merkle_roots(
        self,
        *,
        page: int = 0,
        size: int = 50,
    ) -> MerkleRootsResponse:
        """Get known Merkle roots from BHS (paginated).

        Args:
            page: Page number (0-based).
            size: Page size.

        Returns:
            MerkleRootsResponse with content and pagination info.

        Raises:
            BHSError: On HTTP or API errors.
        """
        client = self._ensure_connected()

        try:
            response = await client.get(
                "/api/v1/chain/merkleroot",
                params={"page": page, "size": size},
            )
        except httpx.HTTPError as exc:
            raise BHSError(f"BHS get_merkle_roots failed: {exc}") from exc

        if response.status_code == 200:
            return MerkleRootsResponse.from_dict(response.json())

        self._raise_for_status(response, "get_merkle_roots")
        return MerkleRootsResponse()  # unreachable

    async def healthcheck(self) -> bool:
        """Check BHS connectivity and health.

        Returns:
            True if BHS is reachable and healthy.
        """
        client = self._ensure_connected()

        try:
            response = await client.get("/api/v1/chain/healthcheck")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def is_valid_root(self, merkle_root: str, block_height: int) -> bool:
        """Convenience: verify a single Merkle root.

        Args:
            merkle_root: Merkle root hash (hex).
            block_height: Block height.

        Returns:
            True if confirmed, False otherwise.
        """
        verification = MerkleRootVerification(
            merkle_root=merkle_root,
            block_height=block_height,
        )
        result = await self.verify_merkle_roots([verification])
        return result.confirmation_state == ConfirmationState.CONFIRMED

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> httpx.AsyncClient:
        """Return the HTTP client, raising if not connected."""
        if self._client is None:
            msg = "BHS service not connected. Call connect() first."
            raise BHSError(msg, status_code=500)
        return self._client

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        """Raise a BHSError from a non-2xx response."""
        status = response.status_code
        try:
            body = response.json()
            detail = body.get("detail", body.get("message", response.text))
        except Exception:  # noqa: BLE001
            detail = response.text

        message = f"BHS {operation} failed ({status}): {detail}"
        raise BHSError(message, status_code=status)
