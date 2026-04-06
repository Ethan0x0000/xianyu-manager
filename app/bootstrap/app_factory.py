"""Application composition root for the rebuilt FastAPI app."""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import build_router
from app.bootstrap.runtime import RuntimeSupervisor
from app.bootstrap.settings import Settings, load_settings
from app.db.schema import initialize_database
from app.runtime.account_registry import get_registry
from app.runtime.token_refresh import TokenRefreshService
from app.runtime.ws_client import WebSocketClient
from app.services.ai_reply import AIReplyService
from app.services.auto_confirm import AutoConfirmService
from app.services.item_polish import ItemPolishService
from app.services.login_service import LoginService
from app.services.reply_policy import ReplyPolicyService
from app.services.shipping import ShippingService
from app.shared.types import DEFAULT_DB_PATH, ServiceKey

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _prepare_database_path(db_path: str) -> None:
    resolved_db_path = _resolve_project_path(db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)

    legacy_db_path = PROJECT_ROOT / resolved_db_path.name
    if (
        resolved_db_path.name == "xianyu_data.db"
        and legacy_db_path != resolved_db_path
        and legacy_db_path.exists()
        and not resolved_db_path.exists()
    ):
        _ = shutil.move(str(legacy_db_path), str(resolved_db_path))


def build_container(
    test_mode: bool = False,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Build the application service container."""

    if settings is None and not test_mode:
        settings = load_settings()

    db_path = settings.db_path if settings is not None else DEFAULT_DB_PATH

    container: dict[str, object] = {
        ServiceKey.ACCOUNT_REGISTRY.value: get_registry(),
        ServiceKey.WS_CLIENT.value: WebSocketClient,
        ServiceKey.TOKEN_REFRESH.value: TokenRefreshService,
        ServiceKey.REPLY_POLICY.value: ReplyPolicyService(db_path),
        ServiceKey.AI_REPLY.value: AIReplyService(db_path),
        ServiceKey.SHIPPING.value: ShippingService(db_path),
        ServiceKey.ITEM_POLISH.value: ItemPolishService,
        ServiceKey.AUTO_CONFIRM.value: AutoConfirmService(),
        ServiceKey.LOGIN_SERVICE.value: LoginService(),
        ServiceKey.SETTINGS.value: settings,
        ServiceKey.DB_PATH.value: db_path,
    }
    return dict(container)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = settings or load_settings()
    _prepare_database_path(settings.db_path)
    initialize_database(settings.db_path)

    container = build_container(settings=settings)
    runtime_supervisor = RuntimeSupervisor(container)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await runtime_supervisor.start()
        try:
            yield
        finally:
            await runtime_supervisor.stop()

    app = FastAPI(
        title="Xianyu Manager",
        description="Single-admin Xianyu management system",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.container = container
    app.state.runtime_supervisor = runtime_supervisor
    app.include_router(build_router())

    static_dir = PROJECT_ROOT / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/static/login.html")

    app.add_api_route("/", root_redirect, include_in_schema=False)

    return app


def get_service(container: Mapping[str, object], name: str) -> object:
    """Get a service from the container, raising if not registered."""

    if name not in container:
        raise KeyError(f"Service '{name}' is not registered in the container")
    return container[name]


__all__ = ["build_container", "create_app", "get_service"]
