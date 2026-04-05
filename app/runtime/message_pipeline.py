"""Message classification and processing pipeline.

Classifies incoming Goofish messages into typed route events and dispatches
them to the appropriate downstream handlers.

FROZEN PRIORITY ORDER:
1. Item-specific reply (highest priority)
2. Keyword reply
3. Default reply
4. AI reply (lowest)

FROZEN ROUTE TYPES (from XianyuAutoAsync.py analysis):
- chat: Regular chat message
- order: Order event (payment, confirm, etc.)
- heartbeat: Connection keepalive
- system: System notification
- unknown: Unrecognized/malformed
"""

from __future__ import annotations

import asyncio
import enum
import importlib
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import ClassVar, Protocol, TypeAlias, cast

logger = logging.getLogger(__name__)

MessageHandler: TypeAlias = Callable[["ParsedMessage"], Awaitable[None]]
JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONDict: TypeAlias = dict[str, JSONValue]


class DeduplicatorProtocol(Protocol):
    def is_duplicate(self, message_id: str) -> bool: ...

    def clear(self) -> None: ...


class DeduplicatorFactory(Protocol):
    def __call__(self) -> DeduplicatorProtocol: ...


__all__ = ["MessageHandler", "MessagePipeline", "MessageRoute", "ParsedMessage"]


def _build_default_deduplicator() -> DeduplicatorProtocol:
    module = importlib.import_module("app.runtime.dedupe")
    factory = cast(DeduplicatorFactory, getattr(module, "MessageDeduplicator"))
    instance = factory()
    return instance


class MessageRoute(enum.Enum):
    CHAT = "chat"
    ORDER = "order"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"
    UNKNOWN = "unknown"
    INVALID = "invalid"


class QueuePriority(enum.IntEnum):
    HEARTBEAT = 0
    ORDER = 1
    CHAT = 2
    OTHER = 3


@dataclass(slots=True)
class ParsedMessage:
    message_id: str
    route: MessageRoute
    sender_id: str = ""
    item_id: str = ""
    order_id: str = ""
    content: str = ""
    raw: JSONDict = field(default_factory=dict)
    queue_priority: int = int(QueuePriority.OTHER)


class MessagePipeline:
    """
    Classifies and normalizes incoming Goofish WebSocket messages.

    Outputs ParsedMessage events to downstream business services.
    Does NOT contain business logic itself.
    """

    DEFAULT_MAX_QUEUE_SIZE: ClassVar[int] = 1000
    DEFAULT_WORKERS: ClassVar[int] = 1

    _ORDER_MARKERS: ClassVar[tuple[str, ...]] = (
        "交易关闭",
        "订单关闭",
        "钱款已原路退返",
        "退款中",
        "退款成功",
        "退货退款",
        "退款关闭",
        "买家确认收货",
        "交易成功",
        "已发货",
        "等待买家收货",
        "我已付款，等待你发货",
        "待发货",
        "去发货",
        "TRADE_PAID_DONE_SELLER",
    )
    _SYSTEM_MARKERS: ClassVar[tuple[str, ...]] = (
        "闲鱼小红花",
        "温馨提醒",
        "曝光卡",
        "蚂蚁森林",
        "能量可领",
        "创建合约",
        "假客服骗钱",
        "订单即将自动确认收货",
        "宝贝性价比如何，去表个态吧",
        "发来一条消息",
        "发来一条新消息",
        "已送出小红花",
        "已收下",
    )
    _ORDER_ID_PATTERNS: ClassVar[tuple[str, ...]] = (
        r'orderId(?:=|:|%3[Dd]|\\u003[dD])\s*"?(\d{10,})',
        r'bizOrderId["\']?\s*[:=]\s*"?(\d{10,})',
        r'order[_-]?id["\']?\s*[:=]\s*"?(\d{10,})',
        r"order[_-]?detail\?(?:[^\s#]*?&)?id=(\d{10,})",
        r"order-detail\?(?:[^\s#]*?&)?orderId=(\d{10,})",
    )

    def __init__(
        self,
        *,
        deduplicator: DeduplicatorProtocol | None = None,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        worker_count: int = DEFAULT_WORKERS,
    ) -> None:
        self._deduplicator: DeduplicatorProtocol = (
            deduplicator or _build_default_deduplicator()
        )
        self._queue: asyncio.PriorityQueue[tuple[int, int, ParsedMessage]] = (
            asyncio.PriorityQueue(maxsize=max_queue_size)
        )
        self._queue_counter: int = 0
        self._queue_lock: asyncio.Lock = asyncio.Lock()
        self._worker_count: int = max(1, worker_count)
        self._running: bool = False
        self._workers: list[asyncio.Task[None]] = []

    def parse(self, raw_event: object | None) -> ParsedMessage:
        """
        Parse a raw WebSocket event into a normalized ParsedMessage.

        Handles malformed/missing input safely — returns INVALID route.
        """
        if not raw_event or not isinstance(raw_event, dict):
            return ParsedMessage(
                message_id="",
                route=MessageRoute.INVALID,
                raw=self._as_dict(raw_event),
            )

        try:
            event = cast(JSONDict, raw_event)
            body = self._as_dict(event.get("body"))
            candidate_texts = self._collect_candidate_texts(event, root="event")

            message_id = self._extract_message_id(event, body)
            sender_id = self._extract_common_field(
                event, body, "senderId", "sender_id", "fromId"
            )
            item_id = self._extract_common_field(event, body, "itemId", "item_id")
            order_id = self._extract_order_id(body, candidate_texts, event)
            content = self._extract_content(event, body, candidate_texts)

            route = self._classify_route(
                raw_event=event,
                texts=[text for _, text in candidate_texts],
                order_id=order_id,
                content=content,
            )
            queue_priority = int(self._get_queue_priority(event, route))

            return ParsedMessage(
                message_id=message_id,
                route=route,
                sender_id=sender_id,
                item_id=item_id,
                order_id=order_id,
                content=content,
                raw=event,
                queue_priority=queue_priority,
            )
        except Exception:
            logger.warning(
                "MessagePipeline.parse failed; returning INVALID", exc_info=True
            )
            return ParsedMessage(
                message_id="",
                route=MessageRoute.INVALID,
                raw=self._as_dict(cast(object, raw_event)),
            )

    async def enqueue(self, raw_event: object | None) -> ParsedMessage | None:
        """Parse an event and place it into the priority queue."""
        parsed = self.parse(raw_event)
        try:
            async with self._queue_lock:
                self._queue_counter += 1
                counter = self._queue_counter
            self._queue.put_nowait((parsed.queue_priority, counter, parsed))
            return parsed
        except asyncio.QueueFull:
            logger.warning(
                "MessagePipeline queue full; dropping message %s", parsed.message_id
            )
            return None

    async def process_next(
        self,
        handler: MessageHandler,
        *,
        timeout: float | None = None,
    ) -> ParsedMessage | None:
        """Process the next queued message, skipping duplicates by message ID."""
        queued = await self._dequeue(timeout=timeout)
        if queued is None:
            return None

        _, _, parsed = queued
        try:
            if parsed.message_id and self._deduplicator.is_duplicate(parsed.message_id):
                logger.debug("Skipping duplicate message_id=%s", parsed.message_id)
                return None

            await handler(parsed)
            return parsed
        finally:
            self._queue.task_done()

    async def start_workers(
        self,
        handler: MessageHandler,
        *,
        worker_count: int | None = None,
    ) -> None:
        """Start background queue workers using the provided handler."""
        if self._running:
            return

        self._running = True
        count = max(1, worker_count or self._worker_count)
        self._workers = [
            asyncio.create_task(
                self._worker_loop(index, handler),
                name=f"message-pipeline-worker-{index}",
            )
            for index in range(count)
        ]

    async def stop_workers(self) -> None:
        """Cancel running workers and wait for shutdown."""
        self._running = False
        for task in self._workers:
            _ = task.cancel()
        if self._workers:
            _ = await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def join(self) -> None:
        """Wait until all queued messages have been processed."""
        await self._queue.join()

    def clear_dedupe(self) -> None:
        """Reset in-memory duplicate tracking."""
        self._deduplicator.clear()

    def qsize(self) -> int:
        """Return the current queue size."""
        return self._queue.qsize()

    async def _worker_loop(self, worker_id: int, handler: MessageHandler) -> None:
        while self._running:
            try:
                _ = await self.process_next(handler, timeout=0.5)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("MessagePipeline worker %s failed", worker_id)

    async def _dequeue(
        self,
        *,
        timeout: float | None = None,
    ) -> tuple[int, int, ParsedMessage] | None:
        if timeout is None:
            return await self._queue.get()
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def _classify_route(
        self,
        *,
        raw_event: JSONDict,
        texts: list[str],
        order_id: str,
        content: str,
    ) -> MessageRoute:
        lwp = str(raw_event.get("lwp", "") or "").strip().lower()
        msg_type = str(raw_event.get("type", "") or "").strip().lower()

        if lwp == "/!" or msg_type == "heartbeat":
            return MessageRoute.HEARTBEAT
        if raw_event.get("code") == 200 and "body" not in raw_event:
            return MessageRoute.HEARTBEAT
        if (
            order_id
            or "order" in lwp
            or msg_type == "order"
            or self._contains_any(texts, self._ORDER_MARKERS)
        ):
            return MessageRoute.ORDER
        if (
            msg_type == "system"
            or "system" in lwp
            or self._contains_any(texts, self._SYSTEM_MARKERS)
        ):
            return MessageRoute.SYSTEM
        if lwp.startswith("/") or msg_type in {"chat", "message"} or content:
            return MessageRoute.CHAT
        return MessageRoute.UNKNOWN

    def _get_queue_priority(
        self,
        raw_event: JSONDict,
        route: MessageRoute,
    ) -> QueuePriority:
        if route == MessageRoute.HEARTBEAT:
            return QueuePriority.HEARTBEAT
        if route == MessageRoute.ORDER:
            return QueuePriority.ORDER
        if route == MessageRoute.CHAT:
            return QueuePriority.CHAT

        body = self._as_dict(raw_event.get("body"))
        sync_package = self._as_dict(body.get("syncPushPackage"))
        sync_data = sync_package.get("data")
        if isinstance(sync_data, list) and sync_data:
            first_item: object = sync_data[0]
            data_str = str(first_item).lower()
            if any(
                marker in data_str
                for marker in ("orderid", "order_id", "bizorderid", "paysucc", "paid")
            ):
                return QueuePriority.ORDER
            if "message" in data_str or "chat" in data_str:
                return QueuePriority.CHAT
        return QueuePriority.OTHER

    def _extract_message_id(
        self,
        raw_event: JSONDict,
        body: JSONDict,
    ) -> str:
        return self._first_non_empty(
            raw_event.get("id"),
            raw_event.get("msgId"),
            raw_event.get("message_id"),
            body.get("id"),
            body.get("msgId"),
            body.get("messageId"),
            body.get("message_id"),
        )

    def _extract_common_field(
        self,
        raw_event: JSONDict,
        body: JSONDict,
        *keys: str,
    ) -> str:
        values = [body.get(key) for key in keys] + [raw_event.get(key) for key in keys]
        return self._first_non_empty(*values)

    def _extract_order_id(
        self,
        body: JSONDict,
        candidate_texts: list[tuple[str, str]],
        raw_event: JSONDict,
    ) -> str:
        explicit = self._first_non_empty(
            body.get("orderId"),
            body.get("bizOrderId"),
            raw_event.get("orderId"),
            raw_event.get("bizOrderId"),
        )
        if explicit:
            return explicit

        for source, candidate_text in candidate_texts:
            order_id = self._extract_order_id_from_candidate_text(
                candidate_text, source=source
            )
            if order_id:
                return order_id
        return ""

    def _extract_content(
        self,
        raw_event: JSONDict,
        body: JSONDict,
        candidate_texts: list[tuple[str, str]],
    ) -> str:
        direct = self._first_non_empty(
            body.get("content"),
            body.get("text"),
            body.get("message"),
            body.get("msg"),
            raw_event.get("content"),
            raw_event.get("text"),
            raw_event.get("message"),
        )
        if direct:
            return direct

        for source, candidate_text in candidate_texts:
            source_lower = source.lower()
            if any(
                token in source_lower
                for token in ("content", "text", "message", "notice", "title")
            ):
                return candidate_text
        return ""

    def _extract_order_id_from_update_key(self, raw_text: object) -> str:
        normalized_text = str(raw_text or "").strip()
        if not normalized_text:
            return ""

        direct_match_found = False
        direct_match = re.search(
            r'updateKey["\']?\s*[:=]\s*["\']([^"\']+)', normalized_text
        )
        if direct_match:
            direct_match_found = True
            normalized_text = direct_match.group(1)

        colon_parts = [part.strip().strip("\"'") for part in normalized_text.split(":")]
        long_numeric_parts = [
            part for part in colon_parts if part.isdigit() and len(part) >= 16
        ]
        if long_numeric_parts:
            return long_numeric_parts[0]

        if direct_match_found:
            generic_matches: list[str] = re.findall(r"\d{16,}", normalized_text)
            if generic_matches:
                return generic_matches[0]
        return ""

    def _extract_order_id_from_candidate_text(
        self, raw_text: object, *, source: str = ""
    ) -> str:
        normalized_text = str(raw_text or "").strip()
        if not normalized_text:
            return ""

        for pattern in self._ORDER_ID_PATTERNS:
            match = re.search(pattern, normalized_text)
            if match:
                return match.group(1)

        source_lower = source.lower()
        text_lower = normalized_text.lower()
        if (
            "updatekey" in source_lower
            or "updatekey" in text_lower
            or ("trade_" in text_lower and ":" in normalized_text)
            or ("buyer_confirm" in text_lower and ":" in normalized_text)
        ):
            return self._extract_order_id_from_update_key(normalized_text)
        return ""

    def _collect_candidate_texts(
        self,
        data: object,
        *,
        root: str,
    ) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add_candidate(source: str, value: object) -> None:
            if value is None:
                return

            normalized_text = str(value).strip()
            if not normalized_text:
                return

            dedupe_key = (source, normalized_text)
            if dedupe_key in seen:
                return
            seen.add(dedupe_key)
            candidates.append((source, normalized_text))

            if normalized_text[:1] in {"{", "["}:
                try:
                    parsed_value = self._load_json_value(normalized_text)
                except Exception:
                    return
                if parsed_value is None:
                    return
                walk_value(parsed_value, f"{source}.json")

        def walk_value(value: object, source: str) -> None:
            if isinstance(value, dict):
                value_dict = cast(dict[str, object], value)
                for key, nested_value in value_dict.items():
                    nested_source = f"{source}.{key}"
                    if isinstance(nested_value, (dict, list)):
                        walk_value(cast(object, nested_value), nested_source)
                    else:
                        add_candidate(nested_source, nested_value)
            elif isinstance(value, list):
                value_list = cast(list[object], value)
                for index, nested_value in enumerate(value_list[:20]):
                    walk_value(nested_value, f"{source}[{index}]")
            else:
                add_candidate(source, value)

        walk_value(data, root)
        return candidates

    def _contains_any(self, texts: list[str], markers: tuple[str, ...]) -> bool:
        lowered = [text.lower() for text in texts if text]
        return any(marker.lower() in text for text in lowered for marker in markers)

    def _first_non_empty(self, *values: object) -> str:
        for value in values:
            normalized = str(value or "").strip()
            if normalized:
                return normalized
        return ""

    def _as_dict(self, value: object) -> JSONDict:
        if isinstance(value, dict):
            return cast(JSONDict, value)
        return {}

    def _load_json_value(self, raw_text: str) -> JSONValue | None:
        parsed_unknown = cast(object, json.loads(raw_text))
        if (
            isinstance(parsed_unknown, (dict, list, str, int, float, bool))
            or parsed_unknown is None
        ):
            return cast(JSONValue, parsed_unknown)
        return None
