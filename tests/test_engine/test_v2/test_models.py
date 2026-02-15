"""Tests for V2 database models — enum values, table names, relationships."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from spv_wallet.engine.v2.database.models import (
    ALL_V2_MODELS,
    AddressV2,
    ContactStatus,
    DataV2,
    Operation,
    OperationType,
    PaymailV2,
    TrackedOutput,
    TrackedTransaction,
    TxInput,
    TxStatusV2,
    UserContact,
    UserUTXO,
    UserV2,
)


class TestEnums:
    """Enum value integrity checks."""

    def test_tx_status_values(self) -> None:
        vals = {s.value for s in TxStatusV2}
        assert vals == {
            "CREATED",
            "BROADCASTED",
            "SEEN_ON_NETWORK",
            "MINED",
            "REJECTED",
            "PROBLEMATIC",
        }

    def test_operation_type_values(self) -> None:
        vals = {o.value for o in OperationType}
        assert vals == {"incoming", "outgoing", "data"}

    def test_contact_status_values(self) -> None:
        vals = {c.value for c in ContactStatus}
        assert vals == {"unconfirmed", "awaiting", "confirmed", "rejected"}


class TestTableNames:
    """Every V2 table is prefixed with v2_."""

    @pytest.mark.parametrize(
        "model,expected",
        [
            (UserV2, "v2_users"),
            (PaymailV2, "v2_paymails"),
            (AddressV2, "v2_addresses"),
            (TrackedTransaction, "v2_tracked_transactions"),
            (TrackedOutput, "v2_tracked_outputs"),
            (TxInput, "v2_tx_inputs"),
            (UserUTXO, "v2_user_utxos"),
            (Operation, "v2_operations"),
            (DataV2, "v2_data"),
            (UserContact, "v2_user_contacts"),
        ],
    )
    def test_table_name(self, model, expected) -> None:
        assert model.__tablename__ == expected


class TestAllModelsCollection:
    """ALL_V2_MODELS contains exactly 10 models."""

    def test_count(self) -> None:
        assert len(ALL_V2_MODELS) == 10

    def test_each_is_declarative(self) -> None:
        for model in ALL_V2_MODELS:
            assert hasattr(model, "__tablename__")


class TestColumnPresence:
    """Spot-check key columns on models."""

    def _columns(self, model) -> set[str]:
        mapper = inspect(model)
        return {c.key for c in mapper.columns}

    def test_user_columns(self) -> None:
        cols = self._columns(UserV2)
        assert {"id", "pub_key", "created_at", "updated_at"} <= cols

    def test_paymail_columns(self) -> None:
        cols = self._columns(PaymailV2)
        assert {"id", "alias", "domain", "public_name", "avatar", "user_id"} <= cols

    def test_tracked_transaction_columns(self) -> None:
        cols = self._columns(TrackedTransaction)
        assert {"id", "tx_status", "block_height", "block_hash", "raw_hex"} <= cols

    def test_tracked_output_columns(self) -> None:
        cols = self._columns(TrackedOutput)
        assert {"tx_id", "vout", "satoshis", "spending_tx"} <= cols

    def test_user_utxo_columns(self) -> None:
        cols = self._columns(UserUTXO)
        assert {"user_id", "tx_id", "vout", "satoshis", "bucket"} <= cols

    def test_operation_columns(self) -> None:
        cols = self._columns(Operation)
        assert {"tx_id", "user_id", "type", "value"} <= cols

    def test_data_v2_columns(self) -> None:
        cols = self._columns(DataV2)
        assert {"tx_id", "vout", "blob"} <= cols

    def test_user_contact_columns(self) -> None:
        cols = self._columns(UserContact)
        assert {"id", "full_name", "status", "user_id"} <= cols
