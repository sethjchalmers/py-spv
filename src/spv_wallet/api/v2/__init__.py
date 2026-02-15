"""V2 REST API routes.

Combines all sub-routers under the ``/api/v2`` prefix.
"""

from fastapi import APIRouter

from spv_wallet.api.v2.admin import admin_router
from spv_wallet.api.v2.callbacks import router as callbacks_router
from spv_wallet.api.v2.contacts import router as contacts_router
from spv_wallet.api.v2.data import router as data_router
from spv_wallet.api.v2.operations import router as operations_router
from spv_wallet.api.v2.transactions import router as transactions_router
from spv_wallet.api.v2.users import router as users_router

v2_router = APIRouter(prefix="/api/v2")

v2_router.include_router(users_router)
v2_router.include_router(transactions_router)
v2_router.include_router(operations_router)
v2_router.include_router(contacts_router)
v2_router.include_router(data_router)
v2_router.include_router(callbacks_router)
v2_router.include_router(admin_router)

__all__ = ["v2_router"]
