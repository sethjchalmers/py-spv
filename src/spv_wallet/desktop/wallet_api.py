"""WalletAPI — async bridge between the PySide6 GUI and the SPV engine.

The Qt event loop is single-threaded, so all engine I/O runs in a background
``QThread`` via ``AsyncWorker``.  Results are delivered back to the GUI thread
through Qt signals, keeping the UI responsive.

Architecture (portable to mobile):
    ┌─────────────┐  signal   ┌────────────┐  await   ┌──────────────┐
    │  Qt Widgets  │ ◄──────► │  WalletAPI  │ ──────► │ SPVWalletEngine│
    └─────────────┘           └────────────┘          └──────────────┘
     (main thread)            (signal bridge)          (async workers)
"""

from __future__ import annotations

import asyncio
import traceback
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Async worker — runs a coroutine on a background thread
# ---------------------------------------------------------------------------


class _WorkerSignals(QObject):
    """Signals emitted by ``AsyncWorker``."""

    finished = Signal(object)  # result value
    error = Signal(str, str)  # (title, detail)


class AsyncWorker(QRunnable):
    """Run an ``async`` coroutine on a ``QThreadPool`` thread.

    The result is delivered via ``signals.finished``; errors via ``signals.error``.
    """

    def __init__(self, coro_fn: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.coro_fn = coro_fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Execute the coroutine (called by QThreadPool)."""
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.coro_fn(*self.args, **self.kwargs))
            self.signals.finished.emit(result)
        except Exception:
            tb = traceback.format_exc()
            self.signals.error.emit("Operation failed", tb)
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# WalletAPI — the GUI ↔ Engine bridge
# ---------------------------------------------------------------------------


class WalletAPI(QObject):
    """High-level wallet operations exposed to the GUI via Qt signals.

    Signals (connect these in your widgets):
        engine_ready         — engine initialised successfully
        engine_closed        — engine shut down
        balance_updated(int) — current confirmed balance in satoshis
        tx_list_updated(list)— list[dict] of recent transactions
        address_generated(str, str) — (address, derivation_path)
        draft_created(dict)  — draft transaction details
        tx_recorded(dict)    — recorded transaction details
        health_updated(dict) — engine health check results
        error_occurred(str, str) — (title, detail)
    """

    # Lifecycle
    engine_ready = Signal()
    engine_closed = Signal()

    # Data
    balance_updated = Signal(int)
    tx_list_updated = Signal(list)
    address_generated = Signal(str, str)  # address, derivation path
    draft_created = Signal(dict)
    tx_recorded = Signal(dict)
    health_updated = Signal(dict)
    xpub_registered = Signal(str)  # xpub_id
    destinations_updated = Signal(list)  # list[dict] of destinations/keys
    utxos_updated = Signal(list)  # list[dict] of UTXOs
    contacts_updated = Signal(list)  # list[dict] of contacts

    # Errors
    error_occurred = Signal(str, str)  # title, detail

    # WoC scanning
    woc_balance_updated = Signal(dict)  # {"confirmed": int, "unconfirmed": int}
    woc_utxos_updated = Signal(list)  # list[dict] from WhatsOnChain
    network_changed = Signal(str)  # "mainnet" or "testnet"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine: Any = None  # SPVWalletEngine (lazy import)
        self._pool = QThreadPool.globalInstance()
        self._raw_xpub: str = ""  # raw xPub Base58 string
        self._xpub_id: str = ""  # sha256 hash of xPub
        self._testnet: bool = False  # network mode
        self._woc: Any = None  # WoCClient (lazy import)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        """Check if the engine is initialized."""
        return self._engine is not None and self._engine.is_initialized

    @property
    def is_testnet(self) -> bool:
        """Whether the wallet is in testnet mode."""
        return self._testnet

    @property
    def xpub_id(self) -> str:
        """The active xPub ID (sha256 hash)."""
        return self._xpub_id

    @property
    def raw_xpub(self) -> str:
        """The raw xPub Base58 string."""
        return self._raw_xpub

    # ------------------------------------------------------------------
    # Internal: enqueue async work
    # ------------------------------------------------------------------

    def _run(
        self,
        coro_fn: Any,
        *args: Any,
        on_done: Any = None,
        **kwargs: Any,
    ) -> None:
        """Enqueue an async coroutine on the thread pool."""
        worker = AsyncWorker(coro_fn, *args, **kwargs)
        worker.signals.error.connect(self.error_occurred)
        if on_done:
            worker.signals.finished.connect(on_done)
        self._pool.start(worker)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, wallet_path: str | Path, *, testnet: bool = False) -> None:
        """Initialize the engine with a wallet file (SQLite).

        Args:
            wallet_path: Path to the wallet ``.sqlite`` database file.
            testnet: If True, run in testnet mode.
        """
        self._testnet = testnet
        self._run(
            self._do_initialize, str(wallet_path), testnet, on_done=self._on_initialized
        )

    async def _do_initialize(self, wallet_path: str, testnet: bool) -> bool:
        from spv_wallet.config.settings import (
            AppConfig,
            DatabaseConfig,
            DatabaseEngine,
            Network,
        )
        from spv_wallet.engine.client import SPVWalletEngine

        dsn = f"sqlite+aiosqlite:///{wallet_path}"
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn=dsn),
            network=Network.TESTNET if testnet else Network.MAINNET,
        )
        self._engine = SPVWalletEngine(config)
        await self._engine.initialize()

        # Create WoC client for live chain data
        from spv_wallet.chain.woc.client import WoCClient

        self._woc = WoCClient(testnet=testnet)
        await self._woc.connect()
        return True

    def _on_initialized(self, _result: Any) -> None:
        self.engine_ready.emit()

    def shutdown(self) -> None:
        """Close the engine gracefully."""
        if self._engine is not None:
            self._run(self._do_shutdown, on_done=self._on_shutdown)

    async def _do_shutdown(self) -> bool:
        if self._woc:
            await self._woc.close()
            self._woc = None
        if self._engine:
            await self._engine.close()
        return True

    def _on_shutdown(self, _result: Any) -> None:
        self._engine = None
        self._woc = None
        self.engine_closed.emit()

    # ------------------------------------------------------------------
    # Wallet setup
    # ------------------------------------------------------------------

    def register_xpub(self, raw_xpub: str) -> None:
        """Register an xPub with the engine.

        Args:
            raw_xpub: Base58-encoded extended public key.
        """
        self._raw_xpub = raw_xpub
        self._run(self._do_register_xpub, raw_xpub, on_done=self._on_xpub_registered)

    async def _do_register_xpub(self, raw_xpub: str) -> str:

        xpub = await self._engine.xpub_service.new_xpub(raw_xpub)
        return xpub.id

    def _on_xpub_registered(self, xpub_id_val: str) -> None:
        self._xpub_id = xpub_id_val
        self.xpub_registered.emit(xpub_id_val)

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    def refresh_balance(self) -> None:
        """Fetch the current balance for the active xPub."""
        if not self._xpub_id:
            return
        self._run(self._do_get_balance, self._xpub_id, on_done=self._on_balance)

    async def _do_get_balance(self, xpub_id_val: str) -> int:
        return await self._engine.utxo_service.get_balance(xpub_id_val)

    def _on_balance(self, balance: int) -> None:
        self.balance_updated.emit(balance)

    # ------------------------------------------------------------------
    # Addresses (receive)
    # ------------------------------------------------------------------

    def generate_address(self) -> None:
        """Derive a new receiving address for the active xPub."""
        if not self._raw_xpub:
            return
        self._run(
            self._do_generate_address,
            self._raw_xpub,
            on_done=self._on_address,
        )

    async def _do_generate_address(self, raw_xpub: str) -> tuple[str, str]:
        dest = await self._engine.destination_service.new_destination(
            raw_xpub,
            chain=0,
        )
        path = f"m/44'/236'/0'/0/{dest.num}"
        return (dest.address, path)

    def _on_address(self, result: tuple[str, str]) -> None:
        self.address_generated.emit(result[0], result[1])

    # ------------------------------------------------------------------
    # Destinations (keys)
    # ------------------------------------------------------------------

    def refresh_destinations(self) -> None:
        """Fetch all derived destinations for the active xPub."""
        if not self._xpub_id:
            return
        self._run(
            self._do_get_destinations,
            self._xpub_id,
            on_done=self._on_destinations,
        )

    async def _do_get_destinations(
        self,
        xpub_id_val: str,
    ) -> list[dict[str, Any]]:
        dests = await self._engine.destination_service.get_destinations_by_xpub(
            xpub_id_val,
        )
        return [
            {
                "id": d.id,
                "address": d.address,
                "type": d.type,
                "chain": d.chain,
                "num": d.num,
                "locking_script": d.locking_script,
            }
            for d in dests
        ]

    def _on_destinations(self, dests: list[dict[str, Any]]) -> None:
        self.destinations_updated.emit(dests)

    # ------------------------------------------------------------------
    # UTXOs
    # ------------------------------------------------------------------

    def refresh_utxos(self, *, unspent_only: bool = False) -> None:
        """Fetch UTXOs for the active xPub.

        Args:
            unspent_only: If *True*, return only unspent outputs.
        """
        if not self._xpub_id:
            return
        self._run(
            self._do_get_utxos,
            self._xpub_id,
            unspent_only,
            on_done=self._on_utxos,
        )

    async def _do_get_utxos(
        self,
        xpub_id_val: str,
        unspent_only: bool,
    ) -> list[dict[str, Any]]:
        utxos = await self._engine.utxo_service.get_utxos(
            xpub_id=xpub_id_val,
            unspent_only=unspent_only,
        )
        return [
            {
                "id": u.id,
                "transaction_id": u.transaction_id,
                "output_index": u.output_index,
                "satoshis": u.satoshis,
                "type": u.type,
                "spending_tx_id": u.spending_tx_id,
                "destination_id": u.destination_id,
                "is_spent": u.is_spent,
            }
            for u in utxos
        ]

    def _on_utxos(self, utxos: list[dict[str, Any]]) -> None:
        self.utxos_updated.emit(utxos)

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------

    def refresh_contacts(self) -> None:
        """Fetch all contacts for the active xPub."""
        if not self._xpub_id:
            return
        self._run(
            self._do_get_contacts,
            self._xpub_id,
            on_done=self._on_contacts,
        )

    async def _do_get_contacts(
        self,
        xpub_id_val: str,
    ) -> list[dict[str, Any]]:
        contacts = await self._engine.contact_service.search_contacts(
            xpub_id=xpub_id_val,
        )
        return [
            {
                "id": c.id,
                "full_name": c.full_name,
                "paymail": c.paymail,
                "pub_key": c.pub_key,
                "status": c.status,
            }
            for c in contacts
        ]

    def _on_contacts(self, contacts: list[dict[str, Any]]) -> None:
        self.contacts_updated.emit(contacts)

    def create_contact(
        self,
        paymail: str,
        full_name: str = "",
        pub_key: str = "",
    ) -> None:
        """Create a new contact.

        Args:
            paymail: Contact paymail address.
            full_name: Display name.
            pub_key: Public key hex string.
        """
        if not self._xpub_id:
            return
        self._run(
            self._do_create_contact,
            self._xpub_id,
            paymail,
            full_name,
            pub_key,
            on_done=lambda _: self.refresh_contacts(),
        )

    async def _do_create_contact(
        self,
        xpub_id_val: str,
        paymail: str,
        full_name: str,
        pub_key: str,
    ) -> dict[str, Any]:
        c = await self._engine.contact_service.create_contact(
            xpub_id_val,
            paymail,
            full_name=full_name,
            pub_key=pub_key,
        )
        return {"id": c.id, "paymail": c.paymail, "status": c.status}

    def update_contact_status(
        self,
        contact_id: str,
        new_status: str,
    ) -> None:
        """Change a contact's status.

        Args:
            contact_id: The contact ID.
            new_status: Target status (awaiting / confirmed / rejected).
        """
        self._run(
            self._do_update_contact_status,
            contact_id,
            new_status,
            on_done=lambda _: self.refresh_contacts(),
        )

    async def _do_update_contact_status(
        self,
        contact_id: str,
        new_status: str,
    ) -> dict[str, Any]:
        c = await self._engine.contact_service.update_status(
            contact_id,
            new_status,
        )
        return {"id": c.id, "status": c.status}

    def delete_contact(self, contact_id: str) -> None:
        """Delete a contact.

        Args:
            contact_id: The contact ID to delete.
        """
        self._run(
            self._do_delete_contact,
            contact_id,
            on_done=lambda _: self.refresh_contacts(),
        )

    async def _do_delete_contact(self, contact_id: str) -> bool:
        await self._engine.contact_service.delete_contact(contact_id)
        return True

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def refresh_transactions(self) -> None:
        """Fetch recent transactions for the active xPub."""
        if not self._xpub_id:
            return
        self._run(
            self._do_get_transactions,
            self._xpub_id,
            on_done=self._on_tx_list,
        )

    async def _do_get_transactions(
        self,
        xpub_id_val: str,
    ) -> list[dict[str, Any]]:
        txs = await self._engine.transaction_service.get_transactions(
            xpub_id_val,
        )
        return [
            {
                "id": tx.id,
                "status": tx.status,
                "direction": tx.direction,
                "total_value": tx.total_value,
                "fee": tx.fee,
                "created_at": str(tx.created_at) if tx.created_at else "",
                "block_height": tx.block_height or 0,
            }
            for tx in txs
        ]

    def _on_tx_list(self, txs: list[dict[str, Any]]) -> None:
        self.tx_list_updated.emit(txs)

    # ------------------------------------------------------------------
    # Send (draft → record)
    # ------------------------------------------------------------------

    def create_draft(
        self,
        to_address: str,
        satoshis: int,
        *,
        op_return: str = "",
    ) -> None:
        """Create a draft transaction.

        Args:
            to_address: Recipient P2PKH address.
            satoshis: Amount to send in satoshis.
            op_return: Optional OP_RETURN data string.
        """
        if not self._xpub_id:
            return

        outputs: list[dict[str, Any]] = [{"to": to_address, "satoshis": satoshis}]
        if op_return:
            outputs.append({"op_return": op_return})

        self._run(
            self._do_create_draft,
            self._xpub_id,
            outputs,
            on_done=self._on_draft_created,
        )

    async def _do_create_draft(
        self,
        xpub_id_val: str,
        outputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        draft = await self._engine.transaction_service.new_transaction(
            xpub_id_val,
            outputs=outputs,
        )
        return {
            "draft_id": draft.id,
            "status": draft.status,
            "fee": draft.fee,
            "outputs": outputs,
        }

    def _on_draft_created(self, info: dict[str, Any]) -> None:
        self.draft_created.emit(info)

    def record_transaction(self, hex_body: str, draft_id: str = "") -> None:
        """Record a signed transaction.

        Args:
            hex_body: Signed transaction hex.
            draft_id: Draft ID (if created via create_draft).
        """
        if not self._xpub_id:
            return
        self._run(
            self._do_record_tx,
            self._xpub_id,
            hex_body,
            draft_id,
            on_done=self._on_tx_recorded,
        )

    async def _do_record_tx(
        self,
        xpub_id_val: str,
        hex_body: str,
        draft_id: str,
    ) -> dict[str, Any]:
        tx = await self._engine.transaction_service.record_transaction(
            xpub_id_val,
            hex_body,
            draft_id=draft_id,
        )
        return {
            "id": tx.id,
            "status": tx.status,
            "direction": tx.direction,
            "total_value": tx.total_value,
            "fee": tx.fee,
        }

    def _on_tx_recorded(self, info: dict[str, Any]) -> None:
        self.tx_recorded.emit(info)

    # ------------------------------------------------------------------
    # WhatsOnChain — live chain scanning
    # ------------------------------------------------------------------

    def scan_address_balance(self, address: str) -> None:
        """Fetch balance for an address via WhatsOnChain.

        Args:
            address: P2PKH address to scan.
        """
        if not self._woc:
            return
        self._run(self._do_woc_balance, address, on_done=self._on_woc_balance)

    async def _do_woc_balance(self, address: str) -> dict[str, Any]:
        bal = await self._woc.get_balance(address)
        return {"confirmed": bal.confirmed, "unconfirmed": bal.unconfirmed}

    def _on_woc_balance(self, info: dict[str, Any]) -> None:
        self.woc_balance_updated.emit(info)

    def scan_address_utxos(self, address: str) -> None:
        """Fetch UTXOs for an address via WhatsOnChain.

        Args:
            address: P2PKH address to scan.
        """
        if not self._woc:
            return
        self._run(self._do_woc_utxos, address, on_done=self._on_woc_utxos)

    async def _do_woc_utxos(self, address: str) -> list[dict[str, Any]]:
        utxos = await self._woc.get_utxos(address)
        return [
            {
                "tx_hash": u.tx_hash,
                "tx_pos": u.tx_pos,
                "value": u.value,
                "height": u.height,
            }
            for u in utxos
        ]

    def _on_woc_utxos(self, utxos: list[dict[str, Any]]) -> None:
        self.woc_utxos_updated.emit(utxos)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_health(self) -> None:
        """Run engine health check."""
        if not self._engine:
            return
        self._run(self._do_health, on_done=self._on_health)

    async def _do_health(self) -> dict[str, str]:
        return await self._engine.health_check()

    def _on_health(self, status: dict[str, str]) -> None:
        self.health_updated.emit(status)
