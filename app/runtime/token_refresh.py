"""Token refresh and cookie protection service.

Extracts the _m_h5_tk refresh, cookie merge/protection, and captcha-triggered
recovery from the legacy XianyuAutoAsync.py monolith.

FROZEN INVARIANTS:
- Protected cookie fields: _m_h5_tk, _m_h5_tk_enc, cookie2, t (from analysis)
- Cookie merge preserves these fields even if incoming dict is missing them
- Refresh triggers: timeout, 401 response, captcha event
"""

from __future__ import annotations

import logging
from typing import cast

from app.runtime.captcha_bridge import SliderAdapter, SliderValidationError

logger = logging.getLogger(__name__)

# Cookie fields that must NEVER be overwritten by incoming cookie updates
PROTECTED_COOKIE_FIELDS = frozenset(
    [
        "_m_h5_tk",
        "_m_h5_tk_enc",
        "cookie2",
        "t",
        "uc1",
        "unb",
    ]
)


class TokenRefreshError(Exception):
    """Raised when token refresh inputs are invalid."""


class TokenRefreshService:
    """
    Service for managing Xianyu _m_h5_tk token refresh and cookie protection.

    Handles:
    - Cookie field protection during incoming updates
    - Token refresh triggering
    - Captcha recovery routing
    """

    def __init__(self, account_id: str) -> None:
        if not account_id:
            raise TokenRefreshError("account_id is required")
        self.account_id: str = account_id
        self._refresh_count: int = 0

    def merge_cookies_protected(
        self,
        existing: object,
        incoming: object,
        protected_fields: frozenset[str] = PROTECTED_COOKIE_FIELDS,
    ) -> dict[str, str]:
        """
        Merge incoming cookie dict into existing, preserving protected fields.

        Protected fields from 'existing' are never overwritten by 'incoming',
        even if 'incoming' contains different or missing values for them.

        Args:
            existing: Current cookie dict with protected fields
            incoming: New cookie data (e.g., from server response)
            protected_fields: Set of field names to preserve from 'existing'

        Returns:
            Merged cookie dict with protected fields preserved
        """
        if not isinstance(existing, dict):
            raise TokenRefreshError("existing cookies must be a dict")
        if not isinstance(incoming, dict):
            raise TokenRefreshError("incoming cookies must be a dict")

        existing_cookies = cast(dict[str, str], existing)
        incoming_cookies = cast(dict[str, str], incoming)
        merged = {**incoming_cookies}

        for field in protected_fields:
            if field in existing_cookies:
                merged[field] = existing_cookies[field]

        return merged

    async def trigger_refresh(
        self,
        cookie_str: str | None,
        token: str | None,
    ) -> bool:
        """
        Trigger a token refresh for this account.

        Args:
            cookie_str: Current cookie string
            token: Current _m_h5_tk token value

        Returns:
            True if refresh succeeded, False otherwise

        Raises:
            TokenRefreshError: If inputs are invalid
        """
        if not cookie_str:
            raise TokenRefreshError("cookie_str is required for token refresh")
        if token is None:
            raise TokenRefreshError("token is required for token refresh")

        self._refresh_count += 1
        logger.info(
            "[%s] Token refresh triggered (count: %s)",
            self.account_id,
            self._refresh_count,
        )
        # Actual HTTP refresh implementation goes here in later tasks
        return False  # Stub: returns False until wired to real HTTP client

    def parse_token_from_cookies(self, cookie_str: str) -> str | None:
        """Extract _m_h5_tk token value from cookie string."""
        if not cookie_str:
            return None
        for part in cookie_str.split(";"):
            part = part.strip()
            if part.startswith("_m_h5_tk="):
                value = part[len("_m_h5_tk=") :]
                # Token is in format "value_timestamp"
                return value.split("_")[0] if "_" in value else value
        return None

    async def recover_from_captcha(
        self,
        verification_url: str | None,
        *,
        slider_adapter: SliderAdapter | None = None,
        risk_session_id: object | None = None,
        risk_trigger_scene: object | None = None,
    ) -> dict[str, object]:
        """Route captcha-triggered recovery through the frozen slider adapter."""
        if not verification_url:
            raise TokenRefreshError("verification_url is required for captcha recovery")

        adapter = slider_adapter or SliderAdapter()
        try:
            return await adapter.handle_captcha(
                verification_url,
                self.account_id,
                user_id=self.account_id,
                enable_learning=True,
                headless=True,
                risk_session_id=risk_session_id,
                risk_trigger_scene=risk_trigger_scene,
            )
        except SliderValidationError as exc:
            raise TokenRefreshError(str(exc)) from exc


__all__ = [
    "PROTECTED_COOKIE_FIELDS",
    "TokenRefreshError",
    "TokenRefreshService",
]
