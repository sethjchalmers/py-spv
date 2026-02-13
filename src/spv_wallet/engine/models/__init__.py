"""V1 engine data models (SQLAlchemy ORM).

All 9 V1 models corresponding to the Go ``engine.AllDBModels()`` set.
Import :data:`ALL_MODELS` for migration and table creation.
"""

from spv_wallet.engine.models.access_key import AccessKey
from spv_wallet.engine.models.base import Base, MetadataMixin, TimestampMixin
from spv_wallet.engine.models.contact import Contact
from spv_wallet.engine.models.destination import Destination
from spv_wallet.engine.models.draft_transaction import DraftTransaction
from spv_wallet.engine.models.paymail_address import PaymailAddress
from spv_wallet.engine.models.transaction import TransactionRecord
from spv_wallet.engine.models.utxo import Utxo
from spv_wallet.engine.models.webhook import Webhook
from spv_wallet.engine.models.xpub import Xpub

ALL_MODELS: list[type[Base]] = [
    Xpub,
    AccessKey,
    Destination,
    DraftTransaction,
    TransactionRecord,
    Utxo,
    PaymailAddress,
    Contact,
    Webhook,
]

__all__ = [
    "ALL_MODELS",
    "AccessKey",
    "Base",
    "Contact",
    "Destination",
    "DraftTransaction",
    "MetadataMixin",
    "PaymailAddress",
    "TimestampMixin",
    "TransactionRecord",
    "Utxo",
    "Webhook",
    "Xpub",
]
