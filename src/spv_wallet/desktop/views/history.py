"""Transaction history list view — sortable table with status pills."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.wallet_api import WalletAPI
from spv_wallet.desktop.widgets.common import heading_label

# Column definitions
_COLUMNS = ["Status", "Direction", "Amount (sats)", "Fee", "Date", "Block"]


class HistoryPanel(QWidget):
    """Transaction history table panel.

    Shows recent transactions for the active xPub with status,
    direction, amount, fee, date, and block height.
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

        # Header
        header_row = QHBoxLayout()
        header_row.addWidget(heading_label("Transactions"))
        header_row.addStretch()

        self._refresh_btn = QPushButton("↻ Refresh")
        self._refresh_btn.setFixedWidth(100)
        header_row.addWidget(self._refresh_btn)
        layout.addLayout(header_row)

        # Table
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table, stretch=1)

    def _connect_signals(self) -> None:
        self._api.tx_list_updated.connect(self._on_tx_list)
        self._refresh_btn.clicked.connect(self._api.refresh_transactions)

    @Slot(list)
    def _on_tx_list(self, txs: list[dict[str, Any]]) -> None:
        """Populate the table with transaction data."""
        self._table.setRowCount(len(txs))
        for row, tx in enumerate(txs):
            self._table.setItem(row, 0, QTableWidgetItem(tx.get("status", "")))
            self._table.setItem(row, 1, QTableWidgetItem(tx.get("direction", "")))
            self._table.setItem(row, 2, QTableWidgetItem(f"{tx.get('total_value', 0):,}"))
            self._table.setItem(row, 3, QTableWidgetItem(str(tx.get("fee", 0))))
            self._table.setItem(row, 4, QTableWidgetItem(tx.get("created_at", "")))
            block = tx.get("block_height", 0)
            self._table.setItem(
                row, 5, QTableWidgetItem(str(block) if block else "—"),
            )

            # Colour-code status
            status_item = self._table.item(row, 0)
            status = tx.get("status", "")
            if status == "confirmed":
                status_item.setForeground(Qt.GlobalColor.green)
            elif status == "unconfirmed":
                status_item.setForeground(Qt.GlobalColor.yellow)
            elif status in ("canceled", "failed"):
                status_item.setForeground(Qt.GlobalColor.red)

    def refresh(self) -> None:
        """Trigger a data refresh."""
        self._api.refresh_transactions()
