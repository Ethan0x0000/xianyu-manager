"""Captcha/slider adapter module.

Provides a stable import boundary for the frozen slider anti-detection subsystem.
The internals of utils/xianyu_slider_stealth.py, utils/slider_patch.py, etc.
are NOT modified — only the entry surface is normalized here.

FROZEN ZONE: Do not refactor slider internals.
"""

from __future__ import annotations

import logging
from typing import Protocol, cast

logger = logging.getLogger(__name__)


class StealthRunnerProtocol(Protocol):
    """Protocol for the frozen slider runner instance."""

    risk_session_id: object | None
    risk_trigger_scene: object | None

    async def async_run(self, url: str) -> tuple[bool, dict[str, str] | None]: ...


class StealthRunnerFactory(Protocol):
    """Protocol for the frozen slider runner constructor."""

    def __call__(
        self, *, user_id: str, enable_learning: bool, headless: bool
    ) -> StealthRunnerProtocol: ...


class RemoteControllerProtocol(Protocol):
    """Protocol for the frozen remote captcha controller singleton."""

    async def create_session(
        self, session_id: str, page: object
    ) -> dict[str, object]: ...

    async def handle_mouse_event(
        self, session_id: str, event_type: str, x: int, y: int
    ) -> bool: ...

    async def check_completion(self, session_id: str) -> bool: ...

    async def close_session(self, session_id: str) -> None: ...

    def session_exists(self, session_id: str) -> bool: ...

    def is_completed(self, session_id: str) -> bool: ...


class SliderPatchHandler(Protocol):
    """Protocol for the frozen slider patch entrypoint."""

    def __call__(self, page: object, user_id: str, max_attempts: int = 5) -> bool: ...


class SliderValidationError(Exception):
    """Raised when slider/captcha input is invalid."""


class SliderAdapter:
    """Stable adapter over the frozen Goofish captcha subsystem."""

    def __init__(self) -> None:
        self._stealth_module: object | None = None
        self._stealth_class: StealthRunnerFactory | None = None
        self._remote_control: RemoteControllerProtocol | None = None
        self._slider_patch_module: object | None = None
        self._slider_patch_handler: SliderPatchHandler | None = None
        self._initialized: bool = False

    def _ensure_initialized(self) -> None:
        """Lazy-initialize frozen slider-related modules."""
        if self._initialized:
            return

        try:
            import utils.xianyu_slider_stealth as stealth

            slider_class = getattr(stealth, "XianyuSliderStealth", None)
            if slider_class is None:
                logger.warning("SliderAdapter: XianyuSliderStealth missing from module")
            else:
                self._stealth_module = stealth
                self._stealth_class = cast(StealthRunnerFactory, slider_class)
                logger.info("SliderAdapter: stealth module loaded")
        except ImportError as exc:
            logger.warning("SliderAdapter: could not load stealth module: %s", exc)

        try:
            from utils.captcha_remote_control import captcha_controller

            self._remote_control = cast(
                RemoteControllerProtocol, cast(object, captcha_controller)
            )
            logger.info("SliderAdapter: remote controller loaded")
        except ImportError as exc:
            logger.warning("SliderAdapter: could not load remote controller: %s", exc)

        try:
            import utils.slider_patch as slider_patch

            handler = getattr(slider_patch, "_handle_slider_verification", None)
            if handler is None:
                logger.warning("SliderAdapter: slider patch entrypoint missing")
            else:
                self._slider_patch_module = slider_patch
                self._slider_patch_handler = cast(
                    SliderPatchHandler, cast(object, handler)
                )
                logger.info("SliderAdapter: slider patch module loaded")
        except ImportError as exc:
            logger.warning("SliderAdapter: could not load slider patch module: %s", exc)

        self._initialized = True

    @staticmethod
    def _require_text(value: str | None, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise SliderValidationError(
                f"{field_name} is required for captcha handling"
            )
        return text

    def validate_captcha_request(
        self, verification_url: str | None, session_id: str | None
    ) -> None:
        """Validate captcha request inputs. Raises SliderValidationError if invalid."""
        _ = self._require_text(verification_url, "verification_url")
        _ = self._require_text(session_id, "session_id")

    @staticmethod
    def _coerce_flag(value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        return default

    def _require_session_id(self, session_id: str | None) -> str:
        return self._require_text(session_id, "session_id")

    async def handle_captcha(
        self,
        verification_url: str | None,
        session_id: str | None,
        **kwargs: object,
    ) -> dict[str, object]:
        """Handle a captcha verification request via the frozen stealth runner."""
        self.validate_captcha_request(verification_url, session_id)
        self._ensure_initialized()

        verification_url = self._require_text(verification_url, "verification_url")
        session_id = self._require_text(session_id, "session_id")

        logger.info("SliderAdapter: handling captcha for session %s", session_id)

        if self._stealth_class is None:
            logger.warning(
                "SliderAdapter: stealth module not available, returning stub result"
            )
            return {"success": False, "error": "stealth_module_unavailable"}

        slider_class = self._stealth_class
        user_id_value = kwargs.pop("user_id", session_id)
        user_id = (
            user_id_value.strip() if isinstance(user_id_value, str) else session_id
        )
        enable_learning = self._coerce_flag(kwargs.pop("enable_learning", True), True)
        headless = self._coerce_flag(kwargs.pop("headless", True), True)
        risk_session_id = kwargs.pop("risk_session_id", None)
        risk_trigger_scene = kwargs.pop("risk_trigger_scene", None)

        try:
            slider = slider_class(
                user_id=user_id,
                enable_learning=enable_learning,
                headless=headless,
            )
            if risk_session_id is not None:
                slider.risk_session_id = risk_session_id
            if risk_trigger_scene is not None:
                slider.risk_trigger_scene = risk_trigger_scene

            success, cookies = await slider.async_run(verification_url)
            result: dict[str, object] = {"success": bool(success)}
            if cookies:
                result["cookies"] = cookies
            if kwargs:
                result["ignored_kwargs"] = sorted(kwargs.keys())
            return result
        except Exception as exc:
            logger.exception(
                "SliderAdapter: captcha handling failed for session %s", session_id
            )
            return {
                "success": False,
                "error": "captcha_execution_failed",
                "details": str(exc),
            }

    def is_available(self) -> bool:
        """Check if the frozen stealth runner is importable."""
        self._ensure_initialized()
        return self._stealth_class is not None

    def get_remote_controller(self) -> RemoteControllerProtocol | None:
        """Return the frozen remote captcha controller singleton."""
        self._ensure_initialized()
        return self._remote_control

    def get_slider_patch_module(self) -> object | None:
        """Return the frozen runtime patch module."""
        self._ensure_initialized()
        return self._slider_patch_module

    async def create_remote_session(
        self, session_id: str | None, page: object
    ) -> dict[str, object]:
        """Create a remote captcha-control session."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        if self._remote_control is None:
            raise RuntimeError("captcha remote controller is unavailable")
        return await self._remote_control.create_session(session_id, page)

    async def handle_remote_mouse_event(
        self, session_id: str | None, event_type: str, x: int, y: int
    ) -> bool:
        """Delegate mouse events to the frozen remote controller."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        if self._remote_control is None:
            raise RuntimeError("captcha remote controller is unavailable")
        return await self._remote_control.handle_mouse_event(
            session_id, event_type, x, y
        )

    async def check_remote_completion(self, session_id: str | None) -> bool:
        """Check remote captcha completion state."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        if self._remote_control is None:
            raise RuntimeError("captcha remote controller is unavailable")
        return await self._remote_control.check_completion(session_id)

    async def close_remote_session(self, session_id: str | None) -> None:
        """Close a remote captcha-control session."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        if self._remote_control is None:
            raise RuntimeError("captcha remote controller is unavailable")
        await self._remote_control.close_session(session_id)

    def session_exists(self, session_id: str | None) -> bool:
        """Return whether a remote captcha session exists."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        return bool(
            self._remote_control and self._remote_control.session_exists(session_id)
        )

    def is_completed(self, session_id: str | None) -> bool:
        """Return whether a remote captcha session is marked completed."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        return bool(
            self._remote_control and self._remote_control.is_completed(session_id)
        )

    def handle_slider_patch(
        self, page: object, session_id: str | None, max_attempts: int = 5
    ) -> bool:
        """Run the frozen slider patch helper against an existing page/frame."""
        session_id = self._require_session_id(session_id)
        self._ensure_initialized()
        if self._slider_patch_handler is None:
            raise RuntimeError("slider patch module is unavailable")
        return bool(
            self._slider_patch_handler(page, session_id, max_attempts=max_attempts)
        )


_default_adapter: SliderAdapter | None = None


def get_slider_adapter() -> SliderAdapter:
    """Get the default SliderAdapter singleton."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = SliderAdapter()
    return _default_adapter


__all__ = ["SliderAdapter", "SliderValidationError", "get_slider_adapter"]
