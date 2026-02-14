"""Tests for BHS data models — ConfirmationState, MerkleRootConfirmation, etc."""

from __future__ import annotations

from spv_wallet.chain.bhs.models import (
    ConfirmationState,
    MerkleRootConfirmation,
    MerkleRootVerification,
    MerkleRootsResponse,
    VerifyMerkleRootsResponse,
)


# ---------------------------------------------------------------------------
# ConfirmationState
# ---------------------------------------------------------------------------


class TestConfirmationState:
    def test_values(self):
        assert ConfirmationState.CONFIRMED == "CONFIRMED"
        assert ConfirmationState.INVALID == "INVALID"
        assert ConfirmationState.UNABLE_TO_VERIFY == "UNABLE_TO_VERIFY"

    def test_from_string_valid(self):
        assert ConfirmationState.from_string("CONFIRMED") == ConfirmationState.CONFIRMED
        assert ConfirmationState.from_string("confirmed") == ConfirmationState.CONFIRMED

    def test_from_string_unknown(self):
        assert ConfirmationState.from_string("BOGUS") == ConfirmationState.UNABLE_TO_VERIFY


# ---------------------------------------------------------------------------
# MerkleRootVerification
# ---------------------------------------------------------------------------


class TestMerkleRootVerification:
    def test_to_dict(self):
        v = MerkleRootVerification(merkle_root="aabb", block_height=100)
        d = v.to_dict()
        assert d["merkleRoot"] == "aabb"
        assert d["blockHeight"] == 100


# ---------------------------------------------------------------------------
# MerkleRootConfirmation
# ---------------------------------------------------------------------------


class TestMerkleRootConfirmation:
    def test_defaults(self):
        c = MerkleRootConfirmation()
        assert c.merkle_root == ""
        assert c.confirmation == ConfirmationState.UNABLE_TO_VERIFY

    def test_from_dict_camel(self):
        data = {
            "merkleRoot": "abc123",
            "blockHeight": 500,
            "confirmation": "CONFIRMED",
        }
        c = MerkleRootConfirmation.from_dict(data)
        assert c.merkle_root == "abc123"
        assert c.block_height == 500
        assert c.confirmation == ConfirmationState.CONFIRMED

    def test_from_dict_snake(self):
        data = {
            "merkle_root": "xyz",
            "block_height": 10,
            "confirmationState": "INVALID",
        }
        c = MerkleRootConfirmation.from_dict(data)
        assert c.merkle_root == "xyz"
        assert c.confirmation == ConfirmationState.INVALID


# ---------------------------------------------------------------------------
# MerkleRootsResponse
# ---------------------------------------------------------------------------


class TestMerkleRootsResponse:
    def test_from_dict(self):
        data = {
            "content": [
                {"merkleRoot": "aaa", "blockHeight": 1, "confirmation": "CONFIRMED"},
                {"merkleRoot": "bbb", "blockHeight": 2, "confirmation": "INVALID"},
            ],
            "page": {"number": 0, "totalPages": 3, "totalElements": 25},
        }
        r = MerkleRootsResponse.from_dict(data)
        assert len(r.content) == 2
        assert r.content[0].merkle_root == "aaa"
        assert r.page == 0
        assert r.total_pages == 3
        assert r.total_elements == 25

    def test_from_dict_empty(self):
        r = MerkleRootsResponse.from_dict({})
        assert r.content == []
        assert r.page == 0


# ---------------------------------------------------------------------------
# VerifyMerkleRootsResponse
# ---------------------------------------------------------------------------


class TestVerifyMerkleRootsResponse:
    def test_all_confirmed(self):
        r = VerifyMerkleRootsResponse(confirmation_state=ConfirmationState.CONFIRMED)
        assert r.all_confirmed is True

    def test_not_confirmed(self):
        r = VerifyMerkleRootsResponse(confirmation_state=ConfirmationState.INVALID)
        assert r.all_confirmed is False

    def test_from_dict(self):
        data = {
            "confirmationState": "CONFIRMED",
            "confirmations": [
                {"merkleRoot": "abc", "blockHeight": 5, "confirmation": "CONFIRMED"},
            ],
        }
        r = VerifyMerkleRootsResponse.from_dict(data)
        assert r.all_confirmed is True
        assert len(r.confirmations) == 1
        assert r.confirmations[0].merkle_root == "abc"
