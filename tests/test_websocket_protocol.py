import base64
import json
import sys
import types
import unittest
from typing import cast
from unittest.mock import Mock, patch


if "loguru" not in sys.modules:
    fake_loguru = types.ModuleType("loguru")
    setattr(fake_loguru, "logger", Mock())
    sys.modules["loguru"] = fake_loguru


from app.protocol.websocket_protocol import (  # noqa: E402
    build_create_chat_frame,
    build_heartbeat_frame,
    build_send_frame,
)


def make_fake_xianyu_utils(uuid_value: str) -> tuple[types.ModuleType, Mock]:
    module = types.ModuleType("utils.xianyu_utils")
    generate_uuid_mock = Mock(return_value=uuid_value)
    setattr(module, "generate_uuid", generate_uuid_mock)
    return module, generate_uuid_mock


class TestWebsocketProtocol(unittest.TestCase):
    def test_build_heartbeat_frame_contains_expected_keys_and_message_id(self) -> None:
        frame = build_heartbeat_frame("mid-123")

        self.assertEqual(frame["lwp"], "/!")
        self.assertEqual(frame["headers"], {"mid": "mid-123"})
        self.assertEqual(json.loads(json.dumps(frame)), frame)

    def test_build_send_frame_contains_expected_structure(self) -> None:
        fake_utils, generate_uuid_mock = make_fake_xianyu_utils("uuid-123")

        with patch.dict(sys.modules, {"utils.xianyu_utils": fake_utils}):
            frame = build_send_frame(
                message_id="mid-123",
                conversation_id="cid-456@goofish",
                receiver_id="receiver-1@goofish",
                sender_id="sender-1@goofish",
                text_content="hello world",
            )

        self.assertEqual(frame["lwp"], "/r/MessageSend/sendByReceiverScope")
        self.assertEqual(frame["headers"], {"mid": "mid-123"})
        self.assertEqual(frame["body"][0]["uuid"], "uuid-123")
        self.assertEqual(frame["body"][0]["cid"], "cid-456@goofish")
        self.assertEqual(
            frame["body"][1]["actualReceivers"],
            [
                "receiver-1@goofish",
                "sender-1@goofish",
            ],
        )
        encoded_payload = cast(str, frame["body"][0]["content"]["custom"]["data"])
        payload = cast(
            dict[str, object],
            json.loads(base64.b64decode(encoded_payload).decode("utf-8")),
        )
        self.assertEqual(payload, {"contentType": 1, "text": {"text": "hello world"}})
        generate_uuid_mock.assert_called_once_with()

    def test_build_send_frame_accepts_item_id_and_remains_json_serializable(
        self,
    ) -> None:
        fake_utils, _ = make_fake_xianyu_utils("uuid-456")

        with patch.dict(sys.modules, {"utils.xianyu_utils": fake_utils}):
            frame = build_send_frame(
                message_id="mid-456",
                conversation_id="cid-789@goofish",
                receiver_id="receiver-2@goofish",
                sender_id="sender-2@goofish",
                text_content="with item",
                item_id="item-99",
            )

        self.assertEqual(frame["body"][0]["uuid"], "uuid-456")
        self.assertEqual(frame["body"][0]["cid"], "cid-789@goofish")
        self.assertEqual(json.loads(json.dumps(frame)), frame)

    def test_build_create_chat_frame_contains_to_id_and_my_id(self) -> None:
        frame = build_create_chat_frame(
            message_id="mid-789",
            to_id="buyer-1",
            my_id="seller-1",
            item_id="item-100",
        )

        self.assertEqual(frame["lwp"], "/r/SingleChatConversation/create")
        self.assertEqual(frame["headers"], {"mid": "mid-789"})
        self.assertEqual(frame["body"][0]["pairFirst"], "buyer-1@goofish")
        self.assertEqual(frame["body"][0]["pairSecond"], "seller-1@goofish")
        self.assertEqual(frame["body"][0]["extension"], {"itemId": "item-100"})


if __name__ == "__main__":
    _ = unittest.main()
