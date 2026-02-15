"""Paymail server routes — /.well-known/bsvalias etc."""

from spv_wallet.api.paymail_server.provider import PaymailServiceProvider
from spv_wallet.api.paymail_server.provider_v2 import PaymailServiceProviderV2

__all__ = ["PaymailServiceProvider", "PaymailServiceProviderV2"]
