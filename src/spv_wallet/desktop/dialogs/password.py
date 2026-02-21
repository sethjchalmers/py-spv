"""Password change dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)


class PasswordDialog(QDialog):
    """Dialog for setting or changing the wallet password."""

    def __init__(
        self,
        *,
        require_current: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(380)
        self._require_current = require_current
        self._setup_ui()

    def _setup_ui(self) -> None:
        form = QFormLayout(self)

        if self._require_current:
            self._current = QLineEdit()
            self._current.setEchoMode(
                QLineEdit.EchoMode.Password,
            )
            form.addRow("Current password:", self._current)
        else:
            self._current = None

        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New password:", self._new_pw)

        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Confirm:", self._confirm)

        hint = QLabel("Password encryption is not yet implemented.")
        hint.setStyleSheet("color: #969696; font-size: 11px;")
        form.addRow(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if self._new_pw.text() != self._confirm.text():
            QMessageBox.warning(
                self,
                "Mismatch",
                "Passwords do not match.",
            )
            return
        self.accept()

    @property
    def new_password(self) -> str:
        """Return the new password entered by the user."""
        return self._new_pw.text()

    @property
    def current_password(self) -> str:
        """Return the current password (empty if not required)."""
        if self._current is not None:
            return self._current.text()
        return ""
