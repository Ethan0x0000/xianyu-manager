import unittest

from app.runtime.message_pipeline import (
    MessagePipeline,
    MessageRoute,
    ParsedMessage,
    QueuePriority,
)


class StubDeduplicator:
    duplicate_ids: set[str]
    calls: list[str]
    was_cleared: bool

    def __init__(self, duplicate_ids: set[str] | None = None) -> None:
        self.duplicate_ids = duplicate_ids or set()
        self.calls = []
        self.was_cleared = False

    def is_duplicate(self, message_id: str) -> bool:
        self.calls.append(message_id)
        return message_id in self.duplicate_ids

    def clear(self) -> None:
        self.was_cleared = True
        self.duplicate_ids.clear()


class TestMessagePipelineParse(unittest.TestCase):
    deduplicator: StubDeduplicator = StubDeduplicator()
    pipeline: MessagePipeline = MessagePipeline(deduplicator=StubDeduplicator())

    def setUp(self) -> None:
        self.deduplicator = StubDeduplicator()
        self.pipeline = MessagePipeline(deduplicator=self.deduplicator)

    def test_parse_none_returns_invalid_message(self) -> None:
        parsed = self.pipeline.parse(None)

        self.assertIsInstance(parsed, ParsedMessage)
        self.assertEqual(parsed.message_id, "")
        self.assertEqual(parsed.route, MessageRoute.INVALID)
        self.assertEqual(parsed.raw, {})
        self.assertEqual(parsed.queue_priority, int(QueuePriority.OTHER))

    def test_parse_sparse_event_returns_unknown_route(self) -> None:
        parsed = self.pipeline.parse({"id": "msg-unknown"})

        self.assertEqual(parsed.message_id, "msg-unknown")
        self.assertEqual(parsed.route, MessageRoute.UNKNOWN)
        self.assertEqual(parsed.content, "")
        self.assertEqual(parsed.queue_priority, int(QueuePriority.OTHER))

    def test_parse_valid_chat_message_extracts_message_id_sender_and_content(
        self,
    ) -> None:
        raw_event = {
            "id": "msg-1",
            "type": "chat",
            "senderId": "sender-1",
            "body": {"content": "hello world", "itemId": "item-1"},
        }

        parsed = self.pipeline.parse(raw_event)

        self.assertEqual(parsed.message_id, "msg-1")
        self.assertEqual(parsed.route, MessageRoute.CHAT)
        self.assertEqual(parsed.sender_id, "sender-1")
        self.assertEqual(parsed.item_id, "item-1")
        self.assertEqual(parsed.content, "hello world")
        self.assertEqual(parsed.queue_priority, int(QueuePriority.CHAT))

    def test_parse_order_message_classifies_order_route(self) -> None:
        raw_event = {
            "id": "msg-2",
            "body": {
                "content": "买家确认收货",
                "orderId": "1234567890",
                "senderId": "buyer-1",
            },
        }

        parsed = self.pipeline.parse(raw_event)

        self.assertEqual(parsed.message_id, "msg-2")
        self.assertEqual(parsed.route, MessageRoute.ORDER)
        self.assertEqual(parsed.sender_id, "buyer-1")
        self.assertEqual(parsed.order_id, "1234567890")
        self.assertEqual(parsed.content, "买家确认收货")
        self.assertEqual(parsed.queue_priority, int(QueuePriority.ORDER))


class TestMessagePipelineQueue(unittest.IsolatedAsyncioTestCase):
    deduplicator: StubDeduplicator = StubDeduplicator()
    pipeline: MessagePipeline = MessagePipeline(deduplicator=StubDeduplicator())

    async def asyncSetUp(self) -> None:
        self.deduplicator = StubDeduplicator()
        self.pipeline = MessagePipeline(deduplicator=self.deduplicator)

    async def test_enqueue_adds_messages_and_qsize_reflects_queue_length(self) -> None:
        first = await self.pipeline.enqueue(
            {"id": "msg-1", "type": "chat", "body": {"content": "hello"}}
        )
        second = await self.pipeline.enqueue(
            {"id": "msg-2", "type": "chat", "body": {"content": "world"}}
        )

        self.assertIsInstance(first, ParsedMessage)
        self.assertIsInstance(second, ParsedMessage)
        self.assertEqual(self.pipeline.qsize(), 2)

    async def test_process_next_uses_deduplicator_to_skip_duplicate_messages(
        self,
    ) -> None:
        self.deduplicator.duplicate_ids.add("dup-1")
        handled_messages: list[ParsedMessage] = []

        async def handler(message: ParsedMessage) -> None:
            handled_messages.append(message)

        _ = await self.pipeline.enqueue(
            {"id": "dup-1", "type": "chat", "body": {"content": "hello"}}
        )

        result = await self.pipeline.process_next(handler, timeout=0.01)

        self.assertIsNone(result)
        self.assertEqual(self.pipeline.qsize(), 0)
        self.assertEqual(handled_messages, [])
        self.assertEqual(self.deduplicator.calls, ["dup-1"])

    async def test_process_next_dispatches_non_duplicate_message(self) -> None:
        handled_messages: list[ParsedMessage] = []

        async def handler(message: ParsedMessage) -> None:
            handled_messages.append(message)

        _ = await self.pipeline.enqueue(
            {"id": "msg-3", "type": "chat", "body": {"content": "ping"}}
        )

        result = await self.pipeline.process_next(handler, timeout=0.01)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.message_id, "msg-3")
        self.assertEqual(result.route, MessageRoute.CHAT)
        self.assertEqual(len(handled_messages), 1)
        handled_message = handled_messages[0]
        self.assertEqual(handled_message.message_id, "msg-3")


if __name__ == "__main__":
    _ = unittest.main()
