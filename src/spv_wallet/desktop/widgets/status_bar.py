"""Status bar — balance, network, and sync status display."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QStatusBar, QWidget

from spv_wallet.desktop.widgets.common import caption_label


class WalletStatusBar(QStatusBar):
    """Application status bar showing balance + connection state.

    Sections (left → right):
        • Balance indicator (satoshis)
        • Network status (connected / offline)
        • Sync status (synced / syncing)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._balance_label = caption_label("Balance: —")
        self._network_label = caption_label("● Offline")
        self._sync_label = caption_label("")

        self.addWidget(self._balance_label, stretch=1)
        self.addPermanentWidget(self._network_label)
        self.addPermanentWidget(self._sync_label)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_balance(self, satoshis: int) -> None:
        """Update the balance display."""
        self._balance_label.setText(f"Balance: {satoshis:,} sats")

    def set_network_status(self, connected: bool) -> None:
        """Update the network connection indicator."""
        if connected:
            self._network_label.setText("● Connected")
            self._network_label.setStyleSheet("color: #22c55e;")
        else:
            self._network_label.setText("● Offline")
            self._network_label.setStyleSheet("color: #ef4444;")

    def set_sync_status(self, text: str) -> None:
        """Update the sync status text."""
        self._sync_label.setText(text)
