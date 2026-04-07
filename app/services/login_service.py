"""QR and password login service for Xianyu accounts.

Handles QR-code login session creation/polling and password-login orchestration.
Supports multiple Xianyu accounts under a single admin.

IMPORTANT SEPARATION:
- This service handles XIANYU ACCOUNT login (seller accounts)
- app/auth/ handles ADMIN LOGIN (the admin panel user)
- These are COMPLETELY SEPARATE concerns
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class LoginValidationError(Exception):
    """Raised when login input is invalid."""

    pass


class LoginTimeoutError(Exception):
    """Raised when QR code expires without being scanned."""

    pass


@dataclass
class QRLoginSession:
    """Represents a QR code login session."""

    session_id: str
    qr_code_url: str = ""
    qr_image_data: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 120)
    status: str = "pending"
    result_cookie: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class PasswordLoginSession:
    """Represents a password-login orchestration session."""

    session_id: str
    account_id: str
    username: str
    refresh_mode: bool = False
    show_browser: bool = False
    db_path: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 240)
    status: str = "processing"
    message: str = "login_initiated"
    result_cookie: str = ""
    verification_url: str = ""
    qr_code_url: str = ""
    screenshot_path: str = ""
    verification_type: str = ""
    verification_message: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class LoginService:
    """
    Manages Xianyu account login flows (QR and password).

    Multiple accounts can be logged in simultaneously under one admin session.
    Slider/captcha handoff is delegated to the browser automation layer.
    """

    def __init__(self) -> None:
        self._active_sessions: dict[str, QRLoginSession] = {}
        self._password_sessions: dict[str, PasswordLoginSession] = {}
        self._background_tasks: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # QR Login
    # ------------------------------------------------------------------

    def create_qr_session(self) -> QRLoginSession:
        """Create a new QR login session and return session metadata."""
        import uuid

        session_id = str(uuid.uuid4())
        session = QRLoginSession(
            session_id=session_id,
            qr_code_url=f"https://oauth.m.taobao.com/login/qr/code?sessionId={session_id}",
            status="pending",
        )
        self._active_sessions[session_id] = session
        logger.info("QR session created: %s", session_id)
        return session

    def get_session(self, session_id: str) -> QRLoginSession | None:
        """Get a QR session by ID."""
        return self._active_sessions.get(session_id)

    def invalidate_session(self, session_id: str) -> None:
        """Mark a session as expired/invalidated."""
        session = self._active_sessions.get(session_id)
        if session:
            session.status = "expired"

    # ------------------------------------------------------------------
    # Password Login
    # ------------------------------------------------------------------

    async def create_password_session(
        self,
        account_id: str,
        username: str,
        password: str,
        refresh_mode: bool = False,
        show_browser: bool = False,
        db_path: str = "",
    ) -> PasswordLoginSession:
        """Validate input, register a polling session, and launch background login."""
        import uuid

        if not username or not password:
            raise LoginValidationError(
                "username and password are required for password login"
            )
        if not account_id:
            raise LoginValidationError("account_id is required")

        session_id = str(uuid.uuid4())
        session = PasswordLoginSession(
            session_id=session_id,
            account_id=account_id,
            username=username,
            refresh_mode=refresh_mode,
            show_browser=show_browser,
            db_path=db_path,
            status="processing",
            message="login_initiated",
        )
        self._password_sessions[session_id] = session
        logger.info(
            "[%s] Password session created: %s (refresh=%s, show_browser=%s)",
            account_id,
            session_id,
            refresh_mode,
            show_browser,
        )

        # Launch background browser automation
        task = asyncio.create_task(
            self._execute_password_login(session, password),
            name=f"password-login-{account_id}-{session_id[:8]}",
        )
        self._background_tasks[session_id] = task
        task.add_done_callback(lambda _t: self._background_tasks.pop(session_id, None))

        return session

    async def _execute_password_login(
        self,
        session: PasswordLoginSession,
        password: str,
    ) -> None:
        """Background task: run browser-based password login and update session."""
        account_id = session.account_id
        start_time = time.monotonic()
        logger.info(
            "[%s] Background login task started (session=%s)",
            account_id,
            session.session_id,
        )

        session.message = "正在准备浏览器环境..."
        slider_instance = None

        try:
            from utils.xianyu_slider_stealth import XianyuSliderStealth

            def _run_login() -> dict[str, str] | None:
                nonlocal slider_instance
                logger.info(
                    "[%s] Creating browser instance (headless=%s)",
                    account_id,
                    not session.show_browser,
                )
                slider_instance = XianyuSliderStealth(
                    user_id=account_id,
                    enable_learning=True,
                    headless=not session.show_browser,
                )

                def _on_verification_required(
                    message: str,
                    screenshot_path_or_none=None,
                    frame_url: str | None = None,
                    screenshot_path: str | None = None,
                    **kwargs,
                ):
                    """Callback invoked by Playwright when QR/face verification is needed."""
                    vtype = kwargs.get("verification_type", "unknown")
                    # Normalise: sync callback signature is (msg, None, frame_url, screenshot_path, ...)
                    actual_screenshot = screenshot_path or screenshot_path_or_none or ""
                    actual_url = frame_url or ""

                    session.status = "verification_required"
                    session.message = message or "需要身份验证"
                    session.verification_url = actual_url
                    session.screenshot_path = actual_screenshot
                    session.verification_type = vtype
                    session.verification_message = message or ""
                    logger.info(
                        "[%s] Verification required: type=%s, screenshot=%s, url=%s",
                        account_id,
                        vtype,
                        actual_screenshot[:80] if actual_screenshot else "",
                        actual_url[:80] if actual_url else "",
                    )

                logger.info("[%s] Browser instance ready, starting login", account_id)
                return slider_instance.login_with_password_playwright(
                    account=session.username,
                    password=password,
                    show_browser=session.show_browser,
                    notification_callback=_on_verification_required,
                    force_clean_context=session.refresh_mode,
                )

            session.message = "正在启动浏览器并执行登录..."
            logger.info(
                "[%s] Launching browser automation (headless=%s)",
                account_id,
                not session.show_browser,
            )

            cookies = await asyncio.to_thread(_run_login)

            elapsed = time.monotonic() - start_time

            if cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

                has_unb = bool(cookies.get("unb"))
                companion_keys = (
                    "cookie2",
                    "_m_h5_tk",
                    "_m_h5_tk_enc",
                    "sgcookie",
                    "t",
                    "cna",
                )
                has_companion = any(cookies.get(k) for k in companion_keys)

                if has_unb and has_companion:
                    session.result_cookie = cookie_str
                    session.status = "success"
                    session.message = f"登录成功，获取到 {len(cookies)} 个有效 Cookie"
                    logger.info(
                        "[%s] Password login succeeded: %d cookies, "
                        "duration=%.1fs, session=%s",
                        account_id,
                        len(cookies),
                        elapsed,
                        session.session_id,
                    )
                    self._persist_login_to_db(session, cookie_str, password)
                elif has_unb:
                    session.result_cookie = cookie_str
                    session.status = "success"
                    session.message = (
                        f"登录成功，获取到 {len(cookies)} 个Cookie"
                        f"（部分关键字段缺失，可能需要刷新）"
                    )
                    logger.warning(
                        "[%s] Password login partial: has unb but "
                        "missing companion cookies, duration=%.1fs",
                        account_id,
                        elapsed,
                    )
                    self._persist_login_to_db(session, cookie_str, password)
                else:
                    missing = []
                    if not has_unb:
                        missing.append("unb")
                    if not has_companion:
                        missing.append("companion cookies")
                    session.status = "failed"
                    session.message = (
                        f"登录返回 {len(cookies)} 个Cookie，"
                        f"但缺少关键字段: {', '.join(missing)}"
                    )
                    logger.warning(
                        "[%s] Password login returned cookies but missing "
                        "essential fields (%s), duration=%.1fs, session=%s",
                        account_id,
                        ", ".join(missing),
                        elapsed,
                        session.session_id,
                    )
            else:
                error_detail = ""
                if slider_instance:
                    error_detail = (
                        getattr(slider_instance, "last_login_error", "") or ""
                    )
                session.status = "failed"
                session.message = error_detail or "登录失败，未获取到 Cookie"
                logger.warning(
                    "[%s] Password login failed: %s, duration=%.1fs, session=%s",
                    account_id,
                    session.message,
                    elapsed,
                    session.session_id,
                )

        except asyncio.CancelledError:
            session.status = "cancelled"
            session.message = "登录任务已取消"
            logger.info(
                "[%s] Password login task cancelled, session=%s",
                account_id,
                session.session_id,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            session.status = "error"
            session.message = f"登录异常：{exc}"
            logger.error(
                "[%s] Password login error after %.1fs: %s",
                account_id,
                elapsed,
                exc,
            )
            logger.debug("[%s] Traceback:\n%s", account_id, traceback.format_exc())

        finally:
            # Ensure concurrency slot + temp directory cleanup regardless of
            # how login_with_password_headful exited.  The method's own finally
            # block closes the DrissionPage browser but does NOT release the
            # concurrency slot — we handle it here as a safety net.
            if slider_instance is not None:
                try:
                    from utils.xianyu_slider_stealth import concurrency_manager

                    concurrency_manager.unregister_instance(slider_instance.user_id)
                except Exception:
                    pass
                try:
                    import shutil

                    temp_dir = getattr(slider_instance, "temp_dir", None)
                    if temp_dir:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

    @staticmethod
    def _persist_login_to_db(
        session: PasswordLoginSession,
        cookie_str: str,
        password: str,
    ) -> None:
        """Persist validated cookies + credentials to DB immediately."""
        if not session.db_path:
            logger.warning(
                "[%s] No db_path available, skipping DB persistence",
                session.account_id,
            )
            return
        try:
            from app.db.connection import get_db
            from app.runtime.account_registry import get_registry

            with get_db(session.db_path) as conn:
                conn.execute(
                    """UPDATE xianyu_accounts
                       SET cookie_str = ?,
                           username = ?,
                           password = ?,
                           show_browser = ?,
                           updated_at = CURRENT_TIMESTAMP
                       WHERE account_id = ?""",
                    (
                        cookie_str,
                        session.username,
                        password,
                        1 if session.show_browser else 0,
                        session.account_id,
                    ),
                )
            entry = get_registry().get_account(session.account_id)
            if entry is not None:
                entry.cookie_str = cookie_str
            logger.info(
                "[%s] Cookie + credentials persisted to DB from background task",
                session.account_id,
            )
        except Exception as exc:
            logger.error(
                "[%s] Failed to persist login data to DB: %s",
                session.account_id,
                exc,
            )

    def get_password_session(self, session_id: str) -> PasswordLoginSession | None:
        """Get a password-login session by ID."""
        return self._password_sessions.get(session_id)

    def cancel_password_session(self, session_id: str) -> bool:
        """Cancel an active password-login session.

        Returns True if the session was cancelled, False if not found or
        already in a terminal state.
        """
        session = self._password_sessions.get(session_id)
        if session is None:
            return False
        if session.status in ("success", "failed", "error", "cancelled"):
            return False

        session.status = "cancelled"
        session.message = "登录已取消"
        logger.info(
            "[%s] Password session cancelled: %s",
            session.account_id,
            session_id,
        )

        # Cancel the background task if still running
        task = self._background_tasks.get(session_id)
        if task and not task.done():
            task.cancel()

        return True

    def active_session_count(self) -> int:
        """Return count of active (non-expired) sessions."""
        return sum(
            1 for session in self._active_sessions.values() if not session.is_expired
        )
