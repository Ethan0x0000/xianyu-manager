import asyncio
import base64
import json
import unittest

from XianyuAutoAsync import XianyuLive


class MessageDedupeKeyTests(unittest.IsolatedAsyncioTestCase):
    def _make_live(self) -> XianyuLive:
        live: XianyuLive = object.__new__(XianyuLive)
        live.cookie_id = "test-cookie"
        live.processed_message_ids = {}
        live.processed_message_ids_lock = asyncio.Lock()
        live.processed_message_ids_max_size = 10000
        live.message_expire_time = 3600
        return live

    def test_resolve_message_dedupe_key_prefers_explicit_message_id(self):
        live = self._make_live()
        message = {
            "1": {
                "10": {
                    "bizTag": '{"messageId":"explicit-message-id"}',
                    "extJson": "{}",
                },
                "5": 1710000000,
            }
        }

        dedupe_key = live._resolve_message_dedupe_key(
            message,
            chat_id="chat-1",
            send_message="你好",
            create_time=0,
        )

        self.assertEqual(dedupe_key, "explicit-message-id")

    def test_resolve_message_dedupe_key_falls_back_when_message_id_missing(self):
        live = self._make_live()
        message = {
            "1": {
                "10": {
                    "bizTag": "{}",
                    "extJson": "{}",
                },
                "5": 1710000000,
            }
        }

        dedupe_key = live._resolve_message_dedupe_key(
            message,
            chat_id="chat-1",
            send_message="你好",
            create_time=0,
        )

        self.assertEqual(dedupe_key, "chat-1_你好_1710000000")

    async def test_fallback_dedupe_key_blocks_second_processing(self):
        live = self._make_live()
        message = {
            "1": {
                "10": {
                    "bizTag": "{}",
                    "extJson": "{}",
                },
                "5": 1710000000,
            }
        }

        dedupe_key = live._resolve_message_dedupe_key(
            message,
            chat_id="chat-1",
            send_message="你好",
            create_time=0,
        )

        self.assertIsNotNone(dedupe_key)
        if dedupe_key is None:
            self.fail("dedupe_key should not be None for fallback messages")

        first = await live._mark_message_processed_if_new(dedupe_key)
        second = await live._mark_message_processed_if_new(dedupe_key)

        self.assertTrue(first)
        self.assertFalse(second)

    async def test_hash_fallback_blocks_second_processing_without_create_time(self):
        live = self._make_live()
        message = {
            "1": {
                "10": {
                    "bizTag": "{}",
                    "extJson": "{}",
                    "senderNick": "买家",
                    "senderUserId": "buyer-1",
                    "reminderContent": "你好",
                }
            }
        }

        dedupe_key = live._resolve_message_dedupe_key(
            message,
            chat_id="chat-1",
            send_message="你好",
            create_time=0,
        )

        self.assertIsNotNone(dedupe_key)
        if dedupe_key is None:
            self.fail("dedupe_key should not be None for hash fallback messages")

        self.assertTrue(dedupe_key.startswith("chat-1_你好_"))
        first = await live._mark_message_processed_if_new(dedupe_key)
        second = await live._mark_message_processed_if_new(dedupe_key)

        self.assertTrue(first)
        self.assertFalse(second)

    async def test_handle_message_dedupes_before_second_schedule_without_message_id(
        self,
    ):
        live = self._make_live()
        live.myid = "self-user"
        live.order_status_handler = None
        live.yifan_account_lock = asyncio.Lock()
        live.yifan_account_waiting = {}

        scheduled_calls: list[dict[str, object]] = []

        async def fake_schedule(
            chat_id: str,
            message_data: dict[str, object],
            websocket,
            send_user_name: str,
            send_user_id: str,
            send_message: str,
            item_id: str,
            msg_time: str,
            message_id: str | None = None,
            create_time: int = 0,
        ):
            scheduled_calls.append(
                {
                    "chat_id": chat_id,
                    "message_data": message_data,
                    "websocket": websocket,
                    "send_user_name": send_user_name,
                    "send_user_id": send_user_id,
                    "send_message": send_message,
                    "item_id": item_id,
                    "msg_time": msg_time,
                    "message_id": message_id,
                    "create_time": create_time,
                }
            )

        live._schedule_debounced_reply = fake_schedule
        live._extract_order_id = lambda message, raw_message_data=None: ""
        live.extract_item_id_from_message = lambda message: "item-1"
        live._sanitize_buyer_nick = lambda *args, **kwargs: None
        live._classify_message_route = lambda **kwargs: {
            "route": "user_chat",
            "order_status_signal": None,
            "should_notify": False,
            "allow_auto_reply": True,
            "is_system_message": False,
            "is_group_message": False,
            "message_direction": 2,
            "content_type": 1,
            "card_title": "",
        }

        import cookie_manager

        previous_manager = cookie_manager.manager

        class DummyCookieManager:
            @staticmethod
            def get_cookie_status(cookie_id: str) -> bool:
                return True

        cookie_manager.manager = DummyCookieManager()

        inner_message = {
            "1": {
                "2": "chat-1@goofish",
                "5": 1710000000000,
                "7": 2,
                "10": {
                    "senderNick": "买家",
                    "senderUserId": "buyer-1",
                    "reminderContent": "你好",
                    "bizTag": "{}",
                    "extJson": "{}",
                    "reminderUrl": "https://www.goofish.com/item?itemId=item-1",
                },
            }
        }
        encoded = base64.b64encode(
            json.dumps(inner_message, ensure_ascii=False).encode("utf-8")
        ).decode("utf-8")
        packet = {
            "body": {
                "syncPushPackage": {
                    "data": [
                        {
                            "data": encoded,
                        }
                    ]
                }
            }
        }

        try:
            await live.handle_message(
                packet, websocket=None, msg_id="first", skip_ack=True
            )
            await live.handle_message(
                packet, websocket=None, msg_id="second", skip_ack=True
            )
        finally:
            cookie_manager.manager = previous_manager

        self.assertEqual(len(scheduled_calls), 1)
        self.assertEqual(scheduled_calls[0]["message_id"], "chat-1_你好_1710000000000")


if __name__ == "__main__":
    unittest.main()
