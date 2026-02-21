"""Desktop views — tabbed panels for the main window."""

from spv_wallet.desktop.views.console import ConsolePanel
from spv_wallet.desktop.views.contacts import ContactsPanel
from spv_wallet.desktop.views.history import HistoryPanel
from spv_wallet.desktop.views.keys import KeysPanel
from spv_wallet.desktop.views.overview import OverviewPanel
from spv_wallet.desktop.views.receive import ReceivePanel
from spv_wallet.desktop.views.send import SendPanel
from spv_wallet.desktop.views.settings import SettingsPanel
from spv_wallet.desktop.views.utxo import UTXOPanel

__all__ = [
    "ConsolePanel",
    "ContactsPanel",
    "HistoryPanel",
    "KeysPanel",
    "OverviewPanel",
    "ReceivePanel",
    "SendPanel",
    "SettingsPanel",
    "UTXOPanel",
]
