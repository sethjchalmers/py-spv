"""Account wizard — add accounts to existing wallets.

Provides a simple dialog to register an additional xPub (account)
with the currently-open wallet engine.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

_TITLE = "Add Account"


class _ImportAccountPage(QWizardPage):
    """Enter an xPub to register as a new account."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle(_TITLE)
        self.setSubTitle("Paste an extended public key (xPub) to track as a new account.")
        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Savings")
        layout.addRow("Account label:", self._name_edit)

        self._xpub_edit = QTextEdit()
        self._xpub_edit.setPlaceholderText("xpub6...")
        self._xpub_edit.setMaximumHeight(80)
        layout.addRow("xPub:", self._xpub_edit)

        self.registerField("account_label*", self._name_edit)

    def validatePage(self) -> bool:
        xpub = self._xpub_edit.toPlainText().strip()
        if not xpub or not xpub.startswith("xpub"):
            QMessageBox.warning(
                self,
                "Invalid xPub",
                "Please enter a valid Base58 xPub starting with 'xpub'.",
            )
            return False
        return True

    @property
    def xpub(self) -> str:
        return self._xpub_edit.toPlainText().strip()


class AccountWizard(QWizard):
    """Wizard dialog for adding a new account (xPub) to the wallet.

    Emits ``account_added(str)`` with the raw xPub on success.
    """

    account_added = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.setMinimumSize(480, 300)

        self._page = _ImportAccountPage()
        self.addPage(self._page)

    def accept(self) -> None:
        xpub = self._page.xpub
        if xpub:
            self.account_added.emit(xpub)
        super().accept()


class QuickAddAccountDialog(QDialog):
    """Minimal dialog alternative to the wizard — single form.

    Emits ``account_added(str)`` with the raw xPub on accept.
    """

    account_added = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        self.setMinimumWidth(440)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Savings")
        form.addRow("Label:", self._name)

        self._xpub = QTextEdit()
        self._xpub.setPlaceholderText("xpub6...")
        self._xpub.setMaximumHeight(80)
        form.addRow("xPub:", self._xpub)

        hint = QLabel("Enter a Base58 xPub to track as a separate account.")
        hint.setStyleSheet("color: #969696; font-size: 11px;")
        form.addRow(hint)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        xpub = self._xpub.toPlainText().strip()
        if not xpub or not xpub.startswith("xpub"):
            QMessageBox.warning(
                self,
                "Invalid xPub",
                "Please enter a valid xPub starting with 'xpub'.",
            )
            return
        self.account_added.emit(xpub)
        self.accept()
