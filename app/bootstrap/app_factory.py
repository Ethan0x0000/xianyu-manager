"""Application composition root for the rebuilt FastAPI app."""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope
from typing_extensions import override

from app.api.routers import register_routers
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


class SPAStaticFiles(StaticFiles):
    """Static-files mount with SPA fallback.

    When a requested path does not correspond to an existing file, serves
    ``index.html`` so that the React SPA router can handle the URL.
    """

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except Exception:
            # File not found – return the SPA entry point
            return await super().get_response("index.html", scope)


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _resolve_frontend_dir(settings: Settings) -> Path:
    frontend_dir = _resolve_project_path(settings.frontend_dist_dir)
    if (frontend_dir / "index.html").exists():
        return frontend_dir

    bundled_frontend_dir = _resolve_project_path(settings.frontend_bundled_dist_dir)
    if (bundled_frontend_dir / "index.html").exists():
        return bundled_frontend_dir

    return frontend_dir


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

    frontend_dir = _resolve_frontend_dir(settings)
    upload_dir = _resolve_project_path(settings.uploads_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "images").mkdir(parents=True, exist_ok=True)

    app.state.settings = settings
    app.state.container = container
    app.state.runtime_supervisor = runtime_supervisor
    app.state.frontend_dir = frontend_dir
    app.state.upload_dir = upload_dir
    register_routers(app)

    # Serve uploaded images under /uploads/
    if upload_dir.exists():
        app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    # SPA mount: Vite build output lives in frontend/dist/; the SPAStaticFiles
    # class returns index.html for any path that doesn't match a real file,
    # so the React router handles client-side URLs like /login, /dashboard.
    if frontend_dir.exists() and (frontend_dir / "index.html").exists():
        app.mount(
            "/",
            SPAStaticFiles(directory=str(frontend_dir), html=True),
            name="spa",
        )

    return app


def get_service(container: Mapping[str, object], name: str) -> object:
    """Get a service from the container, raising if not registered."""

    if name not in container:
        raise KeyError(f"Service '{name}' is not registered in the container")
    return container[name]


__all__ = ["build_container", "create_app", "get_service"]
