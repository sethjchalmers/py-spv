"""Preferences / settings dialog — tabbed configuration."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class PreferencesDialog(QDialog):
    """Application preferences with tabbed sections.

    Tabs: General, Transactions, Network.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumSize(480, 360)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._transactions_tab(), "Transactions")
        tabs.addTab(self._network_tab(), "Network")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["satoshis", "BSV"])
        form.addRow("Display unit:", self._unit_combo)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English"])
        form.addRow("Language:", self._lang_combo)

        return widget

    def _transactions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fee_group = QGroupBox("Fee Policy")
        fee_form = QFormLayout(fee_group)

        self._fee_rate = QSpinBox()
        self._fee_rate.setRange(1, 1000)
        self._fee_rate.setValue(1)
        self._fee_rate.setSuffix(" sat/KB")
        fee_form.addRow("Fee rate:", self._fee_rate)

        layout.addWidget(fee_group)
        layout.addStretch()
        return widget

    def _network_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        form.addRow("ARC endpoint:", QLabel("https://arc.taal.com"))
        form.addRow("BHS endpoint:", QLabel("https://bhs.taal.com"))
        form.addRow(
            QLabel("Network settings are read-only in this version."),
        )

        return widget
