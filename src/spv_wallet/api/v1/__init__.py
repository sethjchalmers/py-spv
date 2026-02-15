"""V1 REST API routes.

Combines all sub-routers under the ``/api/v1`` prefix.
"""

from fastapi import APIRouter

from spv_wallet.api.v1.access_keys import router as access_keys_router
from spv_wallet.api.v1.admin import router as admin_router
from spv_wallet.api.v1.contacts import router as contacts_router
from spv_wallet.api.v1.merkleroots import router as merkleroots_router
from spv_wallet.api.v1.paymails import router as paymails_router
from spv_wallet.api.v1.shared_config import router as shared_config_router
from spv_wallet.api.v1.transactions import router as transactions_router
from spv_wallet.api.v1.users import router as users_router
from spv_wallet.api.v1.utxos import router as utxos_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(users_router)
v1_router.include_router(transactions_router)
v1_router.include_router(utxos_router)
v1_router.include_router(contacts_router)
v1_router.include_router(access_keys_router)
v1_router.include_router(paymails_router)
v1_router.include_router(merkleroots_router)
v1_router.include_router(shared_config_router)
v1_router.include_router(admin_router)

__all__ = ["v1_router"]
