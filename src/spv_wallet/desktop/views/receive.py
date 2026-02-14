"""Receive BSV view — address display, QR code, copy-to-clipboard."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.wallet_api import WalletAPI
from spv_wallet.desktop.widgets.common import (
    Card,
    caption_label,
    heading_label,
    mono_label,
    subheading_label,
)
from spv_wallet.desktop.widgets.qr_widget import QRWidget


class ReceivePanel(QWidget):
    """Panel for generating and displaying a receiving address + QR code.

    Layout:
        [Heading]
        [Card: QR code]
        [Card: address (selectable) + copy button]
        [Card: derivation path]
        [Generate new address button]
    """

    def __init__(self, api: WalletAPI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._current_address = ""
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(heading_label("Receive BSV"))
        layout.addWidget(subheading_label("Share this address to receive payments"))

        # QR code card
        qr_card = Card()
        self._qr_widget = QRWidget(size=220)
        qr_layout = QHBoxLayout()
        qr_layout.addStretch()
        qr_layout.addWidget(self._qr_widget)
        qr_layout.addStretch()
        qr_card.layout().addLayout(qr_layout)
        layout.addWidget(qr_card)

        # Address card
        addr_card = Card()
        addr_card.layout().addWidget(caption_label("Your address"))
        self._addr_label = mono_label("—")
        self._addr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._addr_label.setWordWrap(True)
        addr_card.layout().addWidget(self._addr_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._copy_btn = QPushButton("📋 Copy")
        self._copy_btn.setFixedWidth(100)
        btn_row.addWidget(self._copy_btn)
        addr_card.layout().addLayout(btn_row)
        layout.addWidget(addr_card)

        # Derivation path
        self._path_label = caption_label("Derivation: —")
        self._path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._path_label)

        # New address button
        btn_row2 = QHBoxLayout()
        btn_row2.addStretch()
        self._new_btn = QPushButton("Generate New Address")
        self._new_btn.setProperty("role", "primary")
        self._new_btn.setFixedWidth(220)
        btn_row2.addWidget(self._new_btn)
        btn_row2.addStretch()
        layout.addLayout(btn_row2)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._api.address_generated.connect(self._on_address)
        self._new_btn.clicked.connect(self._on_generate)
        self._copy_btn.clicked.connect(self._on_copy)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot()
    def _on_generate(self) -> None:
        self._new_btn.setEnabled(False)
        self._api.generate_address()

    @Slot(str, str)
    def _on_address(self, address: str, path: str) -> None:
        self._current_address = address
        self._addr_label.setText(address)
        self._path_label.setText(f"Derivation: {path}")
        self._qr_widget.set_data(f"bitcoin:{address}")
        self._new_btn.setEnabled(True)

    @Slot()
    def _on_copy(self) -> None:
        if self._current_address:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(self._current_address)

    def refresh(self) -> None:
        """Generate an initial address on first show."""
        if not self._current_address:
            self._api.generate_address()
