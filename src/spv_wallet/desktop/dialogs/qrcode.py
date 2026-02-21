"""QR code display dialog — enlarged QR for easy scanning."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.widgets.qr_widget import QRWidget


class QRCodeDialog(QDialog):
    """Display a QR code for an address or URI."""

    def __init__(
        self,
        data: str,
        *,
        title: str = "QR Code",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(350, 400)
        self._setup_ui(data)

    def _setup_ui(self, data: str) -> None:
        layout = QVBoxLayout(self)

        # Centred QR widget
        qr = QRWidget(size=280)
        qr.set_data(data)
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(qr)
        qr_row.addStretch()
        layout.addLayout(qr_row)

        # Data label
        data_lbl = QLabel(data)
        data_lbl.setWordWrap(True)
        data_lbl.setStyleSheet("font-family: monospace; font-size: 11px;")
        layout.addWidget(data_lbl)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
