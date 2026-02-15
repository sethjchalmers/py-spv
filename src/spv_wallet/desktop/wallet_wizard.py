"""Wallet wizard — create new wallet or import existing one.

The wizard runs before the main window is shown.  Flow:
  1.  Choose mode: Open Existing / Generate New / Import
  2a. Open Existing → select from previously-created wallets
  2b. Generate → shows 12-word seed phrase to back up → derives xPub
  2c. Import   → paste seed phrase OR raw xPub

Wallet databases are stored in a ``wallets/`` subdirectory relative to
the application.  When running from a frozen bundle (PyInstaller / DMG /
EXE) the data directory sits next to the executable.  In development it
falls back to ``~/.py-spv/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)


class _SeedDisplay(QTextEdit):
    """Read-only text widget that copies only raw seed words (no numbers)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw_words = ""
        self.setReadOnly(True)

    def set_seed(self, mnemonic: str) -> None:
        """Set the mnemonic and render a numbered HTML grid."""
        self._raw_words = mnemonic
        words = mnemonic.split()
        rows: list[str] = []
        for i in range(0, len(words), 3):
            cells = ""
            for j in range(3):
                if i + j < len(words):
                    num = i + j + 1
                    cells += (
                        f'<td style="padding: 4px 12px 4px 0;">'
                        f'<span style="color: #888;">{num:2d}.</span> {words[i + j]}'
                        f"</td>"
                    )
            rows.append(f"<tr>{cells}</tr>")
        self.setHtml(f'<table style="font-size:16px;">{"".join(rows)}</table>')

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Intercept Ctrl+C / Cmd+C to copy only seed words."""
        if event.matches(QKeySequence.StandardKey.Copy):
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self._raw_words)
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """Replace default context menu copy with seed-only copy."""
        menu = self.createStandardContextMenu()
        if menu is None:
            return
        for action in menu.actions():
            if action.text() and "copy" in action.text().lower().replace("&", ""):
                action.triggered.disconnect()
                action.triggered.connect(self._copy_seed)
        menu.exec(event.globalPos())

    def _copy_seed(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._raw_words)


# Page IDs for non-linear navigation
_PAGE_MODE = 0
_PAGE_GENERATE = 1
_PAGE_IMPORT = 2


# ---------------------------------------------------------------------------
# Application data directory
# ---------------------------------------------------------------------------


def _get_wallets_dir() -> Path:
    """Return the ``wallets/`` directory for storing wallet databases.

    When the app is frozen (PyInstaller / cx_Freeze), the data directory
    lives next to the executable — exactly like ElectrumSV's portable
    mode.  In development (un-frozen) it falls back to ``~/.py-spv/``.
    """
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.home() / ".py-spv"
    wallets = base / "wallets"
    wallets.mkdir(parents=True, exist_ok=True)
    return wallets


def _list_existing_wallets() -> list[Path]:
    """Return sorted list of ``.sqlite`` wallet files in the wallets dir."""
    wallets_dir = _get_wallets_dir()
    return sorted(wallets_dir.glob("*.sqlite"))


def _next_wallet_name() -> str:
    """Generate the next unused wallet filename like ``wallet_1.sqlite``."""
    existing = _list_existing_wallets()
    existing_names = {p.name for p in existing}
    n = 1
    while f"wallet_{n}.sqlite" in existing_names:
        n += 1
    return f"wallet_{n}.sqlite"


def _next_wallet_stem() -> str:
    """Return a default wallet name without extension, e.g. ``wallet_1``."""
    return _next_wallet_name().removesuffix(".sqlite")


# ---------------------------------------------------------------------------
# Seed / key generation helpers
# ---------------------------------------------------------------------------


def _generate_mnemonic() -> str:
    """Generate a 12-word BIP39 mnemonic seed phrase."""
    from mnemonic import Mnemonic

    m = Mnemonic("english")
    return m.generate(strength=128)  # 12 words


def _mnemonic_to_xpub(words: str) -> str:
    """Derive an xPub from a BIP39 mnemonic phrase.

    Derivation path: m/44'/236'/0'  (BSV BIP44).
    """
    from mnemonic import Mnemonic

    from spv_wallet.bsv.keys import ExtendedKey

    m = Mnemonic("english")
    seed = m.to_seed(words.strip())
    master = ExtendedKey.from_seed(seed)
    # BIP44 path for BSV: m/44'/236'/0'
    account = master.derive_child(0x80000000 + 44)
    account = account.derive_child(0x80000000 + 236)
    account = account.derive_child(0x80000000 + 0)
    return account.neuter().to_string()


# ---------------------------------------------------------------------------
# Page 1 — Choose Mode (Generate or Import)
# ---------------------------------------------------------------------------


_BTN_STYLE = "font-size: 14px; padding: 8px;"


class ModePage(QWizardPage):
    """Launcher page: open an existing wallet or start a new one."""

    _chosen_flow: str = ""  # "generate" or "import"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Wallet Setup")
        self.setSubTitle("Open a wallet you've already created, or set up a new one.")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Existing wallets section (hidden when none exist) ──
        self._existing_label = QLabel("Your wallets:")
        self._existing_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(self._existing_label)

        self._wallet_list = QListWidget()
        self._wallet_list.setMaximumHeight(120)
        self._wallet_list.setStyleSheet("font-size: 14px; padding: 4px;")
        layout.addWidget(self._wallet_list)

        self._open_btn = QPushButton("📂  Open Selected Wallet")
        self._open_btn.setStyleSheet(_BTN_STYLE)
        self._open_btn.setEnabled(False)
        layout.addWidget(self._open_btn)

        self._separator = QLabel("")
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet("background-color: #555;")
        layout.addWidget(self._separator)

        # ── New wallet actions ──
        action_label = QLabel("Or set up a new wallet:")
        action_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(action_label)

        self._create_btn = QPushButton("🆕  Create a New Wallet")
        self._create_btn.setStyleSheet(_BTN_STYLE)
        layout.addWidget(self._create_btn)

        self._import_btn = QPushButton("📥  Import / Restore a Wallet")
        self._import_btn.setStyleSheet(_BTN_STYLE)
        layout.addWidget(self._import_btn)

        layout.addStretch()

        # Wire signals
        self._wallet_list.currentRowChanged.connect(self._on_wallet_selected)
        self._open_btn.clicked.connect(self._on_open_clicked)
        self._create_btn.clicked.connect(self._on_create_clicked)
        self._import_btn.clicked.connect(self._on_import_clicked)

    # -- lifecycle --

    def initializePage(self) -> None:
        """Populate the list of existing wallets each time we enter."""
        self._wallet_list.clear()
        wallets = _list_existing_wallets()
        for wp in wallets:
            item = QListWidgetItem(f"  {wp.stem}")
            item.setData(256, str(wp))
            self._wallet_list.addItem(item)

        has_wallets = len(wallets) > 0
        self._existing_label.setVisible(has_wallets)
        self._wallet_list.setVisible(has_wallets)
        self._open_btn.setVisible(has_wallets)
        self._separator.setVisible(has_wallets)

    # -- signals --

    def _on_wallet_selected(self, row: int) -> None:
        self._open_btn.setEnabled(row >= 0)

    def _on_open_clicked(self) -> None:
        """Directly accept the wizard with the selected wallet."""
        wizard = self.wizard()
        if wizard is not None and isinstance(wizard, WalletWizard):
            item = self._wallet_list.currentItem()
            if item is not None:
                wizard._selected_existing_path = item.data(256)
                wizard.accept()

    def _on_create_clicked(self) -> None:
        """Navigate to the Generate page."""
        self._chosen_flow = "generate"
        self.completeChanged.emit()
        wizard = self.wizard()
        if wizard is not None:
            wizard.next()

    def _on_import_clicked(self) -> None:
        """Navigate to the Import page."""
        self._chosen_flow = "import"
        self.completeChanged.emit()
        wizard = self.wizard()
        if wizard is not None:
            wizard.next()

    # -- QWizardPage overrides --

    def isComplete(self) -> bool:
        return self._chosen_flow != ""

    def nextId(self) -> int:
        if self._chosen_flow == "import":
            return _PAGE_IMPORT
        return _PAGE_GENERATE


# ---------------------------------------------------------------------------
# Page 3a — Generate New Wallet (show seed phrase)
# ---------------------------------------------------------------------------


class GeneratePage(QWizardPage):
    """Name the wallet and display a 12-word seed phrase for backup."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Create New Wallet")
        self.setSubTitle(
            "Name your wallet, then write down the 12-word seed phrase.\n"
            "Anyone with these words can access your wallet. Never share them."
        )
        self._mnemonic = ""
        self._confirmed = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Wallet name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Wallet name:"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. My Wallet")
        self._name_input.setMaximumWidth(260)
        name_row.addWidget(self._name_input)
        name_row.addStretch()
        layout.addLayout(name_row)

        layout.addSpacing(4)

        # Seed phrase display (copies only raw words, no numbers)
        self._seed_display = _SeedDisplay()
        self._seed_display.setMaximumHeight(120)
        self._seed_display.setProperty("role", "mono")
        self._seed_display.setStyleSheet("font-size: 16px; line-height: 1.8; padding: 12px;")
        layout.addWidget(self._seed_display)

        # Warning
        warning = QLabel(
            "⚠️  IMPORTANT: Write these words down on paper. Do NOT\n"
            "screenshot or store them digitally. This is your only backup."
        )
        warning.setStyleSheet("color: #f59e0b; font-weight: 600;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Confirm checkbox-style button
        self._confirm_btn = QPushButton("✓  I have written down my seed phrase")
        self._confirm_btn.setProperty("role", "primary")
        self._confirm_btn.setCheckable(True)
        self._confirm_btn.clicked.connect(self._on_confirm)
        layout.addWidget(self._confirm_btn)

        layout.addStretch()

        # Hidden field for the generated xpub
        self._xpub_holder = QLineEdit()
        self._xpub_holder.setVisible(False)
        layout.addWidget(self._xpub_holder)
        self.registerField("raw_xpub", self._xpub_holder)

    def initializePage(self) -> None:
        """Generate a fresh mnemonic and pre-fill wallet name."""
        self._mnemonic = _generate_mnemonic()
        self._confirmed = False
        self._confirm_btn.setChecked(False)
        self._seed_display.set_seed(self._mnemonic)
        self._name_input.setText(_next_wallet_stem())
        self.completeChanged.emit()

    def _on_confirm(self, checked: bool) -> None:
        self._confirmed = checked
        if checked:
            # Derive xPub from the mnemonic
            xpub = _mnemonic_to_xpub(self._mnemonic)
            self._xpub_holder.setText(xpub)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._confirmed and len(self._name_input.text().strip()) > 0

    @property
    def wallet_name(self) -> str:
        """Return the sanitised wallet filename."""
        name = self._name_input.text().strip() or _next_wallet_stem()
        if not name.endswith(".sqlite"):
            name += ".sqlite"
        return name

    def nextId(self) -> int:
        return -1  # final page


# ---------------------------------------------------------------------------
# Page 3b — Import Existing (seed phrase or raw xPub)
# ---------------------------------------------------------------------------


class ImportPage(QWizardPage):
    """Import via seed phrase or raw xPub."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Import Wallet")
        self.setSubTitle("Name your wallet, then restore from a seed phrase or paste an xPub.")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Wallet name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Wallet name:"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. My Wallet")
        self._name_input.setMaximumWidth(260)
        name_row.addWidget(self._name_input)
        name_row.addStretch()
        layout.addLayout(name_row)

        layout.addSpacing(4)

        # Seed phrase input
        self._seed_radio = QRadioButton("Seed phrase (12 or 24 words)")
        self._seed_radio.setChecked(True)
        layout.addWidget(self._seed_radio)

        self._seed_input = QTextEdit()
        self._seed_input.setPlaceholderText("word1 word2 word3 … (12 or 24 words)")
        self._seed_input.setMaximumHeight(80)
        self._seed_input.setProperty("role", "mono")
        layout.addWidget(self._seed_input)

        layout.addSpacing(8)

        # Raw xPub input
        self._xpub_radio = QRadioButton("Raw xPub key (advanced / watch-only)")
        layout.addWidget(self._xpub_radio)

        self._xpub_input = QTextEdit()
        self._xpub_input.setPlaceholderText("xpub6...")
        self._xpub_input.setMaximumHeight(80)
        self._xpub_input.setProperty("role", "mono")
        layout.addWidget(self._xpub_input)

        # Hint
        hint = QLabel(
            "💡  Seed phrase will derive your full wallet. xPub creates a\n"
            "     watch-only wallet (can view & generate addresses, cannot sign)."
        )
        hint.setProperty("role", "caption")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()

        # Toggle input enable/disable based on radio
        self._seed_radio.toggled.connect(self._on_mode_toggle)
        self._xpub_radio.toggled.connect(self._on_mode_toggle)
        self._on_mode_toggle()

        # Hidden field for the resolved xpub
        self._xpub_holder = QLineEdit()
        self._xpub_holder.setVisible(False)
        layout.addWidget(self._xpub_holder)
        self.registerField("raw_xpub_import", self._xpub_holder)

    def initializePage(self) -> None:
        """Pre-fill wallet name."""
        self._name_input.setText(_next_wallet_stem())

    def _on_mode_toggle(self) -> None:
        seed_mode = self._seed_radio.isChecked()
        self._seed_input.setEnabled(seed_mode)
        self._xpub_input.setEnabled(not seed_mode)

    def validatePage(self) -> bool:
        """Validate wallet name and resolve the xPub."""
        if not self._name_input.text().strip():
            QMessageBox.warning(
                self, "Wallet name required", "Please enter a name for your wallet."
            )
            return False
        if self._seed_radio.isChecked():
            words = self._seed_input.toPlainText().strip()
            word_count = len(words.split())
            if word_count not in (12, 24):
                QMessageBox.warning(
                    self,
                    "Invalid seed phrase",
                    f"Expected 12 or 24 words, got {word_count}.\n"
                    "Please check your seed phrase and try again.",
                )
                return False
            try:
                xpub = _mnemonic_to_xpub(words)
                self._xpub_holder.setText(xpub)
                return True
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Invalid seed phrase",
                    f"Could not derive wallet:\n{exc}",
                )
                return False
        else:
            text = self._xpub_input.toPlainText().strip()
            if not text.startswith("xpub") or len(text) < 80:
                QMessageBox.warning(
                    self,
                    "Invalid xPub",
                    "Please enter a valid extended public key starting with 'xpub'.",
                )
                return False
            self._xpub_holder.setText(text)
            return True

    @property
    def wallet_name(self) -> str:
        """Return the sanitised wallet filename."""
        name = self._name_input.text().strip() or _next_wallet_stem()
        if not name.endswith(".sqlite"):
            name += ".sqlite"
        return name

    def nextId(self) -> int:
        return -1  # final page


class WalletWizard(QWizard):
    """Multi-step wizard for wallet setup.

    Flows:
        Mode → "Open Selected Wallet" button → done  (existing wallet)
        Mode → Create → Generate (name + seed) → done  (new wallet)
        Mode → Import  (name + seed / xPub)    → done  (new wallet)

    Usage::

        wizard = WalletWizard()
        if wizard.exec() == QWizard.DialogCode.Accepted:
            wallet_path = wizard.wallet_path()
            raw_xpub    = wizard.raw_xpub()
    """

    # Set by ModePage._on_open_clicked when user opens an existing wallet.
    _selected_existing_path: str | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("py-spv — Wallet Setup")
        self.setMinimumSize(650, 520)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self._mode_page = ModePage()
        self._generate_page = GeneratePage()
        self._import_page = ImportPage()
        self.setPage(_PAGE_MODE, self._mode_page)
        self.setPage(_PAGE_GENERATE, self._generate_page)
        self.setPage(_PAGE_IMPORT, self._import_page)

    def wallet_path(self) -> str:
        """Return the wallet file path for the chosen flow."""
        if self._selected_existing_path:
            return self._selected_existing_path

        if self._mode_page._chosen_flow == "import":
            name = self._import_page.wallet_name
        else:
            name = self._generate_page.wallet_name
        return str(_get_wallets_dir() / name)

    def raw_xpub(self) -> str:
        """Return the resolved xPub string (from generate or import)."""
        xpub = (self.field("raw_xpub") or "").strip()
        if not xpub:
            xpub = (self.field("raw_xpub_import") or "").strip()
        return xpub
