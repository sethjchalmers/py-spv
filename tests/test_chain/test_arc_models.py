"""Tests for ARC data models — TXInfo, TXStatus, FeeUnit, PolicyResponse."""

from __future__ import annotations

from spv_wallet.chain.arc.models import FeeUnit, PolicyResponse, TXInfo, TXStatus


# ---------------------------------------------------------------------------
# TXStatus
# ---------------------------------------------------------------------------


class TestTXStatus:
    def test_all_status_values(self):
        assert TXStatus.UNKNOWN == "UNKNOWN"
        assert TXStatus.MINED == "MINED"
        assert TXStatus.SEEN_ON_NETWORK == "SEEN_ON_NETWORK"
        assert TXStatus.REJECTED == "REJECTED"

    def test_from_string_valid(self):
        assert TXStatus.from_string("MINED") == TXStatus.MINED
        assert TXStatus.from_string("SEEN_ON_NETWORK") == TXStatus.SEEN_ON_NETWORK

    def test_from_string_unknown(self):
        assert TXStatus.from_string("BOGUS") == TXStatus.UNKNOWN
        assert TXStatus.from_string("") == TXStatus.UNKNOWN

    def test_status_lifecycle_order(self):
        lifecycle = [
            TXStatus.QUEUED, TXStatus.RECEIVED, TXStatus.STORED,
            TXStatus.ANNOUNCED_TO_NETWORK, TXStatus.REQUESTED_BY_NETWORK,
            TXStatus.SENT_TO_NETWORK, TXStatus.ACCEPTED_BY_NETWORK,
            TXStatus.SEEN_ON_NETWORK, TXStatus.MINED, TXStatus.CONFIRMED,
        ]
        assert len(lifecycle) == 10


# ---------------------------------------------------------------------------
# TXInfo
# ---------------------------------------------------------------------------


class TestTXInfo:
    def test_defaults(self):
        info = TXInfo()
        assert info.txid == ""
        assert info.tx_status == ""
        assert info.block_height == 0
        assert info.competing_txs == []
        assert info.status == TXStatus.UNKNOWN

    def test_from_dict_camel_case(self):
        data = {
            "txid": "abc123",
            "txStatus": "MINED",
            "blockHash": "blockhash123",
            "blockHeight": 800000,
            "merklePath": "merkle_data",
            "timestamp": 1700000000,
            "competingTxs": ["tx1", "tx2"],
            "extraInfo": "extra",
        }
        info = TXInfo.from_dict(data)
        assert info.txid == "abc123"
        assert info.tx_status == "MINED"
        assert info.status == TXStatus.MINED
        assert info.block_hash == "blockhash123"
        assert info.block_height == 800000
        assert info.merkle_path == "merkle_data"
        assert info.timestamp == 1700000000
        assert info.competing_txs == ["tx1", "tx2"]
        assert info.extra_info == "extra"

    def test_from_dict_snake_case(self):
        data = {"txid": "x", "tx_status": "REJECTED", "block_height": 5}
        info = TXInfo.from_dict(data)
        assert info.tx_status == "REJECTED"
        assert info.block_height == 5

    def test_to_dict(self):
        info = TXInfo(txid="abc", tx_status="MINED", block_height=100)
        d = info.to_dict()
        assert d["txid"] == "abc"
        assert d["txStatus"] == "MINED"
        assert d["blockHeight"] == 100

    def test_is_mined(self):
        assert TXInfo(tx_status="MINED").is_mined is True
        assert TXInfo(tx_status="CONFIRMED").is_mined is True
        assert TXInfo(tx_status="SEEN_ON_NETWORK").is_mined is False
        assert TXInfo(tx_status="REJECTED").is_mined is False

    def test_from_dict_missing_fields(self):
        info = TXInfo.from_dict({})
        assert info.txid == ""
        assert info.block_height == 0

    def test_roundtrip(self):
        info = TXInfo(
            txid="deadbeef", tx_status="SEEN_ON_NETWORK",
            block_height=0, timestamp=12345,
        )
        info2 = TXInfo.from_dict(info.to_dict())
        assert info.txid == info2.txid
        assert info.tx_status == info2.tx_status


# ---------------------------------------------------------------------------
# FeeUnit
# ---------------------------------------------------------------------------


class TestFeeUnit:
    def test_defaults(self):
        f = FeeUnit()
        assert f.satoshis == 1
        assert f.bytes == 1000

    def test_from_dict(self):
        f = FeeUnit.from_dict({"satoshis": 5, "bytes": 500})
        assert f.satoshis == 5
        assert f.bytes == 500

    def test_fee_for_size(self):
        f = FeeUnit(satoshis=1, bytes=1000)
        assert f.fee_for_size(1000) == 1
        assert f.fee_for_size(1) == 1  # minimum 1 sat
        assert f.fee_for_size(1001) == 2  # rounds up
        assert f.fee_for_size(2000) == 2
        assert f.fee_for_size(5000) == 5

    def test_fee_for_size_higher_rate(self):
        f = FeeUnit(satoshis=10, bytes=1000)
        assert f.fee_for_size(1000) == 10
        assert f.fee_for_size(500) == 5


# ---------------------------------------------------------------------------
# PolicyResponse
# ---------------------------------------------------------------------------


class TestPolicyResponse:
    def test_defaults(self):
        p = PolicyResponse()
        assert p.max_tx_size_policy == 10_000_000
        assert p.mining_fee.satoshis == 1

    def test_from_dict_nested(self):
        data = {
            "policy": {
                "maxScriptSizePolicy": 50_000_000,
                "maxTxSizePolicy": 5_000_000,
                "miningFee": {"satoshis": 2, "bytes": 500},
            }
        }
        p = PolicyResponse.from_dict(data)
        assert p.max_script_size_policy == 50_000_000
        assert p.max_tx_size_policy == 5_000_000
        assert p.mining_fee.satoshis == 2
        assert p.mining_fee.bytes == 500

    def test_from_dict_flat(self):
        data = {
            "maxScriptSizePolicy": 100,
            "maxTxSizePolicy": 200,
            "miningFee": {"satoshis": 3, "bytes": 1000},
        }
        p = PolicyResponse.from_dict(data)
        assert p.max_script_size_policy == 100
        assert p.max_tx_size_policy == 200

    def test_from_dict_empty(self):
        p = PolicyResponse.from_dict({})
        assert p.mining_fee.satoshis == 1  # defaults
