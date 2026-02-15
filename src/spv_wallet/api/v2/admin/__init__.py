"""V2 admin endpoints.

Combines admin sub-routers into a single ``admin_router``.
"""

from fastapi import APIRouter

from spv_wallet.api.v2.admin.paymails import router as paymails_router
from spv_wallet.api.v2.admin.users import router as users_router
from spv_wallet.api.v2.admin.webhooks import router as webhooks_router

admin_router = APIRouter()

admin_router.include_router(users_router)
admin_router.include_router(paymails_router)
admin_router.include_router(webhooks_router)

__all__ = ["admin_router"]
