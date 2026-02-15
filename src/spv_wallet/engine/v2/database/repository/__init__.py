"""V2 repositories — data access layer.

Each repository encapsulates all database queries for its entity,
following the repository pattern (matching Go's engine/v2/database/repository/).
"""

from spv_wallet.engine.v2.database.repository.addresses import AddressRepository
from spv_wallet.engine.v2.database.repository.operations import OperationRepository
from spv_wallet.engine.v2.database.repository.outputs import OutputRepository
from spv_wallet.engine.v2.database.repository.paymails import PaymailRepository
from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository
from spv_wallet.engine.v2.database.repository.users import UserRepository

__all__ = [
    "AddressRepository",
    "OperationRepository",
    "OutputRepository",
    "PaymailRepository",
    "TransactionRepository",
    "UserRepository",
]
