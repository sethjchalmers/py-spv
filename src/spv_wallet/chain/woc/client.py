"""WhatsOnChain REST client — balance, UTXOs, broadcast, transaction lookup.

Async HTTP client for the free public WhatsOnChain API:
- GET  /v1/bsv/<network>/address/<addr>/balance
- GET  /v1/bsv/<network>/address/<addr>/unspent
- POST /v1/bsv/<network>/tx/raw
- GET  /v1/bsv/<network>/tx/hash/<txid>

Supports both mainnet and testnet via the ``network`` parameter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WoCBalance:
    """Address balance from WhatsOnChain."""

    confirmed: int  # satoshis
    unconfirmed: int  # satoshis

    @property
    def total(self) -> int:
        return self.confirmed + self.unconfirmed


@dataclass(frozen=True)
class WoCUtxo:
    """A single UTXO from WhatsOnChain."""

    tx_hash: str
    tx_pos: int  # vout index
    value: int  # satoshis
    height: int  # 0 = unconfirmed


@dataclass(frozen=True)
class WoCTxInfo:
    """Basic transaction info from WhatsOnChain."""

    txid: str
    size: int
    confirmations: int
    block_hash: str
    block_height: int
    time: int


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.whatsonchain.com/v1/bsv"


class WoCClient:
    """Async HTTP client for the WhatsOnChain BSV API.

    Usage::

        woc = WoCClient(testnet=True)
        await woc.connect()
        try:
            balance = await woc.get_balance("mxyz...")
            utxos = await woc.get_utxos("mxyz...")
        finally:
            await woc.close()
    """

    def __init__(self, *, testnet: bool = False) -> None:
        """Initialize the WoC client.

        Args:
            testnet: If True, use the testnet API endpoint.
        """
        self._testnet = testnet
        self._network = "test" if testnet else "main"
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Create the underlying HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=f"{_BASE_URL}/{self._network}",
            headers={"Accept": "application/json"},
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

    @property
    def testnet(self) -> bool:
        """Whether this client targets testnet."""
        return self._testnet

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_balance(self, address: str) -> WoCBalance:
        """Get the confirmed/unconfirmed balance for an address.

        Args:
            address: P2PKH address string.

        Returns:
            WoCBalance with confirmed and unconfirmed satoshi amounts.
        """
        client = self._ensure_connected()
        resp = await client.get(f"/address/{address}/balance")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return WoCBalance(
            confirmed=data.get("confirmed", 0),
            unconfirmed=data.get("unconfirmed", 0),
        )

    async def get_utxos(self, address: str) -> list[WoCUtxo]:
        """Get unspent transaction outputs for an address.

        Args:
            address: P2PKH address string.

        Returns:
            List of WoCUtxo objects.
        """
        client = self._ensure_connected()
        resp = await client.get(f"/address/{address}/unspent")
        resp.raise_for_status()
        items: list[dict[str, Any]] = resp.json()
        return [
            WoCUtxo(
                tx_hash=item["tx_hash"],
                tx_pos=item["tx_pos"],
                value=item["value"],
                height=item.get("height", 0),
            )
            for item in items
        ]

    async def get_transaction(self, txid: str) -> WoCTxInfo:
        """Get basic transaction info by txid.

        Args:
            txid: Transaction hash (hex).

        Returns:
            WoCTxInfo with confirmation and block details.
        """
        client = self._ensure_connected()
        resp = await client.get(f"/tx/hash/{txid}")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return WoCTxInfo(
            txid=data.get("txid", txid),
            size=data.get("size", 0),
            confirmations=data.get("confirmations", 0),
            block_hash=data.get("blockhash", ""),
            block_height=data.get("blockheight", 0),
            time=data.get("time", 0),
        )

    async def get_raw_tx(self, txid: str) -> str:
        """Get raw transaction hex by txid.

        Args:
            txid: Transaction hash (hex).

        Returns:
            Raw transaction hex string.
        """
        client = self._ensure_connected()
        resp = await client.get(f"/tx/{txid}/hex")
        resp.raise_for_status()
        return resp.text.strip()

    async def broadcast(self, raw_tx_hex: str) -> str:
        """Broadcast a signed transaction.

        Args:
            raw_tx_hex: Signed transaction in hex format.

        Returns:
            The txid of the broadcast transaction.
        """
        client = self._ensure_connected()
        resp = await client.post(
            "/tx/raw",
            json={"txhex": raw_tx_hex},
        )
        resp.raise_for_status()
        # WoC returns the txid as plain text or in JSON
        text = resp.text.strip().strip('"')
        return text

    async def get_exchange_rate(self) -> float:
        """Get current BSV/USD exchange rate.

        Returns:
            USD price per BSV.
        """
        client = self._ensure_connected()
        resp = await client.get("/exchangerate")
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return float(data.get("rate", 0.0))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> httpx.AsyncClient:
        if self._client is None:
            msg = "WoCClient is not connected — call connect() first"
            raise RuntimeError(msg)
        return self._client
