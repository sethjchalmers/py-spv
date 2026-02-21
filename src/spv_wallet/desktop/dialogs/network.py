"""Network status dialog — connectivity and peer info."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NetworkDialog(QDialog):
    """Displays engine network status and health."""

    def __init__(
        self,
        health: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Network Status")
        self.setMinimumWidth(420)
        self._health = health or {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._labels: dict[str, QLabel] = {}
        for key in ("engine", "datastore", "cache", "chain"):
            lbl = QLabel(self._health.get(key, "unknown"))
            self._labels[key] = lbl
            form.addRow(f"{key.title()}:", lbl)
        layout.addLayout(form)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self._refresh_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @Slot()
    def _on_refresh(self) -> None:
        """Placeholder — in production, re-query health."""
        pass

    def update_health(self, health: dict[str, Any]) -> None:
        """Update displayed health values."""
        self._health = health
        for key, lbl in self._labels.items():
            state = health.get(key, "unknown")
            colour = {
                "ok": "#22c55e",
                "error": "#ef4444",
                "not_connected": "#f59e0b",
            }.get(str(state), "#969696")
            lbl.setText(str(state))
            lbl.setStyleSheet(f"color: {colour};")
