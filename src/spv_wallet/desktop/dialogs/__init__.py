"""Desktop dialogs — modal windows for transactions, settings, etc."""

from spv_wallet.desktop.dialogs.network import NetworkDialog
from spv_wallet.desktop.dialogs.password import PasswordDialog
from spv_wallet.desktop.dialogs.preferences import PreferencesDialog
from spv_wallet.desktop.dialogs.qrcode import QRCodeDialog
from spv_wallet.desktop.dialogs.transaction import TransactionDialog

__all__ = [
    "NetworkDialog",
    "PasswordDialog",
    "PreferencesDialog",
    "QRCodeDialog",
    "TransactionDialog",
]
