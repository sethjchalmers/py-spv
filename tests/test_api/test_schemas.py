"""Tests for V1 API Pydantic schemas."""

from __future__ import annotations

import pytest

from spv_wallet.api.v1.schemas import (
    ArcCallbackRequest,
    DraftTransactionRequest,
    ErrorResponse,
    PaginationParams,
    TransactionOutput,
    XPubCreateRequest,
)


class TestPaginationParams:
    def test_defaults(self):
        p = PaginationParams()
        assert p.limit == 50
        assert p.offset == 0

    def test_custom_values(self):
        p = PaginationParams(limit=100, offset=10)
        assert p.limit == 100
        assert p.offset == 10

    def test_limit_max(self):
        with pytest.raises(Exception):  # noqa: B017
            PaginationParams(limit=2000)


class TestErrorResponse:
    def test_serialisation(self):
        e = ErrorResponse(code="test-error", message="something failed")
        d = e.model_dump()
        assert d["code"] == "test-error"
        assert d["message"] == "something failed"


class TestXPubCreateRequest:
    def test_with_metadata(self):
        r = XPubCreateRequest(xpub="xpub123", metadata={"key": "value"})
        assert r.xpub == "xpub123"
        assert r.metadata == {"key": "value"}

    def test_without_metadata(self):
        r = XPubCreateRequest(xpub="xpub123")
        assert r.metadata is None


class TestDraftTransactionRequest:
    def test_with_outputs(self):
        r = DraftTransactionRequest(
            outputs=[
                TransactionOutput(to="addr1", satoshis=1000),
                TransactionOutput(op_return="deadbeef"),
            ],
        )
        assert len(r.outputs) == 2
        assert r.outputs[0].to == "addr1"
        assert r.outputs[1].op_return == "deadbeef"


class TestArcCallbackRequest:
    def test_alias_fields(self):
        r = ArcCallbackRequest(
            txID="abc123",
            txStatus="SEEN_ON_NETWORK",
            blockHash="hash",
            blockHeight=100,
        )
        assert r.txid == "abc123"
        assert r.tx_status == "SEEN_ON_NETWORK"
        assert r.block_hash == "hash"
        assert r.block_height == 100

    def test_defaults(self):
        r = ArcCallbackRequest(txID="abc", txStatus="MINED")
        assert r.block_hash == ""
        assert r.block_height == 0
        assert r.competing_txs == []
