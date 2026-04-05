from __future__ import annotations

import asyncio
import enum
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeAlias, cast

from app.protocol.websocket_protocol import build_heartbeat_frame, build_send_frame

logger = logging.getLogger(__name__)

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONDict: TypeAlias = dict[str, JSONValue]
MessageHandler: TypeAlias = Callable[[JSONDict], Awaitable[None]]

__all__ = [
    "ConnectionState",
    "WebSocketClient",
    "WebSocketConfigError",
]


class ConnectionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class WebSocketConfigError(Exception):
    """Raised when WebSocket client is misconfigured."""


class WebSocketClient:
    """
    Goofish WebSocket transport client.

    Handles connection state, heartbeat, message sending, reconnect backoff,
    and background task lifecycle without embedding reply/shipping policy.

    FROZEN INVARIANTS:
    - WebSocket URL: wss://wss-goofish.dingtalk.com/
    - Heartbeat lwp: /!
    - Heartbeat interval: 15s (from config)
    - Reconnect: exponential backoff with max 32s
    """

    WS_URL: str = "wss://wss-goofish.dingtalk.com/"
    HEARTBEAT_INTERVAL: int = 15  # seconds
    MAX_RECONNECT_DELAY: int = 32  # seconds

    def __init__(
        self,
        account_id: str,
        cookie_str: str,
        device_id: str = "",
        on_message: MessageHandler | None = None,
    ) -> None:
        self.account_id: str = account_id
        self.cookie_str: str = cookie_str
        self.device_id: str = device_id
        self.on_message: MessageHandler | None = on_message

        self._validate_config()

        self.state: ConnectionState = ConnectionState.DISCONNECTED
        self._ws: object | None = None
        self._stop_event: asyncio.Event | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._reconnect_count: int = 0
        self._last_sent_payload: str | None = None
        self._last_heartbeat_payload: JSONDict | None = None

    def _validate_config(self) -> None:
        """Validate required config before any network activity."""
        if not self.account_id or not self.account_id.strip():
            raise WebSocketConfigError(
                "account_id and cookie_str are required to create WebSocketClient"
            )
        if not self.cookie_str or not self.cookie_str.strip():
            raise WebSocketConfigError(
                "account_id and cookie_str are required to create WebSocketClient"
            )
        if not self.WS_URL or not str(self.WS_URL).strip():
            raise WebSocketConfigError("WS_URL is required to create WebSocketClient")

    def _get_stop_event(self) -> asyncio.Event:
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        return self._stop_event

    def _new_mid(self) -> str:
        timestamp = int(time.time() * 1000)
        return f"{timestamp}-{uuid.uuid4().hex[:8]}"

    def build_heartbeat(self, mid: str) -> JSONDict:
        """Build a heartbeat frame. Returns dict with lwp='/!'"""
        frame = cast(JSONDict, build_heartbeat_frame(mid))
        self._last_heartbeat_payload = frame
        return frame

    def build_send(
        self,
        *,
        message_id: str,
        conversation_id: str,
        receiver_id: str,
        sender_id: str,
        text_content: str,
        item_id: str | None = None,
    ) -> JSONDict:
        """Build a message-send frame using the frozen protocol wrapper."""
        return cast(
            JSONDict,
            build_send_frame(
                message_id=message_id,
                conversation_id=conversation_id,
                receiver_id=receiver_id,
                sender_id=sender_id,
                text_content=text_content,
                item_id=item_id,
            ),
        )

    async def connect(self) -> None:
        """Initiate a stub WebSocket connection and start background tasks."""
        self._validate_config()
        if self.state == ConnectionState.CONNECTED:
            return

        stop_event = self._get_stop_event()
        stop_event.clear()

        self.state = ConnectionState.CONNECTING
        logger.info(
            "[%s] WebSocket connect initiated to %s", self.account_id, self.WS_URL
        )

        # Transport wiring is intentionally stubbed for this extraction task.
        self._ws = object()
        self.state = ConnectionState.CONNECTED
        self.reset_reconnect_count()
        _ = await self._start_heartbeat_task()
        logger.info("[%s] WebSocket connected (transport stub)", self.account_id)

    async def disconnect(self) -> None:
        """Gracefully disconnect and cancel heartbeat task."""
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()

        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None
        self._ws = None
        self.state = ConnectionState.DISCONNECTED
        logger.info("[%s] WebSocket disconnected", self.account_id)

    async def _cancel_task(self, task: asyncio.Task[None] | None) -> None:
        if task is None or task.done():
            return
        _ = task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _start_heartbeat_task(self) -> asyncio.Task[None]:
        """Cancel any existing heartbeat task and start a fresh one."""
        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name=f"ws-heartbeat-{self.account_id}",
        )
        return self._heartbeat_task

    async def _heartbeat_loop(self) -> None:
        """Maintain heartbeat cadence while the client remains connected."""
        stop_event = self._get_stop_event()
        try:
            while self.state == ConnectionState.CONNECTED and not stop_event.is_set():
                frame = self.build_heartbeat(self._new_mid())
                logger.debug(
                    "[%s] Prepared heartbeat frame: %s", self.account_id, frame
                )
                try:
                    _ = await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.HEARTBEAT_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            logger.info("[%s] Heartbeat loop exited", self.account_id)

    async def send(self, payload: JSONDict) -> None:
        """Send a payload frame via the WebSocket connection."""
        if self.state != ConnectionState.CONNECTED or self._ws is None:
            raise RuntimeError(f"Cannot send: WebSocket is {self.state.value}")

        serialized_payload = json.dumps(payload, ensure_ascii=False)
        self._last_sent_payload = serialized_payload
        logger.debug("[%s] Sending frame: %s", self.account_id, serialized_payload)

    async def run_forever(self) -> None:
        """Run the stub connection lifecycle with reconnect backoff."""
        stop_event = self._get_stop_event()
        stop_event.clear()

        while not stop_event.is_set():
            try:
                await self.connect()
                _ = await stop_event.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state = ConnectionState.FAILED
                logger.warning(
                    "[%s] WebSocket loop failed: %s",
                    self.account_id,
                    exc,
                )
                if stop_event.is_set():
                    break
                self.state = ConnectionState.RECONNECTING
                delay = self.calculate_retry_delay()
                logger.info(
                    "[%s] Reconnecting after %.1fs backoff",
                    self.account_id,
                    delay,
                )
                try:
                    _ = await asyncio.wait_for(stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    continue
            finally:
                if self.state != ConnectionState.DISCONNECTED:
                    await self.disconnect()

    def start_background(self) -> asyncio.Task[None]:
        """Start the connection loop as a background asyncio task."""
        if self._runner_task and not self._runner_task.done():
            return self._runner_task
        self._runner_task = asyncio.create_task(
            self.run_forever(),
            name=f"ws-client-{self.account_id}",
        )
        return self._runner_task

    async def stop_background(self) -> None:
        """Stop the connection loop and clean up background tasks."""
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()

        await self.disconnect()
        await self._cancel_task(self._runner_task)
        self._runner_task = None

    def calculate_retry_delay(self) -> float:
        """Calculate exponential backoff delay for reconnect."""
        raw_delay: int = 1 << self._reconnect_count
        delay: int = min(raw_delay, self.MAX_RECONNECT_DELAY)
        self._reconnect_count += 1
        return float(delay)

    def reset_reconnect_count(self) -> None:
        """Reset reconnect counter after successful connection."""
        self._reconnect_count = 0
