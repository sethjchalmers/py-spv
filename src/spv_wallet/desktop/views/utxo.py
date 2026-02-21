"""UTXO browser view — list and inspect unspent transaction outputs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.widgets.common import caption_label, heading_label

if TYPE_CHECKING:
    from spv_wallet.desktop.wallet_api import WalletAPI

_COLUMNS = [
    "TXID:Vout",
    "Amount (sats)",
    "Script Type",
    "Status",
    "Destination",
]


class UTXOPanel(QWidget):
    """UTXO browser panel.

    Lists all tracked UTXOs for the active xPub with filtering
    for unspent-only and context menu for copying.
    """

    def __init__(self, api: WalletAPI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(heading_label("UTXOs"))
        header_row.addStretch()

        self._unspent_only = QCheckBox("Unspent only")
        self._unspent_only.setChecked(True)
        header_row.addWidget(self._unspent_only)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedWidth(100)
        header_row.addWidget(self._refresh_btn)
        layout.addLayout(header_row)

        # Summary
        self._summary = caption_label("0 UTXOs  |  0 sats")
        layout.addWidget(self._summary)

        # Table
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(_COLUMNS)):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table, stretch=1)

    def _connect_signals(self) -> None:
        self._api.utxos_updated.connect(self._on_utxos)
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._unspent_only.toggled.connect(self._on_refresh)
        self._table.customContextMenuRequested.connect(
            self._on_context_menu,
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_utxos(self, utxos: list[dict[str, Any]]) -> None:
        self._table.setRowCount(len(utxos))
        total_sats = 0
        for row, u in enumerate(utxos):
            utxo_id = u.get("id", "")
            sats = u.get("satoshis", 0)
            total_sats += sats

            self._table.setItem(row, 0, QTableWidgetItem(utxo_id))
            self._table.setItem(row, 1, QTableWidgetItem(f"{sats:,}"))
            self._table.setItem(row, 2, QTableWidgetItem(u.get("type", "P2PKH")))

            is_spent = u.get("is_spent", False)
            status_text = "Spent" if is_spent else "Unspent"
            status_item = QTableWidgetItem(status_text)
            if is_spent:
                status_item.setForeground(Qt.GlobalColor.red)
            else:
                status_item.setForeground(Qt.GlobalColor.green)
            self._table.setItem(row, 3, status_item)

            dest = u.get("destination_id", "")
            display = dest[:16] + "..." if len(dest) > 16 else dest
            self._table.setItem(row, 4, QTableWidgetItem(display))

        self._summary.setText(f"{len(utxos)} UTXOs  |  {total_sats:,} sats")

    @Slot()
    def _on_refresh(self) -> None:
        self._api.refresh_utxos(
            unspent_only=self._unspent_only.isChecked(),
        )

    def _on_context_menu(self, pos: Any) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        utxo_id = item.text()

        menu = QMenu(self)
        copy_id = menu.addAction("Copy UTXO ID")
        copy_txid = menu.addAction("Copy TXID")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == copy_id:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(utxo_id)
        elif action == copy_txid:
            txid = utxo_id.split(":")[0] if ":" in utxo_id else utxo_id
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(txid)

    def refresh(self) -> None:
        """Trigger data refresh."""
        self._api.refresh_utxos(
            unspent_only=self._unspent_only.isChecked(),
        )
