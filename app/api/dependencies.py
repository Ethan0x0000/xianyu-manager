from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.auth.sessions import get_session_store
from app.bootstrap.settings import load_settings


def get_db_path() -> str:
    """Dependency: get database path from settings."""
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
