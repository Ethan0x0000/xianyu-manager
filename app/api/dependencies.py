from __future__ import annotations

from typing import Annotated, cast

from fastapi import Cookie, FastAPI, Header, HTTPException, Request, status

from app.auth.service import SESSION_COOKIE_NAME
from app.bootstrap.settings import Settings
from app.auth.sessions import get_session_store
from app.bootstrap.settings import load_settings


def get_db_path(request: Request) -> str:
    """Dependency: get database path from settings."""
    app = cast(FastAPI, request.app)
    app_settings = cast(Settings | None, getattr(app.state, "settings", None))
    if isinstance(app_settings, Settings):
        return app_settings.db_path

    try:
        return load_settings().db_path
    except Exception:
        return "data/xianyu_data.db"


def get_runtime_settings(request: Request) -> Settings:
    """Get runtime settings from app state.

    Returns the Settings instance attached to ``app.state`` which includes
    database-applied overrides (e.g. ``admin_password_hash`` persisted via
    the admin API).  Falls back to a fresh ``load_settings()`` call when
    app state is unavailable (e.g. during tests).
    """
    app = cast(FastAPI, request.app)
    app_settings = cast(Settings | None, getattr(app.state, "settings", None))
    if isinstance(app_settings, Settings):
        return app_settings
    return load_settings()


async def verify_token(
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    """Verify session token from Authorization header or secure cookie."""
    authorization = authorization or ""
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif session_cookie:
        token = session_cookie.strip()

    if not token or not get_session_store().validate_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return token


__all__ = ["get_db_path", "get_runtime_settings", "verify_token"]
