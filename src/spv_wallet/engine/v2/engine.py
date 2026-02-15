"""V2 engine entry point.

The V2Engine wraps all V2 services and repositories, providing a
single entry point for V2 functionality. It's initialized as part
of the main SPVWalletEngine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine
    from spv_wallet.engine.v2.contacts.service import ContactsServiceV2
    from spv_wallet.engine.v2.paymails.service import PaymailsServiceV2
    from spv_wallet.engine.v2.transaction.outlines.service import OutlinesService
    from spv_wallet.engine.v2.transaction.record.service import RecordService
    from spv_wallet.engine.v2.transaction.txsync.service import TxSyncService
    from spv_wallet.engine.v2.users.service import UsersService


class V2Engine:
    """V2 engine — outline-based transaction workflow.

    Owns all V2 services and provides a unified access point.
    """

    _ERR_NOT_INITIALIZED = "V2 engine not initialized"

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._users: UsersService | None = None
        self._paymails: PaymailsServiceV2 | None = None
        self._contacts: ContactsServiceV2 | None = None
        self._outlines: OutlinesService | None = None
        self._record: RecordService | None = None
        self._tx_sync: TxSyncService | None = None

    def initialize(self) -> None:
        """Initialize all V2 services."""
        from spv_wallet.engine.v2.contacts.service import ContactsServiceV2
        from spv_wallet.engine.v2.paymails.service import PaymailsServiceV2
        from spv_wallet.engine.v2.transaction.outlines.service import OutlinesService
        from spv_wallet.engine.v2.transaction.record.service import RecordService
        from spv_wallet.engine.v2.transaction.txsync.service import TxSyncService
        from spv_wallet.engine.v2.users.service import UsersService

        self._users = UsersService(self._engine)
        self._paymails = PaymailsServiceV2(self._engine)
        self._contacts = ContactsServiceV2(self._engine)
        self._outlines = OutlinesService(self._engine)
        self._record = RecordService(self._engine)
        self._tx_sync = TxSyncService(self._engine)

    def close(self) -> None:
        """Tear down all V2 services."""
        self._users = None
        self._paymails = None
        self._contacts = None
        self._outlines = None
        self._record = None
        self._tx_sync = None

    @property
    def users(self) -> UsersService:
        """Get the V2 users service."""
        if self._users is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._users

    @property
    def paymails(self) -> PaymailsServiceV2:
        """Get the V2 paymails service."""
        if self._paymails is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._paymails

    @property
    def contacts(self) -> ContactsServiceV2:
        """Get the V2 contacts service."""
        if self._contacts is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._contacts

    @property
    def outlines(self) -> OutlinesService:
        """Get the V2 outlines service."""
        if self._outlines is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._outlines

    @property
    def record(self) -> RecordService:
        """Get the V2 record service."""
        if self._record is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._record

    @property
    def tx_sync(self) -> TxSyncService:
        """Get the V2 tx sync service."""
        if self._tx_sync is None:
            raise RuntimeError(self._ERR_NOT_INITIALIZED)
        return self._tx_sync
