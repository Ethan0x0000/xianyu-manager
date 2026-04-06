"""QR and password login service for Xianyu accounts.

Handles QR-code login session creation/polling and password-login orchestration.
Supports multiple Xianyu accounts under a single admin.

IMPORTANT SEPARATION:
- This service handles XIANYU ACCOUNT login (seller accounts)
- app/auth/ handles ADMIN LOGIN (the admin panel user)
- These are COMPLETELY SEPARATE concerns
"""

from __future__ import annotations

import logging
import time
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
    Slider/captcha handoff is delegated to
    app.runtime.captcha_bridge.SliderAdapter.
    """

    def __init__(self) -> None:
        self._active_sessions: dict[str, QRLoginSession] = {}
        self._password_sessions: dict[str, PasswordLoginSession] = {}

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

    async def initiate_password_login(
        self,
        account_id: str,
        username: str,
        password: str,
    ) -> dict[str, str]:
        """Initiate password-based Xianyu account login."""
        if not username or not password:
            raise LoginValidationError(
                "username and password are required for password login"
            )
        if not account_id:
            raise LoginValidationError("account_id is required")

        logger.info("[%s] Password login initiated", account_id)
        return {"status": "pending", "message": "login_initiated"}

    async def create_password_session(
        self,
        account_id: str,
        username: str,
        password: str,
        refresh_mode: bool = False,
        show_browser: bool = False,
    ) -> PasswordLoginSession:
        """Validate password-login input and register a polling session."""
        import uuid

        result = await self.initiate_password_login(account_id, username, password)
        session_id = str(uuid.uuid4())
        session = PasswordLoginSession(
            session_id=session_id,
            account_id=account_id,
            username=username,
            refresh_mode=refresh_mode,
            show_browser=show_browser,
            status="processing",
            message=str(result.get("message") or "login_initiated"),
        )
        self._password_sessions[session_id] = session
        logger.info("[%s] Password session created: %s", account_id, session_id)
        return session

    def get_password_session(self, session_id: str) -> PasswordLoginSession | None:
        """Get a password-login session by ID."""
        return self._password_sessions.get(session_id)

    def active_session_count(self) -> int:
        """Return count of active (non-expired) sessions."""
        return sum(
            1 for session in self._active_sessions.values() if not session.is_expired
        )
