from __future__ import annotations

from fastapi import APIRouter

from .accounts import router as accounts_router
from .auth import router as auth_router
from .items import router as items_router
from .replies import keywords_router, router as replies_router
from .runtime import router as runtime_router
from .shipping import delivery_router, router as shipping_router
from .system import router as system_router


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(system_router)
    router.include_router(auth_router)
    router.include_router(accounts_router)
    router.include_router(replies_router)
    router.include_router(keywords_router)
    router.include_router(shipping_router)
    router.include_router(delivery_router)
    router.include_router(items_router)
    router.include_router(runtime_router)
    return router


__all__ = ["build_router"]
