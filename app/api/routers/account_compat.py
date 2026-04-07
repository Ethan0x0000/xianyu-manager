from __future__ import annotations

import logging
from collections.abc import Mapping
import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import (
    AccountCompatDetailResponse,
    AccountPauseDurationUpdateRequest,
    AccountRemarkUpdateRequest,
    AccountStatusUpdateRequest,
    PasswordLoginCreateResponse,
    PasswordLoginRequest,
    PasswordLoginStatusResponse,
    QRLoginCreateResponse,
    QRLoginStatusResponse,
    RefreshCookieRequest,
    RefreshCookieResponse,
)
from app.db.connection import get_db
from app.runtime.account_registry import get_registry
from app.services.login_service import LoginService, LoginValidationError
from app.shared.types import ServiceKey
from utils.refresh_util import refresh_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["accounts"])


def _get_login_service(request: Request) -> LoginService:
    app = cast(FastAPI, request.app)
    container = cast(
        Mapping[str, object] | None,
        getattr(app.state, "container", None),
    )
    if container is None or ServiceKey.LOGIN_SERVICE.value not in container:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login service unavailable",
        )
    return cast(LoginService, container[ServiceKey.LOGIN_SERVICE.value])


def _load_account_row(db_path: str, account_id: str) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, password, notes, enabled,
                       show_browser, pause_duration, created_at, updated_at
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )


def _require_account_row(db_path: str, account_id: str) -> sqlite3.Row:
    row = _load_account_row(db_path, account_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return row


def _cookie_status(cookie_value: str) -> str:
    return "available" if cookie_value.strip() else "missing"


def _map_account_detail(row: sqlite3.Row) -> AccountCompatDetailResponse:
    account_id = cast(str, row["account_id"])
    cookie_value = cast(str, row["cookie_str"] or "")
    username = cast(str, row["username"] or "")
    enabled = bool(cast(int, row["enabled"]))
    show_browser = bool(cast(int, row["show_browser"]))
    has_password = bool(cast(str, row["password"] or ""))
    remark = cast(str, row["notes"] or "")
    pause_duration = cast(int | None, row["pause_duration"])
    created_at = cast(str | None, row["created_at"])
    updated_at = cast(str | None, row["updated_at"])
    return AccountCompatDetailResponse(
        id=account_id,
        value=cookie_value,
        username=username,
        enabled=enabled,
        show_browser=show_browser,
        has_cookie=bool(cookie_value),
        cookie_status=_cookie_status(cookie_value),
        has_password=has_password,
        remark=remark,
        pause_duration=int(pause_duration) if pause_duration is not None else 10,
        created_at=created_at,
        updated_at=updated_at,
    )


def _format_cookie_string(cookie_map: dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookie_map.items() if name)


def _update_registry_cookie(account_id: str, cookie_value: str) -> None:
    entry = get_registry().get_account(account_id)
    if entry is not None:
        entry.cookie_str = cookie_value


def _update_account_cookie(
    db_path: str, account_id: str, cookie_value: str
) -> sqlite3.Row:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE xianyu_accounts
            SET cookie_str = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ?
            """,
            (cookie_value, account_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        row = cast(
            sqlite3.Row,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, password, notes, enabled,
                       show_browser, pause_duration, created_at, updated_at
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )
    _update_registry_cookie(account_id, cookie_value)
    return row


def _set_account_enabled(account_id: str, enabled: bool) -> None:
    registry = get_registry()
    entry = registry.get_account(account_id)
    if entry is None:
        return
    if enabled:
        registry.enable_account(account_id)
    else:
        registry.disable_account(account_id)


def _resolve_password_credentials(
    row: sqlite3.Row,
    payload: PasswordLoginRequest,
) -> tuple[str, str]:
    stored_username = cast(str, row["username"] or "")
    stored_password = cast(str, row["password"] or "")
    resolved_username = (payload.account or payload.username or stored_username).strip()
    resolved_password = (
        payload.password if payload.password is not None else stored_password
    ).strip()

    if payload.refresh_mode and (not stored_username or not stored_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="stored username/password are required for refresh mode",
        )

    if not resolved_username or not resolved_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="username/password are required for password login",
        )

    return resolved_username, resolved_password


@router.post("/qr-login/generate", response_model=QRLoginCreateResponse)
async def create_qr_login_session(
    request: Request,
    token: Annotated[str, Depends(verify_token)],
) -> QRLoginCreateResponse:
    del token
    service = _get_login_service(request)
    session = service.create_qr_session()
    return QRLoginCreateResponse(
        session_id=session.session_id,
        qr_code_url=session.qr_code_url,
        qr_image_data=session.qr_image_data,
        status="pending",
        expires_at=session.expires_at,
    )


@router.get("/qr-login/check/{session_id}", response_model=QRLoginStatusResponse)
async def get_qr_login_status(
    session_id: str,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
) -> QRLoginStatusResponse:
    del token
    service = _get_login_service(request)
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR login session not found",
        )

    session_status = "expired" if session.is_expired else session.status
    return QRLoginStatusResponse(
        session_id=session.session_id,
        status=session_status,
        qr_code_url=session.qr_code_url,
        qr_image_data=session.qr_image_data,
        expires_at=session.expires_at,
        result_cookie=session.result_cookie,
    )


@router.post("/password-login", response_model=PasswordLoginCreateResponse)
async def create_password_login_session(
    payload: PasswordLoginRequest,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> PasswordLoginCreateResponse:
    del token
    logger.info(
        "[%s] Password login request received (refresh=%s, show_browser=%s)",
        payload.account_id,
        payload.refresh_mode,
        payload.show_browser,
    )
    row = _require_account_row(db_path, payload.account_id)
    username, password = _resolve_password_credentials(row, payload)
    service = _get_login_service(request)
    try:
        session = await service.create_password_session(
            account_id=payload.account_id,
            username=username,
            password=password,
            refresh_mode=payload.refresh_mode,
            show_browser=payload.show_browser,
            db_path=db_path,
        )
    except LoginValidationError as exc:
        logger.warning(
            "[%s] Password login validation failed: %s",
            payload.account_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    logger.info(
        "[%s] Password login session started: %s",
        payload.account_id,
        session.session_id,
    )
    return PasswordLoginCreateResponse(
        session_id=session.session_id,
        status=session.status,
        message=session.message,
    )


@router.get(
    "/password-login/check/{session_id}",
    response_model=PasswordLoginStatusResponse,
)
async def get_password_login_status(
    session_id: str,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
) -> PasswordLoginStatusResponse:
    del token
    service = _get_login_service(request)
    session = service.get_password_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Password login session not found",
        )

    session_status = "expired" if session.is_expired else session.status
    # Cookie persistence is now handled by the background task in login_service.
    # This endpoint is read-only for password login status.

    return PasswordLoginStatusResponse(
        session_id=session.session_id,
        status=session_status,
        message=session.message,
        result_cookie=session.result_cookie,
        cookie_valid=bool(session.result_cookie and session.status == "success"),
        cookie_count=session.result_cookie.count("=") if session.result_cookie else 0,
        verification_url=session.verification_url,
        qr_code_url=session.qr_code_url,
        screenshot_path=session.screenshot_path,
        verification_type=session.verification_type,
        verification_message=session.verification_message,
    )


@router.delete(
    "/password-login/{session_id}",
    response_model=PasswordLoginStatusResponse,
)
async def cancel_password_login_session(
    session_id: str,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
) -> PasswordLoginStatusResponse:
    """Cancel an active password-login session."""
    del token
    service = _get_login_service(request)
    cancelled = service.cancel_password_session(session_id)
    if not cancelled:
        session = service.get_password_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Password login session not found",
            )
        # Session exists but is already in a terminal state — return current status
        return PasswordLoginStatusResponse(
            session_id=session.session_id,
            status=session.status,
            message=session.message,
        )

    session = service.get_password_session(session_id)
    assert session is not None  # cancel succeeded, so session exists
    return PasswordLoginStatusResponse(
        session_id=session.session_id,
        status=session.status,
        message=session.message,
    )


@router.get("/cookies/details", response_model=list[AccountCompatDetailResponse])
async def list_account_details(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[AccountCompatDetailResponse]:
    del token
    with get_db(db_path) as conn:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                """
            SELECT account_id, cookie_str, username, password, notes, enabled,
                   show_browser, pause_duration, created_at, updated_at
            FROM xianyu_accounts
            ORDER BY account_id
            """
            ).fetchall(),
        )
    return [_map_account_detail(row) for row in rows]


@router.get("/cookie/{account_id}/details", response_model=AccountCompatDetailResponse)
async def get_account_details(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    include_secrets: Annotated[bool, Query()] = False,
) -> AccountCompatDetailResponse:
    del token
    del include_secrets
    row = _require_account_row(db_path, account_id)
    return _map_account_detail(row)


@router.put("/cookies/{account_id}/status", response_model=AccountCompatDetailResponse)
async def update_account_status(
    account_id: str,
    payload: AccountStatusUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AccountCompatDetailResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE xianyu_accounts
            SET enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ?
            """,
            (int(payload.enabled), account_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        row = cast(
            sqlite3.Row,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, password, notes, enabled,
                       show_browser, pause_duration, created_at, updated_at
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )

    _set_account_enabled(account_id, payload.enabled)
    return _map_account_detail(row)


@router.put("/cookies/{account_id}/remark", response_model=AccountCompatDetailResponse)
async def update_account_remark(
    account_id: str,
    payload: AccountRemarkUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AccountCompatDetailResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE xianyu_accounts
            SET notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ?
            """,
            (payload.remark, account_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        row = cast(
            sqlite3.Row,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, password, notes, enabled,
                       show_browser, pause_duration, created_at, updated_at
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )
    return _map_account_detail(row)


@router.put(
    "/cookies/{account_id}/pause-duration",
    response_model=AccountCompatDetailResponse,
)
async def update_account_pause_duration(
    account_id: str,
    payload: AccountPauseDurationUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AccountCompatDetailResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE xianyu_accounts
            SET pause_duration = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ?
            """,
            (payload.pause_duration, account_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        row = cast(
            sqlite3.Row,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, password, notes, enabled,
                       show_browser, pause_duration, created_at, updated_at
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )
    return _map_account_detail(row)


@router.post("/qr-login/refresh-cookies", response_model=RefreshCookieResponse)
async def refresh_account_cookie(
    payload: RefreshCookieRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> RefreshCookieResponse:
    del token
    existing_row = _require_account_row(db_path, payload.cookie_id)
    try:
        refresh_result = cast(
            tuple[str | None, dict[str, str]],
            await refresh_token(payload.qr_cookies),
        )
        refresh_token_value, refreshed_cookies = refresh_result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cookie refresh failed: {exc}",
        ) from exc

    cookie_value = _format_cookie_string(refreshed_cookies) or payload.qr_cookies
    row = _update_account_cookie(db_path, payload.cookie_id, cookie_value)
    del existing_row
    del refresh_result
    del refresh_token_value
    return RefreshCookieResponse(
        cookie_id=payload.cookie_id,
        message="cookie_refreshed",
        cookie_status=_cookie_status(cookie_value),
        value=str(row["cookie_str"] or ""),
    )


__all__ = ["router"]
