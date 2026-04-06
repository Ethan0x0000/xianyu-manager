import os
import unittest
from typing import cast, override

from app.db.connection import get_db
from app.services.reply_policy import ReplyPolicyService, ReplyResult
from tests.helpers import make_test_db


class ExposedReplyPolicyService(ReplyPolicyService):
    def matches(self, text: str, pattern: str, is_regex: bool) -> bool:
        return self._matches(text, pattern, is_regex)


class TestReplyPolicyService(unittest.TestCase):
    db_path: str = ""
    service: ExposedReplyPolicyService = cast(
        ExposedReplyPolicyService, cast(object, None)
    )

    @override
    def setUp(self) -> None:
        self.db_path = make_test_db()
        self.service = ExposedReplyPolicyService(self.db_path)

    @override
    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _execute(self, sql: str, params: tuple[object, ...]) -> None:
        with get_db(self.db_path) as conn:
            _ = conn.execute(sql, params)

    def test_resolve_returns_item_reply_when_item_reply_exists(self) -> None:
        self._execute(
            "INSERT INTO item_replies (item_id, reply_content, enabled) VALUES (?, ?, ?)",
            ("item-1", "item-specific reply", 1),
        )
        self._execute(
            "INSERT INTO item_keywords (item_id, pattern, reply_content, enabled) VALUES (?, ?, ?, ?)",
            ("item-1", "hello", "item keyword reply", 1),
        )
        self._execute(
            "INSERT INTO keywords (pattern, reply_content, enabled) VALUES (?, ?, ?)",
            ("hello", "general keyword reply", 1),
        )
        self._execute(
            "INSERT INTO default_replies (content, enabled) VALUES (?, ?)",
            ("default reply", 1),
        )

        result = self.service.resolve("item-1", "hello there")

        self.assertIsNotNone(result)
        result = cast(ReplyResult, result)
        self.assertEqual(result.reply_text, "item-specific reply")
        self.assertEqual(result.source, "item_reply")
        self.assertEqual(result.matched_pattern, "")

    def test_resolve_returns_item_keyword_match_before_general_keyword(self) -> None:
        self._execute(
            "INSERT INTO item_keywords (item_id, pattern, reply_content, enabled) VALUES (?, ?, ?, ?)",
            ("item-1", "special", "item keyword reply", 1),
        )
        self._execute(
            "INSERT INTO keywords (pattern, reply_content, enabled) VALUES (?, ?, ?)",
            ("special", "general keyword reply", 1),
        )

        result = self.service.resolve("item-1", "this is a special request")

        self.assertIsNotNone(result)
        result = cast(ReplyResult, result)
        self.assertEqual(result.reply_text, "item keyword reply")
        self.assertEqual(result.source, "item_keyword")
        self.assertEqual(result.matched_pattern, "special")

    def test_resolve_returns_general_keyword_match_before_default_reply(self) -> None:
        self._execute(
            "INSERT INTO keywords (pattern, reply_content, enabled) VALUES (?, ?, ?)",
            ("coupon", "general keyword reply", 1),
        )
        self._execute(
            "INSERT INTO default_replies (content, enabled) VALUES (?, ?)",
            ("default reply", 1),
        )

        result = self.service.resolve("item-1", "do you have a coupon?")

        self.assertIsNotNone(result)
        result = cast(ReplyResult, result)
        self.assertEqual(result.reply_text, "general keyword reply")
        self.assertEqual(result.source, "keyword")
        self.assertEqual(result.matched_pattern, "coupon")

    def test_resolve_returns_default_reply_when_no_keywords_match(self) -> None:
        self._execute(
            "INSERT INTO keywords (pattern, reply_content, enabled) VALUES (?, ?, ?)",
            ("coupon", "general keyword reply", 1),
        )
        self._execute(
            "INSERT INTO default_replies (content, enabled) VALUES (?, ?)",
            ("default reply", 1),
        )

        result = self.service.resolve("item-1", "just browsing")

        self.assertIsNotNone(result)
        result = cast(ReplyResult, result)
        self.assertEqual(result.reply_text, "default reply")
        self.assertEqual(result.source, "default")
        self.assertEqual(result.matched_pattern, "")

    def test_resolve_returns_none_when_nothing_matches(self) -> None:
        result = self.service.resolve("item-1", "just browsing")

        self.assertIsNone(result)

    def test_matches_does_case_insensitive_substring_match(self) -> None:
        self.assertTrue(self.service.matches("Hello World", "hello", False))
        self.assertFalse(self.service.matches("Hello World", "bye", False))

    def test_matches_supports_regex_patterns(self) -> None:
        self.assertTrue(self.service.matches("order 123 shipped", r"order\s+\d+", True))
        self.assertFalse(self.service.matches("order shipped", r"order\s+\d+", True))

    def test_matches_returns_false_for_invalid_regex(self) -> None:
        self.assertFalse(self.service.matches("hello", "(", True))


if __name__ == "__main__":
    _ = unittest.main()
