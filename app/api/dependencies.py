from __future__ import annotations

from typing import Annotated, cast

from fastapi import FastAPI, Header, HTTPException, Request, status

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


async def verify_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Verify bearer token from Authorization header."""
    authorization = authorization or ""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token or not get_session_store().validate_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return token


__all__ = ["get_db_path", "verify_token"]
