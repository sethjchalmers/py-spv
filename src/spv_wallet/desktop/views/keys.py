"""Key / address management table view."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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

_COLUMNS = ["Address", "Type", "Chain", "Index", "Script Type"]


class KeysPanel(QWidget):
    """Derived keys/addresses table.

    Shows all destinations (derived addresses) for the active xPub,
    with chain (external/internal), derivation index, and script type.
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
        header_row.addWidget(heading_label("Keys / Addresses"))
        header_row.addStretch()

        self._derive_btn = QPushButton("Derive New Address")
        self._derive_btn.setFixedWidth(180)
        header_row.addWidget(self._derive_btn)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedWidth(100)
        header_row.addWidget(self._refresh_btn)
        layout.addLayout(header_row)

        # Summary
        self._count_label = caption_label("0 addresses")
        layout.addWidget(self._count_label)

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
        self._api.destinations_updated.connect(self._on_destinations)
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._derive_btn.clicked.connect(self._on_derive)
        self._table.customContextMenuRequested.connect(
            self._on_context_menu,
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_destinations(self, dests: list[dict[str, Any]]) -> None:
        self._table.setRowCount(len(dests))
        for row, d in enumerate(dests):
            self._table.setItem(row, 0, QTableWidgetItem(d.get("address", "")))
            self._table.setItem(row, 1, QTableWidgetItem(d.get("type", "")))
            chain = d.get("chain", 0)
            chain_label = "External" if chain == 0 else "Internal"
            self._table.setItem(row, 2, QTableWidgetItem(chain_label))
            self._table.setItem(row, 3, QTableWidgetItem(str(d.get("num", 0))))
            self._table.setItem(
                row,
                4,
                QTableWidgetItem(d.get("script_type", "P2PKH")),
            )
        self._count_label.setText(f"{len(dests)} addresses")

    @Slot()
    def _on_refresh(self) -> None:
        self._api.refresh_destinations()

    @Slot()
    def _on_derive(self) -> None:
        self._derive_btn.setEnabled(False)
        self._api.generate_address()
        self._derive_btn.setEnabled(True)
        self._api.refresh_destinations()

    def _on_context_menu(self, pos: Any) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        address = item.text()

        menu = QMenu(self)
        copy_action = menu.addAction("Copy Address")
        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == copy_action:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(address)

    def refresh(self) -> None:
        """Trigger data refresh."""
        self._api.refresh_destinations()
