from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.dependencies import get_runtime_settings, verify_token
from app.api.schemas import (
    LoginInfoStatusResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    VerifyResponse,
)
from app.auth.rate_limiter import get_rate_limiter
from app.auth.service import (
    SESSION_COOKIE_NAME,
    create_session_token,
    verify_admin_login,
)
from app.auth.sessions import get_session_store
from app.bootstrap.settings import (
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    Settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
legacy_router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting reverse-proxy headers."""
    client_host = request.client.host if request.client else ""
    if _is_trusted_proxy(client_host):
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        if forwarded:
            return forwarded

        real_ip = (request.headers.get("X-Real-IP") or "").strip()
        if real_ip:
            return real_ip

    if client_host:
        return client_host

    return "unknown"


def _is_trusted_proxy(client_host: str) -> bool:
    if not client_host:
        return False
    if client_host == "testclient":
        return True

    try:
        ip = ipaddress.ip_address(client_host)
    except ValueError:
        return client_host in {"localhost"}

    if ip.is_loopback or ip.is_link_local:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        return any(
            ip in network
            for network in (
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
            )
        )

    return ip in ipaddress.ip_network("fc00::/7")


def _build_verify_response(settings: Settings) -> VerifyResponse:
    return VerifyResponse(username=settings.admin_username)


def _set_session_cookie(
    response: Response, request: Request, session_token: str
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        max_age=86400,
        path="/",
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=request.url.scheme == "https",
    )


def _revoke_session(session_token: str) -> LogoutResponse:
    get_session_store().revoke_session(session_token)
    return LogoutResponse()


def _build_login_info_status_response(settings: Settings) -> LoginInfoStatusResponse:
    return LoginInfoStatusResponse(
        enabled=(
            settings.admin_username == DEFAULT_ADMIN_USERNAME
            and verify_admin_login(
                DEFAULT_ADMIN_USERNAME,
                DEFAULT_ADMIN_PASSWORD,
                settings,
            )
        )
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> LoginResponse:
    client_ip = _get_client_ip(request)
    limiter = get_rate_limiter()

    # Periodic cleanup
    _ = limiter.cleanup_expired()

    # Check IP block
    ip_blocked, ip_reason, _ = limiter.check_ip(client_ip)
    if ip_blocked:
        logger.warning("IP %s login blocked: %s", client_ip, ip_reason)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ip_reason,
        )

    # Check user lock
    if payload.username:
        user_locked, user_reason, _ = limiter.check_user(payload.username)
        if user_locked:
            logger.warning(
                "User '%s' login locked (IP: %s): %s",
                payload.username,
                client_ip,
                user_reason,
            )
            limiter.record_failure(client_ip, payload.username)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=user_reason,
            )

    # Verify credentials
    if not verify_admin_login(payload.username, payload.password, settings):
        limiter.record_failure(client_ip, payload.username)

        # Progressive response delay
        delay = limiter.get_response_delay(client_ip)
        if delay > 0:
            logger.info("IP %s login failed, delaying response %.1fs", client_ip, delay)
            await asyncio.sleep(delay)

        logger.warning("Login failed for '%s' (IP: %s)", payload.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Success
    limiter.record_success(client_ip, payload.username)
    token = create_session_token(settings.secret_key)
    _ = get_session_store().create_session(token)
    _set_session_cookie(response, request, token)
    logger.info("Login succeeded for '%s' (IP: %s)", payload.username, client_ip)
    return LoginResponse(token="")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    token: Annotated[str, Depends(verify_token)],
    request: Request,
    response: Response,
) -> LogoutResponse:
    _clear_session_cookie(response, request)
    return _revoke_session(token)


@router.get("/verify", response_model=VerifyResponse)
async def verify(
    token: Annotated[str, Depends(verify_token)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> VerifyResponse:
    del token
    return _build_verify_response(settings)


@router.get("/login-info-status", response_model=LoginInfoStatusResponse)
async def auth_login_info_status(
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> LoginInfoStatusResponse:
    return _build_login_info_status_response(settings)


@legacy_router.post("/logout", response_model=LogoutResponse)
async def legacy_logout(
    token: Annotated[str, Depends(verify_token)],
    request: Request,
    response: Response,
) -> LogoutResponse:
    _clear_session_cookie(response, request)
    return _revoke_session(token)


@legacy_router.get("/verify", response_model=VerifyResponse)
async def legacy_verify(
    token: Annotated[str, Depends(verify_token)],
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> VerifyResponse:
    del token
    return _build_verify_response(settings)


@legacy_router.get("/login-info-status", response_model=LoginInfoStatusResponse)
async def login_info_status(
    settings: Annotated[Settings, Depends(get_runtime_settings)],
) -> LoginInfoStatusResponse:
    return _build_login_info_status_response(settings)


__all__ = ["legacy_router", "router"]
