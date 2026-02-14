"""Overview dashboard — balance, recent transactions, health status."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.wallet_api import WalletAPI
from spv_wallet.desktop.widgets.common import (
    Card,
    Separator,
    balance_label,
    caption_label,
    heading_label,
    subheading_label,
)


class OverviewPanel(QWidget):
    """Dashboard panel — the landing page after wallet opens.

    Layout:
        [Balance display (big, gold)]
        [Card: recent transactions summary (last 5)]
        [Card: engine health status]
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

        layout.addWidget(heading_label("Wallet Overview"))

        # Balance card
        bal_card = Card()
        bal_card.layout().addWidget(subheading_label("Total Balance"))
        self._balance_lbl = balance_label("0")
        bal_card.layout().addWidget(self._balance_lbl)
        self._balance_sub = caption_label("satoshis")
        self._balance_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bal_card.layout().addWidget(self._balance_sub)
        layout.addWidget(bal_card)

        layout.addWidget(Separator())

        # Recent transactions card
        tx_card = Card()
        tx_card.layout().addWidget(subheading_label("Recent Transactions"))
        self._tx_table = QTableWidget(0, 4)
        self._tx_table.setHorizontalHeaderLabels(["Status", "Direction", "Amount", "Date"])
        self._tx_table.setMaximumHeight(200)
        self._tx_table.verticalHeader().setVisible(False)
        self._tx_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        from PySide6.QtWidgets import QHeaderView  # noqa: PLC0415

        self._tx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tx_card.layout().addWidget(self._tx_table)
        layout.addWidget(tx_card)

        # Health card
        health_card = Card()
        health_card.layout().addWidget(subheading_label("Engine Status"))
        self._health_row = QHBoxLayout()
        self._health_labels: dict[str, QLabel] = {}
        for component in ("engine", "datastore", "cache", "chain"):
            lbl = caption_label(f"{component}: —")
            self._health_labels[component] = lbl
            self._health_row.addWidget(lbl)
        health_card.layout().addLayout(self._health_row)
        layout.addWidget(health_card)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._api.balance_updated.connect(self._on_balance)
        self._api.tx_list_updated.connect(self._on_tx_list)
        self._api.health_updated.connect(self._on_health)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_balance(self, satoshis: int) -> None:
        self._balance_lbl.setText(f"{satoshis:,}")
        self._balance_sub.setText("satoshis")

    @Slot(list)
    def _on_tx_list(self, txs: list[dict[str, Any]]) -> None:
        recent = txs[:5]
        self._tx_table.setRowCount(len(recent))
        for row, tx in enumerate(recent):
            self._tx_table.setItem(row, 0, QTableWidgetItem(tx.get("status", "")))
            self._tx_table.setItem(row, 1, QTableWidgetItem(tx.get("direction", "")))
            self._tx_table.setItem(
                row, 2, QTableWidgetItem(f"{tx.get('total_value', 0):,}"),
            )
            self._tx_table.setItem(row, 3, QTableWidgetItem(tx.get("created_at", "")))

    @Slot(dict)
    def _on_health(self, status: dict[str, str]) -> None:
        for component, lbl in self._health_labels.items():
            state = status.get(component, "unknown")
            colour = {
                "ok": "#22c55e",
                "error": "#ef4444",
                "not_connected": "#f59e0b",
                "not_initialized": "#ef4444",
            }.get(state, "#969696")
            lbl.setText(f"{component}: {state}")
            lbl.setStyleSheet(f"color: {colour};")

    def refresh(self) -> None:
        """Trigger data refresh for all sections."""
        self._api.refresh_balance()
        self._api.refresh_transactions()
        self._api.check_health()
