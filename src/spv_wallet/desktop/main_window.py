"""Main window — QMainWindow with sidebar navigation and stacked panels."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from spv_wallet.desktop.theme import DARK_STYLESHEET
from spv_wallet.desktop.views.history import HistoryPanel
from spv_wallet.desktop.views.overview import OverviewPanel
from spv_wallet.desktop.views.receive import ReceivePanel
from spv_wallet.desktop.views.send import SendPanel
from spv_wallet.desktop.views.settings import SettingsPanel
from spv_wallet.desktop.wallet_api import WalletAPI
from spv_wallet.desktop.widgets.status_bar import WalletStatusBar

# Navigation items: (label, icon hint)
_NAV_ITEMS = [
    ("Overview", "🏠"),
    ("Send", "📤"),
    ("Receive", "📥"),
    ("Transactions", "📋"),
    ("Settings", "⚙️"),
]


class MainWindow(QMainWindow):
    """Primary application window with sidebar navigation.

    Layout::

        ┌───────────┬──────────────────────────┐
        │  Sidebar  │   Stacked panels         │
        │  (nav)    │   (overview / send / …)   │
        │           │                          │
        ├───────────┴──────────────────────────┤
        │  Status bar (balance · network)      │
        └──────────────────────────────────────┘
    """

    def __init__(self, api: WalletAPI | None = None) -> None:
        super().__init__()
        self.setWindowTitle("py-spv Wallet")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # WalletAPI bridge — passed from app.py or created internally
        self._api = api or WalletAPI(self)

        # Apply dark theme
        self.setStyleSheet(DARK_STYLESHEET)

        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Stacked content panels
        self._stack = QStackedWidget()
        self._panels = [
            OverviewPanel(self._api),
            SendPanel(self._api),
            ReceivePanel(self._api),
            HistoryPanel(self._api),
            SettingsPanel(self._api),
        ]
        for panel in self._panels:
            self._stack.addWidget(panel)
        root.addWidget(self._stack, stretch=1)

        # Status bar
        self._status_bar = WalletStatusBar(self)
        self.setStatusBar(self._status_bar)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("background-color: #252526;")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        # App title
        from spv_wallet.desktop.widgets.common import heading_label  # noqa: PLC0415

        title = heading_label("py-spv")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #eab308; font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        layout.addSpacing(16)

        # Navigation buttons
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []

        for idx, (label, icon) in enumerate(_NAV_ITEMS):
            btn = QPushButton(f" {icon}  {label}")
            btn.setProperty("role", "nav")
            btn.setCheckable(True)
            self._nav_group.addButton(btn, idx)
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        # Select first by default
        self._nav_buttons[0].setChecked(True)

        layout.addStretch()
        return sidebar

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._nav_group.idClicked.connect(self._on_nav)
        self._api.balance_updated.connect(self._status_bar.set_balance)
        self._api.engine_ready.connect(self._on_engine_ready)
        self._api.error_occurred.connect(self._on_error)

    @Slot(int)
    def _on_nav(self, index: int) -> None:
        """Switch the active panel."""
        self._stack.setCurrentIndex(index)
        # Trigger refresh on the target panel
        panel = self._panels[index]
        if hasattr(panel, "refresh"):
            panel.refresh()

    @Slot()
    def _on_engine_ready(self) -> None:
        self._status_bar.set_network_status(connected=True)
        self._status_bar.set_sync_status("Ready")
        # Trigger initial data load
        overview = self._panels[0]
        if hasattr(overview, "refresh"):
            overview.refresh()

    @Slot(str, str)
    def _on_error(self, title: str, _detail: str) -> None:
        self._status_bar.set_sync_status(f"Error: {title}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def api(self) -> WalletAPI:
        """Access the WalletAPI bridge."""
        return self._api
