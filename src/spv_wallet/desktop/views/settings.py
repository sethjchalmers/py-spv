"""Settings panel — wallet info, network configuration display."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from spv_wallet.desktop.widgets.common import Card, caption_label, heading_label, mono_label

if TYPE_CHECKING:
    from spv_wallet.desktop.wallet_api import WalletAPI


class SettingsPanel(QWidget):
    """Settings / info panel.

    Displays wallet metadata and engine configuration (read-only for now).
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

        layout.addWidget(heading_label("Settings"))

        # Wallet info card
        info_card = Card()
        info_card.layout().addWidget(QLabel("xPub ID"))
        self._xpub_label = mono_label("—")
        info_card.layout().addWidget(self._xpub_label)

        info_card.layout().addWidget(QLabel("Raw xPub"))
        self._raw_xpub_label = mono_label("—")
        self._raw_xpub_label.setWordWrap(True)
        info_card.layout().addWidget(self._raw_xpub_label)
        layout.addWidget(info_card)

        # Engine health card
        health_card = Card()
        health_card.layout().addWidget(QLabel("Engine Health"))
        self._health_label = caption_label("—")
        health_card.layout().addWidget(self._health_label)
        layout.addWidget(health_card)

        # Version / about
        about_card = Card()
        about_card.layout().addWidget(QLabel("py-spv Wallet"))
        about_card.layout().addWidget(caption_label("Version 0.1.0-alpha"))
        about_card.layout().addWidget(
            caption_label("BSV blockchain SPV wallet — desktop edition"),
        )
        layout.addWidget(about_card)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._api.xpub_registered.connect(self._on_xpub)
        self._api.health_updated.connect(self._on_health)

    @Slot(str)
    def _on_xpub(self, xpub_id: str) -> None:
        self._xpub_label.setText(xpub_id)
        self._raw_xpub_label.setText(self._api.raw_xpub)

    @Slot(dict)
    def _on_health(self, status: dict[str, str]) -> None:
        lines = [f"{k}: {v}" for k, v in status.items()]
        self._health_label.setText(" | ".join(lines))

    def refresh(self) -> None:
        """Refresh displayed info."""
        if self._api.xpub_id:
            self._xpub_label.setText(self._api.xpub_id)
            self._raw_xpub_label.setText(self._api.raw_xpub)
        self._api.check_health()
