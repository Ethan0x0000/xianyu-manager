import os
import unittest
from typing import cast

from app.services.ai_reply import AIProvider, AIReplyService, UnsupportedProviderError
from tests.helpers import make_test_db


class AIReplyServiceDBMixin:
    db_path: str = ""
    service: AIReplyService = cast(AIReplyService, cast(object, None))

    def setUp(self) -> None:
        self.db_path = make_test_db()
        self.service = AIReplyService(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)


class TestAIReplyService(AIReplyServiceDBMixin, unittest.TestCase):
    def test_resolve_provider_maps_supported_aliases(self) -> None:
        cases = {
            "openai": AIProvider.OPENAI,
            "gpt": AIProvider.OPENAI,
            "gemini": AIProvider.GEMINI,
            "compatible": AIProvider.OPENAI_COMPATIBLE,
            "disabled": AIProvider.DISABLED,
        }

        for provider_type, expected in cases.items():
            with self.subTest(provider_type=provider_type):
                self.assertIs(self.service.resolve_provider(provider_type), expected)

    def test_resolve_provider_raises_for_unsupported_provider(self) -> None:
        with self.assertRaises(UnsupportedProviderError):
            _ = self.service.resolve_provider("fakeai")

    def test_save_message_and_get_conversation_context_round_trip(self) -> None:
        self.service.save_message("session-1", "user", "hello")
        self.service.save_message("session-1", "assistant", "hi there")
        self.service.save_message("session-1", "user", "need help")

        context = self.service.get_conversation_context("session-1")

        self.assertEqual(
            context,
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
                {"role": "user", "content": "need help"},
            ],
        )

    def test_get_conversation_context_respects_limit_parameter(self) -> None:
        self.service.save_message("session-1", "user", "first")
        self.service.save_message("session-1", "assistant", "second")
        self.service.save_message("session-1", "user", "third")

        context = self.service.get_conversation_context("session-1", limit=2)

        self.assertEqual(
            context,
            [
                {"role": "assistant", "content": "second"},
                {"role": "user", "content": "third"},
            ],
        )


class TestAIReplyServiceAsync(AIReplyServiceDBMixin, unittest.IsolatedAsyncioTestCase):
    async def test_generate_reply_returns_empty_string_when_no_ai_settings_enabled(
        self,
    ) -> None:
        reply = await self.service.generate_reply("session-1", "hello")

        self.assertEqual(reply, "")


if __name__ == "__main__":
    _ = unittest.main()
