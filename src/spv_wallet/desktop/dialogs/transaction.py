"""Transaction detail dialog — inspect a single transaction."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class TransactionDialog(QDialog):
    """Detail view for a single transaction.

    Displays status, direction, amount, fee, block height,
    timestamps, and raw hex if available.
    """

    def __init__(
        self,
        tx_data: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transaction Details")
        self.setMinimumWidth(550)
        self._tx = tx_data
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Form fields
        form = QFormLayout()
        form.setSpacing(8)

        txid = self._tx.get("id", "Unknown")
        txid_label = QLabel(txid)
        txid_label.setWordWrap(True)
        txid_label.setTextInteractionFlags(
            txid_label.textInteractionFlags() | txid_label.textInteractionFlags().SelectableByMouse,
        )
        form.addRow("Transaction ID:", txid_label)

        form.addRow(
            "Status:",
            QLabel(self._tx.get("status", "unknown")),
        )
        form.addRow(
            "Direction:",
            QLabel(self._tx.get("direction", "unknown")),
        )
        form.addRow(
            "Amount (sats):",
            QLabel(f"{self._tx.get('total_value', 0):,}"),
        )
        form.addRow("Fee (sats):", QLabel(str(self._tx.get("fee", 0))))

        block = self._tx.get("block_height", 0)
        form.addRow(
            "Block Height:",
            QLabel(str(block) if block else "Unconfirmed"),
        )
        form.addRow(
            "Created:",
            QLabel(self._tx.get("created_at", "")),
        )

        layout.addLayout(form)

        # Raw hex (if available)
        hex_data = self._tx.get("hex", "")
        if hex_data:
            layout.addWidget(QLabel("Raw Hex:"))
            hex_edit = QTextEdit()
            hex_edit.setPlainText(hex_data)
            hex_edit.setReadOnly(True)
            hex_edit.setMaximumHeight(100)
            hex_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
            layout.addWidget(hex_edit)

        # Buttons
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy TXID")
        copy_btn.clicked.connect(
            lambda: self._copy_text(txid),
        )
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()

        close_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
        )
        close_box.rejected.connect(self.reject)
        btn_row.addWidget(close_box)
        layout.addLayout(btn_row)

    @staticmethod
    def _copy_text(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
