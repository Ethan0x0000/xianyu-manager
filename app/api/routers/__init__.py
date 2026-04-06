from __future__ import annotations

from importlib import import_module
from typing import cast

from fastapi import APIRouter, FastAPI

from .accounts import router as accounts_router
from .auth import legacy_router as legacy_auth_router, router as auth_router
from .items import router as items_router
from .replies import keywords_router, router as replies_router
from .runtime import router as runtime_router
from .shipping import delivery_router, router as shipping_router
from .stream import router as stream_router
from .system import router as system_router
from .uploads import router as uploads_router

account_compat_router = cast(
    APIRouter,
    import_module("app.api.routers.account_compat").router,
)

ROUTERS = (
    system_router,
    auth_router,
    legacy_auth_router,
    account_compat_router,
    accounts_router,
    replies_router,
    keywords_router,
    shipping_router,
    delivery_router,
    items_router,
    runtime_router,
    uploads_router,
    stream_router,
)


def build_router() -> APIRouter:
    router = APIRouter()
    for child_router in ROUTERS:
        router.include_router(child_router)
    return router


def register_routers(app: FastAPI) -> None:
    for router in ROUTERS:
        app.include_router(router)


__all__ = ["build_router", "register_routers"]
