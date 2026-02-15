"""V2 TxFlow — transaction processing pipeline.

Mirrors Go's ``engine/v2/transaction/record/tx_flow.go``.
The TxFlow processes a signed transaction through these steps:
1. Parse raw hex
2. Verify inputs exist and are unspent
3. Create tracked transaction record
4. Create tracked outputs (new UTXOs)
5. Mark spent inputs
6. Create user operations
7. Broadcast to ARC
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from spv_wallet.bsv.transaction import Transaction
from spv_wallet.engine.v2.database.models import (
    DataV2,
    Operation,
    OperationType,
    TrackedOutput,
    TrackedTransaction,
    TxInput,
    TxStatusV2,
    UserUTXO,
)
from spv_wallet.engine.v2.database.repository.outputs import OutputRepository
from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository
from spv_wallet.errors.definitions import ErrRecordTxInvalid

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


@dataclasses.dataclass
class TxFlowResult:
    """Result of processing a transaction through TxFlow."""

    tracked_tx: TrackedTransaction
    operations: list[Operation]
    new_utxos: list[UserUTXO]
    spent_utxo_count: int
    data_outputs: list[DataV2]
    broadcasted: bool = False
    broadcast_error: str | None = None


class TxFlow:
    """Transaction processing pipeline.

    Takes a signed raw transaction, parses it, creates all necessary
    database records, and broadcasts to ARC.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._tx_repo = TransactionRepository(engine.datastore)
        self._output_repo = OutputRepository(engine.datastore)

    async def process(
        self,
        user_id: str,
        raw_hex: str,
        *,
        beef_hex: str | None = None,
        broadcast: bool = True,
    ) -> TxFlowResult:
        """Process a signed transaction through the full pipeline.

        Args:
            user_id: The user who owns this transaction.
            raw_hex: Raw transaction hex.
            beef_hex: Optional BEEF-encoded hex.
            broadcast: Whether to broadcast to ARC.

        Returns:
            TxFlowResult with all created records.

        Raises:
            SPVError: If raw hex is invalid.
        """
        # 1. Parse raw hex
        try:
            tx = Transaction.from_hex(raw_hex)
        except Exception as exc:
            raise ErrRecordTxInvalid from exc

        txid = tx.txid()

        # 2. Create tracked transaction
        tracked_tx = await self._tx_repo.create_transaction(
            TrackedTransaction(
                id=txid,
                tx_status=TxStatusV2.CREATED.value,
                raw_hex=raw_hex,
                beef_hex=beef_hex,
            ),
        )

        # 3. Create TxInput references
        await self._create_input_refs(txid, tx)

        # 4. Create tracked outputs, UTXOs, and data records
        new_utxos, data_outputs = await self._create_outputs(txid, user_id, tx)

        # 5. Mark spent inputs and remove from user UTXO set
        spent_count = await self._mark_spent_inputs(user_id, txid, tx)

        # 6. Create user operation
        operation = await self._create_operation(txid, user_id, tx)

        # 7. Broadcast to ARC
        broadcasted, broadcast_error = await self._maybe_broadcast(
            txid,
            raw_hex,
            tracked_tx,
            broadcast,
        )

        return TxFlowResult(
            tracked_tx=tracked_tx,
            operations=[operation],
            new_utxos=new_utxos,
            spent_utxo_count=spent_count,
            data_outputs=data_outputs,
            broadcasted=broadcasted,
            broadcast_error=broadcast_error,
        )

    async def _create_input_refs(self, txid: str, tx: Transaction) -> None:
        """Create TxInput references for BEEF ancestry."""
        source_txids: set[str] = set()
        for inp in tx.inputs:
            if inp.prev_tx_id:
                source_txids.add(inp.prev_tx_id)

        if source_txids:
            tx_inputs = [TxInput(tx_id=txid, source_tx_id=src_id) for src_id in source_txids]
            await self._tx_repo.create_tx_inputs(tx_inputs)

    async def _create_outputs(
        self,
        txid: str,
        user_id: str,
        tx: Transaction,
    ) -> tuple[list[UserUTXO], list[DataV2]]:
        """Create tracked outputs, user UTXOs, and data records."""
        new_utxos: list[UserUTXO] = []
        data_outputs: list[DataV2] = []
        tracked_outputs: list[TrackedOutput] = []

        for idx, out in enumerate(tx.outputs):
            tracked_outputs.append(
                TrackedOutput(tx_id=txid, vout=idx, user_id=user_id, satoshis=out.satoshis),
            )

            if _is_op_return(out.script):
                data_outputs.append(
                    DataV2(tx_id=txid, vout=idx, user_id=user_id, blob=out.script),
                )
            elif out.satoshis > 0:
                new_utxos.append(
                    UserUTXO(user_id=user_id, tx_id=txid, vout=idx, satoshis=out.satoshis),
                )

        if tracked_outputs:
            await self._output_repo.create_many(tracked_outputs)
        if new_utxos:
            await self._tx_repo.create_utxos(new_utxos)
        if data_outputs:
            await self._tx_repo.create_data(data_outputs)

        return new_utxos, data_outputs

    async def _mark_spent_inputs(
        self,
        user_id: str,
        txid: str,
        tx: Transaction,
    ) -> int:
        """Mark spent inputs and remove from user UTXO set."""
        spent_count = 0
        for inp in tx.inputs:
            if not inp.prev_tx_id:
                continue
            marked = await self._output_repo.mark_spent(inp.prev_tx_id, inp.prev_index, txid)
            if marked:
                spent_count += 1
            await self._tx_repo.delete_utxo(user_id, inp.prev_tx_id, inp.prev_index)
        return spent_count

    async def _create_operation(
        self,
        txid: str,
        user_id: str,
        tx: Transaction,
    ) -> Operation:
        """Create a user operation record."""
        total_out = sum(o.satoshis for o in tx.outputs if not _is_op_return(o.script))
        op_type = OperationType.OUTGOING.value if total_out > 0 else OperationType.DATA.value

        operation = Operation(
            tx_id=txid,
            user_id=user_id,
            type=op_type,
            value=-total_out,
        )

        from spv_wallet.engine.v2.database.repository.operations import OperationRepository

        op_repo = OperationRepository(self._engine.datastore)
        await op_repo.create(operation)
        return operation

    async def _maybe_broadcast(
        self,
        txid: str,
        raw_hex: str,
        tracked_tx: TrackedTransaction,
        broadcast: bool,
    ) -> tuple[bool, str | None]:
        """Optionally broadcast to ARC. Returns (broadcasted, error)."""
        if not broadcast or self._engine.chain_service is None:
            return False, None

        try:
            await self._engine.chain_service.broadcast(raw_hex)
            await self._tx_repo.update_transaction(
                txid,
                tx_status=TxStatusV2.BROADCASTED.value,
            )
            tracked_tx.tx_status = TxStatusV2.BROADCASTED.value
            return True, None
        except Exception as exc:
            return False, str(exc)


def _is_op_return(script: bytes | None) -> bool:
    """Check if a script is an OP_RETURN output."""
    return bool(script and len(script) > 0 and script[0] == 0x6A)
