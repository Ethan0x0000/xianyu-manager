from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import verify_token
from app.api.schemas import (
    LoginInfoStatusResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    VerifyResponse,
)
from app.auth.service import create_session_token, verify_admin_login
from app.auth.sessions import get_session_store
from app.bootstrap.settings import (
    DEFAULT_ADMIN_PASSWORD_HASH,
    DEFAULT_ADMIN_USERNAME,
    load_settings,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
legacy_router = APIRouter(tags=["auth"])


def _build_verify_response() -> VerifyResponse:
    settings = load_settings()
    return VerifyResponse(username=settings.admin_username)


def _revoke_session(authorization: str | None) -> LogoutResponse:
    authorization = authorization or ""
    session_token = authorization.removeprefix("Bearer ").strip()
    get_session_store().revoke_session(session_token)
    return LogoutResponse()


def _build_login_info_status_response() -> LoginInfoStatusResponse:
    settings = load_settings()
    return LoginInfoStatusResponse(
        enabled=(
            settings.admin_username == DEFAULT_ADMIN_USERNAME
            and settings.admin_password_hash == DEFAULT_ADMIN_PASSWORD_HASH
        )
    )


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
    return _revoke_session(authorization)


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    token: Annotated[str, Depends(verify_token)],
) -> VerifyResponse:
    del token
    return _build_verify_response()


@router.get("/login-info-status", response_model=LoginInfoStatusResponse)
async def auth_login_info_status() -> LoginInfoStatusResponse:
    return _build_login_info_status_response()


@legacy_router.post("/logout", response_model=LogoutResponse)
async def legacy_logout(
    token: Annotated[str, Depends(verify_token)],
    authorization: Annotated[str | None, Header()] = None,
) -> LogoutResponse:
    del token
    return _revoke_session(authorization)


@legacy_router.get("/verify", response_model=VerifyResponse)
async def legacy_verify(
    token: Annotated[str, Depends(verify_token)],
) -> VerifyResponse:
    del token
    return _build_verify_response()


@legacy_router.get("/login-info-status", response_model=LoginInfoStatusResponse)
async def login_info_status() -> LoginInfoStatusResponse:
    return _build_login_info_status_response()


__all__ = ["legacy_router", "router"]
