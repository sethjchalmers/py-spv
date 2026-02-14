"""Tests for error classes and pre-defined error instances."""

from __future__ import annotations

import pytest

from spv_wallet.errors import definitions as defs
from spv_wallet.errors.chain_errors import ARCError, BHSError
from spv_wallet.errors.spv_errors import SPVError

# ---------------------------------------------------------------------------
# SPVError base class
# ---------------------------------------------------------------------------


class TestSPVError:
    def test_default_attributes(self) -> None:
        err = SPVError("something broke")
        assert str(err) == "something broke"
        assert err.message == "something broke"
        assert err.status_code == 500
        assert err.code == "spv-error"

    def test_custom_attributes(self) -> None:
        err = SPVError("bad request", status_code=400, code="bad-req")
        assert err.status_code == 400
        assert err.code == "bad-req"

    def test_is_exception(self) -> None:
        with pytest.raises(SPVError, match="boom"):
            raise SPVError("boom")


# ---------------------------------------------------------------------------
# ARCError / BHSError
# ---------------------------------------------------------------------------


class TestARCError:
    def test_defaults(self) -> None:
        err = ARCError("arc failed")
        assert isinstance(err, SPVError)
        assert err.status_code == 502
        assert err.code == "arc-error"
        assert err.message == "arc failed"

    def test_custom_status(self) -> None:
        err = ARCError("timeout", status_code=504)
        assert err.status_code == 504

    def test_raise(self) -> None:
        with pytest.raises(ARCError):
            raise ARCError("rejected")


class TestBHSError:
    def test_defaults(self) -> None:
        err = BHSError("bhs unreachable")
        assert isinstance(err, SPVError)
        assert err.status_code == 502
        assert err.code == "bhs-error"
        assert err.message == "bhs unreachable"

    def test_custom_status(self) -> None:
        err = BHSError("slow", status_code=504)
        assert err.status_code == 504

    def test_raise(self) -> None:
        with pytest.raises(BHSError):
            raise BHSError("header not found")


# ---------------------------------------------------------------------------
# Pre-defined error instances (definitions.py)
# ---------------------------------------------------------------------------


class TestDefinitions:
    """Verify all pre-defined error singletons have expected attributes."""

    @pytest.mark.parametrize(
        ("error_name", "status", "code"),
        [
            ("ErrUnauthorized", 401, "unauthorized"),
            ("ErrAdminRequired", 403, "admin-required"),
            ("ErrMissingFieldXPub", 400, "missing-xpub"),
            ("ErrInvalidXPub", 400, "invalid-xpub"),
            ("ErrXPubNotFound", 404, "xpub-not-found"),
            ("ErrTransactionNotFound", 404, "transaction-not-found"),
            ("ErrUTXONotFound", 404, "utxo-not-found"),
            ("ErrContactNotFound", 404, "contact-not-found"),
            ("ErrNotEnoughFunds", 422, "not-enough-funds"),
            ("ErrDraftNotFound", 404, "draft-not-found"),
            ("ErrTransactionRejected", 422, "transaction-rejected"),
        ],
    )
    def test_predefined_error(self, error_name: str, status: int, code: str) -> None:
        err = getattr(defs, error_name)
        assert isinstance(err, SPVError)
        assert err.status_code == status
        assert err.code == code
        assert err.message  # non-empty message
