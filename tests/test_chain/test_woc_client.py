"""Tests for WhatsOnChain HTTP client — uses httpx mock transport."""

from __future__ import annotations

import json

import httpx
import pytest

from spv_wallet.chain.woc.client import WoCBalance, WoCClient, WoCTxInfo, WoCUtxo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_ADDRESS = "mxVFsFW8Nv5oNPFdBUVR7RaCYQGP2dX9jv"


def _inject_transport(client: WoCClient, transport: httpx.MockTransport) -> None:
    """Replace the internal httpx client with one using mock transport."""
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.whatsonchain.com/v1/bsv/test",
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestWoCClientLifecycle:
    @pytest.mark.asyncio
    async def test_not_connected_by_default(self) -> None:
        woc = WoCClient(testnet=True)
        assert woc.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_and_close(self) -> None:
        woc = WoCClient(testnet=True)
        await woc.connect()
        assert woc.is_connected is True
        await woc.close()
        assert woc.is_connected is False

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        woc = WoCClient(testnet=True)
        await woc.close()
        assert woc.is_connected is False

    @pytest.mark.asyncio
    async def test_not_connected_raises(self) -> None:
        woc = WoCClient(testnet=True)
        with pytest.raises(RuntimeError, match="not connected"):
            await woc.get_balance(_TEST_ADDRESS)

    def test_testnet_flag(self) -> None:
        woc = WoCClient(testnet=True)
        assert woc.testnet is True

    def test_mainnet_flag(self) -> None:
        woc = WoCClient(testnet=False)
        assert woc.testnet is False


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------


class TestWoCBalance:
    @pytest.mark.asyncio
    async def test_get_balance(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert f"/address/{_TEST_ADDRESS}/balance" in str(request.url)
            return httpx.Response(
                200,
                json={"confirmed": 150000, "unconfirmed": 5000},
            )

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        bal = await woc.get_balance(_TEST_ADDRESS)
        assert isinstance(bal, WoCBalance)
        assert bal.confirmed == 150000
        assert bal.unconfirmed == 5000
        assert bal.total == 155000

    @pytest.mark.asyncio
    async def test_get_balance_zero(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"confirmed": 0, "unconfirmed": 0})

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        bal = await woc.get_balance(_TEST_ADDRESS)
        assert bal.confirmed == 0
        assert bal.unconfirmed == 0
        assert bal.total == 0


# ---------------------------------------------------------------------------
# UTXOs
# ---------------------------------------------------------------------------


class TestWoCUtxos:
    @pytest.mark.asyncio
    async def test_get_utxos(self) -> None:
        utxo_data = [
            {"tx_hash": "abc123", "tx_pos": 0, "value": 100000, "height": 12345},
            {"tx_hash": "def456", "tx_pos": 1, "value": 50000, "height": 0},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            assert f"/address/{_TEST_ADDRESS}/unspent" in str(request.url)
            return httpx.Response(200, json=utxo_data)

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        utxos = await woc.get_utxos(_TEST_ADDRESS)
        assert len(utxos) == 2
        assert isinstance(utxos[0], WoCUtxo)
        assert utxos[0].tx_hash == "abc123"
        assert utxos[0].tx_pos == 0
        assert utxos[0].value == 100000
        assert utxos[0].height == 12345
        assert utxos[1].height == 0

    @pytest.mark.asyncio
    async def test_get_utxos_empty(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        utxos = await woc.get_utxos(_TEST_ADDRESS)
        assert utxos == []


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class TestWoCTransaction:
    @pytest.mark.asyncio
    async def test_get_transaction(self) -> None:
        tx_data = {
            "txid": "abc123def456",
            "size": 225,
            "confirmations": 6,
            "blockhash": "0000abc",
            "blockheight": 12345,
            "time": 1700000000,
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=tx_data)

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        info = await woc.get_transaction("abc123def456")
        assert isinstance(info, WoCTxInfo)
        assert info.txid == "abc123def456"
        assert info.confirmations == 6
        assert info.block_height == 12345

    @pytest.mark.asyncio
    async def test_get_raw_tx(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="deadbeefcafe")

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        raw = await woc.get_raw_tx("abc123")
        assert raw == "deadbeefcafe"


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


class TestWoCBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast(self) -> None:
        expected_txid = "abc123456789"

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["txhex"] == "deadbeef"
            return httpx.Response(200, text=f'"{expected_txid}"')

        woc = WoCClient(testnet=True)
        _inject_transport(woc, httpx.MockTransport(handler))

        txid = await woc.broadcast("deadbeef")
        assert txid == expected_txid


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class TestWoCModels:
    def test_balance_total(self) -> None:
        bal = WoCBalance(confirmed=1000, unconfirmed=500)
        assert bal.total == 1500

    def test_utxo_frozen(self) -> None:
        utxo = WoCUtxo(tx_hash="abc", tx_pos=0, value=100, height=1)
        with pytest.raises(AttributeError):
            utxo.value = 200  # type: ignore[misc]

    def test_txinfo_frozen(self) -> None:
        info = WoCTxInfo(
            txid="abc",
            size=100,
            confirmations=3,
            block_hash="",
            block_height=0,
            time=0,
        )
        with pytest.raises(AttributeError):
            info.txid = "def"  # type: ignore[misc]
