from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import verify_token
from app.api.schemas import LoginRequest, LoginResponse, LogoutResponse
from app.auth.service import create_session_token, verify_admin_login
from app.auth.sessions import get_session_store
from app.bootstrap.settings import load_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    settings = load_settings()
    if not verify_admin_login(payload.username, payload.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_session_token(settings.secret_key)
    _ = get_session_store().create_session(token)
    return LoginResponse(token=token)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    token: Annotated[str, Depends(verify_token)],
    authorization: Annotated[str | None, Header()] = None,
) -> LogoutResponse:
    del token
    authorization = authorization or ""
    session_token = authorization.removeprefix("Bearer ").strip()
    get_session_store().revoke_session(session_token)
    return LogoutResponse()


__all__ = ["router"]
