"""Send BSV form view — address, amount, optional OP_RETURN, confirm."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.wallet_api import WalletAPI
from spv_wallet.desktop.widgets.amount_edit import AmountEdit
from spv_wallet.desktop.widgets.common import Card, Separator, caption_label, heading_label


class SendPanel(QWidget):
    """Panel for composing and sending BSV transactions.

    Layout:
        [Heading]
        [Card: address input]
        [Card: amount input]
        [Card: optional OP_RETURN]
        [Send button]
        [Status area]
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

        layout.addWidget(heading_label("Send BSV"))

        # Address card
        addr_card = Card()
        addr_card.layout().addWidget(QLabel("Recipient address"))
        self._addr_input = QLineEdit()
        self._addr_input.setPlaceholderText("Enter BSV address (P2PKH)")
        self._addr_input.setProperty("role", "mono")
        addr_card.layout().addWidget(self._addr_input)
        layout.addWidget(addr_card)

        # Amount card
        amt_card = Card()
        amt_card.layout().addWidget(QLabel("Amount"))
        self._amount = AmountEdit()
        amt_card.layout().addWidget(self._amount)
        layout.addWidget(amt_card)

        # OP_RETURN card (optional)
        op_card = Card()
        op_card.layout().addWidget(QLabel("OP_RETURN data (optional)"))
        self._op_return_input = QLineEdit()
        self._op_return_input.setPlaceholderText("Text or hex data")
        op_card.layout().addWidget(self._op_return_input)
        layout.addWidget(op_card)

        layout.addWidget(Separator())

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(100)
        btn_row.addWidget(self._clear_btn)

        self._send_btn = QPushButton("Create Draft")
        self._send_btn.setProperty("role", "primary")
        self._send_btn.setFixedWidth(160)
        btn_row.addWidget(self._send_btn)
        layout.addLayout(btn_row)

        # Status
        self._status = caption_label("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._send_btn.clicked.connect(self._on_send)
        self._clear_btn.clicked.connect(self._on_clear)
        self._api.draft_created.connect(self._on_draft_created)
        self._api.error_occurred.connect(self._on_error)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_send(self) -> None:
        address = self._addr_input.text().strip()
        satoshis = self._amount.satoshis()

        if not address:
            QMessageBox.warning(self, "Missing address", "Please enter a recipient address.")
            return
        if satoshis <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be greater than zero.")
            return

        self._send_btn.setEnabled(False)
        self._status.setText("Creating draft…")

        op_return = self._op_return_input.text().strip()
        self._api.create_draft(address, satoshis, op_return=op_return)

    @Slot(dict)
    def _on_draft_created(self, info: dict[str, Any]) -> None:
        self._send_btn.setEnabled(True)
        draft_id = info.get("draft_id", "?")
        fee = info.get("fee", 0)
        self._status.setText(f"Draft created: {draft_id[:12]}… (fee: {fee} sats)")
        QMessageBox.information(
            self, "Draft Created",
            f"Transaction draft created.\n\n"
            f"Draft ID: {draft_id}\n"
            f"Fee: {fee} sats\n\n"
            f"Sign and broadcast to complete.",
        )

    @Slot(str, str)
    def _on_error(self, title: str, detail: str) -> None:
        self._send_btn.setEnabled(True)
        self._status.setText(f"Error: {title}")

    @Slot()
    def _on_clear(self) -> None:
        self._addr_input.clear()
        self._amount.clear()
        self._op_return_input.clear()
        self._status.setText("")
