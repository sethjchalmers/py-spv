"""Contact list view — table with status management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.widgets.common import caption_label, heading_label

if TYPE_CHECKING:
    from spv_wallet.desktop.wallet_api import WalletAPI

_COLUMNS = ["Name", "Paymail", "Public Key", "Status"]

_STATUS_COLOURS = {
    "confirmed": "#22c55e",
    "awaiting": "#f59e0b",
    "unconfirmed": "#969696",
    "rejected": "#ef4444",
}


class _AddContactDialog(QDialog):
    """Simple dialog for adding a new contact."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Contact")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Display name")
        layout.addRow("Name:", self.name_input)

        self.paymail_input = QLineEdit()
        self.paymail_input.setPlaceholderText("user@example.com")
        layout.addRow("Paymail:", self.paymail_input)

        self.pubkey_input = QLineEdit()
        self.pubkey_input.setPlaceholderText(
            "(optional) compressed hex pubkey",
        )
        layout.addRow("Public Key:", self.pubkey_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class ContactsPanel(QWidget):
    """Contacts management panel.

    Table of contacts with add/delete and status management
    via context menu.
    """

    def __init__(self, api: WalletAPI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._contacts: list[dict[str, Any]] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header row
        header_row = QHBoxLayout()
        header_row.addWidget(heading_label("Contacts"))
        header_row.addStretch()

        self._add_btn = QPushButton("Add Contact")
        self._add_btn.setFixedWidth(140)
        header_row.addWidget(self._add_btn)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedWidth(100)
        header_row.addWidget(self._refresh_btn)
        layout.addLayout(header_row)

        # Summary
        self._count_label = caption_label("0 contacts")
        layout.addWidget(self._count_label)

        # Table
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, len(_COLUMNS)):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._table, stretch=1)

    def _connect_signals(self) -> None:
        self._api.contacts_updated.connect(self._on_contacts)
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._add_btn.clicked.connect(self._on_add_contact)
        self._table.customContextMenuRequested.connect(
            self._on_context_menu,
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_contacts(self, contacts: list[dict[str, Any]]) -> None:
        self._contacts = contacts
        self._table.setRowCount(len(contacts))
        for row, c in enumerate(contacts):
            self._table.setItem(row, 0, QTableWidgetItem(c.get("full_name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(c.get("paymail", "")))
            pubkey = c.get("pub_key", "")
            pk_display = pubkey[:16] + "..." if len(pubkey) > 16 else pubkey
            self._table.setItem(row, 2, QTableWidgetItem(pk_display))

            status = c.get("status", "unconfirmed")
            status_item = QTableWidgetItem(status)
            colour = _STATUS_COLOURS.get(status, "#969696")
            status_item.setForeground(QColor(colour))
            self._table.setItem(row, 3, status_item)

        self._count_label.setText(f"{len(contacts)} contacts")

    @Slot()
    def _on_refresh(self) -> None:
        self._api.refresh_contacts()

    @Slot()
    def _on_add_contact(self) -> None:
        dialog = _AddContactDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.name_input.text().strip()
            paymail = dialog.paymail_input.text().strip()
            pubkey = dialog.pubkey_input.text().strip()
            if not paymail:
                QMessageBox.warning(
                    self,
                    "Missing paymail",
                    "Paymail address is required.",
                )
                return
            self._api.create_contact(
                paymail=paymail,
                full_name=name,
                pub_key=pubkey,
            )

    def _on_context_menu(self, pos: Any) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._contacts):
            return
        contact = self._contacts[row]
        contact_id = contact.get("id", "")
        status = contact.get("status", "")

        menu = QMenu(self)

        # Copy actions
        copy_paymail = menu.addAction("Copy Paymail")

        # Status transitions
        menu.addSeparator()
        confirm_action = None
        reject_action = None
        if status in ("unconfirmed", "awaiting"):
            confirm_action = menu.addAction("Confirm")
            reject_action = menu.addAction("Reject")

        # Delete
        menu.addSeparator()
        delete_action = menu.addAction("Delete Contact")

        action = menu.exec(
            self._table.viewport().mapToGlobal(pos),
        )
        if action is None:
            return

        if action == copy_paymail:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(contact.get("paymail", ""))
        elif action == confirm_action:
            self._api.update_contact_status(contact_id, "confirmed")
        elif action == reject_action:
            self._api.update_contact_status(contact_id, "rejected")
        elif action == delete_action:
            reply = QMessageBox.question(
                self,
                "Delete Contact",
                f"Delete contact {contact.get('full_name', '')}?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._api.delete_contact(contact_id)

    def refresh(self) -> None:
        """Trigger data refresh."""
        self._api.refresh_contacts()
