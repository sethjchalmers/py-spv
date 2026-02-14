"""Desktop views — tabbed panels for the main window."""

from spv_wallet.desktop.views.history import HistoryPanel
from spv_wallet.desktop.views.overview import OverviewPanel
from spv_wallet.desktop.views.receive import ReceivePanel
from spv_wallet.desktop.views.send import SendPanel
from spv_wallet.desktop.views.settings import SettingsPanel

__all__ = [
    "HistoryPanel",
    "OverviewPanel",
    "ReceivePanel",
    "SendPanel",
    "SettingsPanel",
]
