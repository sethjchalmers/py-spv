"""BSV amount input widget — satoshi ↔ BSV display toggle."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

_SATS_PER_BSV = 100_000_000


class AmountEdit(QWidget):
    """Input field for BSV amounts with satoshi / BSV toggle.

    Emits ``amount_changed(int)`` with value in **satoshis**.
    """

    amount_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._show_bsv = False  # default: show sats

        self._input = QLineEdit()
        self._input.setPlaceholderText("0")
        self._input.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._unit_btn = QPushButton("sats")
        self._unit_btn.setFixedWidth(60)
        self._unit_btn.setToolTip("Toggle satoshis / BSV")

        self._unit_label = QLabel("satoshis")
        self._unit_label.setProperty("role", "caption")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._input, stretch=1)
        layout.addWidget(self._unit_btn)

        self._unit_btn.clicked.connect(self._toggle_unit)
        self._input.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def satoshis(self) -> int:
        """Return the current value in satoshis."""
        text = self._input.text().strip().replace(",", "")
        if not text:
            return 0
        try:
            if self._show_bsv:
                return int(float(text) * _SATS_PER_BSV)
            return int(text)
        except ValueError:
            return 0

    def set_satoshis(self, sats: int) -> None:
        """Programmatically set the value in satoshis."""
        if self._show_bsv:
            self._input.setText(f"{sats / _SATS_PER_BSV:.8f}")
        else:
            self._input.setText(str(sats))

    def clear(self) -> None:
        """Clear the input."""
        self._input.clear()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_sats(sats: int) -> str:
        """Human-readable satoshi string with thousands separator."""
        return f"{sats:,}"

    @staticmethod
    def format_bsv(sats: int) -> str:
        """Human-readable BSV string (8 decimals)."""
        return f"{sats / _SATS_PER_BSV:.8f} BSV"

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _toggle_unit(self) -> None:
        sats = self.satoshis()
        self._show_bsv = not self._show_bsv
        self._unit_btn.setText("BSV" if self._show_bsv else "sats")
        self.set_satoshis(sats)

    def _on_text_changed(self, _text: str) -> None:
        self.amount_changed.emit(self.satoshis())
