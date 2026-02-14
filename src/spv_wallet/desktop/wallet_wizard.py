"""Wallet wizard — create new wallet or import existing one.

The wizard runs before the main window is shown.  Flow:
  1.  Choose wallet file path (.sqlite)
  2.  Choose mode: Generate New or Import Existing
  3a. Generate → shows 12-word seed phrase to back up → derives xPub
  3b. Import   → paste seed phrase OR raw xPub
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

# Page IDs for non-linear navigation
_PAGE_FILE = 0
_PAGE_MODE = 1
_PAGE_GENERATE = 2
_PAGE_IMPORT = 3


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
# Page 1 — Wallet File
# ---------------------------------------------------------------------------


class WalletFilePage(QWizardPage):
    """Choose or create a wallet file."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Wallet File")
        self.setSubTitle("Choose where to store your wallet data.")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Wallet file path:"))

        row = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("/path/to/my-wallet.sqlite")
        self._path_input.setProperty("role", "mono")

        # Set a sensible default
        default_path = str(Path.home() / "py-spv-wallet.sqlite")
        self._path_input.setText(default_path)

        row.addWidget(self._path_input, stretch=1)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(100)
        row.addWidget(self._browse_btn)
        layout.addLayout(row)

        self._status = QLabel("")
        self._status.setProperty("role", "caption")
        layout.addWidget(self._status)

        self.registerField("wallet_path*", self._path_input)
        self._browse_btn.clicked.connect(self._on_browse)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Wallet Location",
            "py-spv-wallet.sqlite",
            "SQLite files (*.sqlite *.db);;All files (*)",
        )
        if path:
            if not Path(path).suffix:
                path += ".sqlite"
            self._path_input.setText(path)


# ---------------------------------------------------------------------------
# Page 2 — Choose Mode (Generate or Import)
# ---------------------------------------------------------------------------


class ModePage(QWizardPage):
    """Choose between generating a new wallet or importing an existing one."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Wallet Setup")
        self.setSubTitle("How would you like to set up your wallet?")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        self._generate_radio = QRadioButton("🆕  Create a new wallet")
        self._generate_radio.setChecked(True)
        self._generate_radio.setStyleSheet("font-size: 15px; padding: 8px;")
        layout.addWidget(self._generate_radio)

        gen_desc = QLabel(
            "Generate a new 12-word seed phrase. You'll be shown the words\n"
            "to write down and keep safe — they are your wallet backup."
        )
        gen_desc.setProperty("role", "caption")
        gen_desc.setIndent(28)
        gen_desc.setWordWrap(True)
        layout.addWidget(gen_desc)

        layout.addSpacing(8)

        self._import_radio = QRadioButton("📥  Import an existing wallet")
        self._import_radio.setStyleSheet("font-size: 15px; padding: 8px;")
        layout.addWidget(self._import_radio)

        imp_desc = QLabel(
            "Restore from a seed phrase you've already backed up,\n"
            "or import a raw xPub key for watch-only mode."
        )
        imp_desc.setProperty("role", "caption")
        imp_desc.setIndent(28)
        imp_desc.setWordWrap(True)
        layout.addWidget(imp_desc)

        layout.addStretch()

    @property
    def is_generate(self) -> bool:
        return self._generate_radio.isChecked()

    def nextId(self) -> int:
        return _PAGE_GENERATE if self.is_generate else _PAGE_IMPORT


# ---------------------------------------------------------------------------
# Page 3a — Generate New Wallet (show seed phrase)
# ---------------------------------------------------------------------------


class GeneratePage(QWizardPage):
    """Generate and display a 12-word seed phrase for backup."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setTitle("Your Seed Phrase")
        self.setSubTitle(
            "Write down these 12 words in order and keep them safe.\n"
            "Anyone with these words can access your wallet. Never share them."
        )
        self._mnemonic = ""
        self._confirmed = False

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Seed phrase display
        self._seed_display = QTextEdit()
        self._seed_display.setReadOnly(True)
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
        """Generate a fresh mnemonic each time this page is shown."""
        self._mnemonic = _generate_mnemonic()
        self._confirmed = False
        self._confirm_btn.setChecked(False)

        # Format as numbered grid
        words = self._mnemonic.split()
        lines = []
        for i in range(0, len(words), 3):
            row = "    ".join(
                f"{i + j + 1:2d}. {words[i + j]}" for j in range(3) if i + j < len(words)
            )
            lines.append(row)
        self._seed_display.setText("\n".join(lines))

        self.completeChanged.emit()

    def _on_confirm(self, checked: bool) -> None:
        self._confirmed = checked
        if checked:
            # Derive xPub from the mnemonic
            xpub = _mnemonic_to_xpub(self._mnemonic)
            self._xpub_holder.setText(xpub)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._confirmed

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
        self.setSubTitle("Restore from a seed phrase, or paste a raw xPub for watch-only mode.")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

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

    def _on_mode_toggle(self) -> None:
        seed_mode = self._seed_radio.isChecked()
        self._seed_input.setEnabled(seed_mode)
        self._xpub_input.setEnabled(not seed_mode)

    def validatePage(self) -> bool:
        """Validate and resolve the xPub."""
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

    def nextId(self) -> int:
        return -1  # final page


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------


class WalletWizard(QWizard):
    """Multi-step wizard for wallet setup.

    Flows:
        File → Mode → Generate (show seed phrase)  → done
        File → Mode → Import   (seed or xPub)      → done

    Usage::

        wizard = WalletWizard()
        if wizard.exec() == QWizard.DialogCode.Accepted:
            wallet_path = wizard.wallet_path()
            raw_xpub    = wizard.raw_xpub()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("py-spv — Wallet Setup")
        self.setMinimumSize(650, 480)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.setPage(_PAGE_FILE, WalletFilePage())
        self.setPage(_PAGE_MODE, ModePage())
        self.setPage(_PAGE_GENERATE, GeneratePage())
        self.setPage(_PAGE_IMPORT, ImportPage())

    def wallet_path(self) -> str:
        """Return the chosen wallet file path."""
        return self.field("wallet_path") or ""

    def raw_xpub(self) -> str:
        """Return the resolved xPub string (from generate or import)."""
        # Generate page stores in "raw_xpub", import in "raw_xpub_import"
        xpub = (self.field("raw_xpub") or "").strip()
        if not xpub:
            xpub = (self.field("raw_xpub_import") or "").strip()
        return xpub
