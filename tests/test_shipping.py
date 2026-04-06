import os
import sqlite3
import unittest
from typing import cast

from app.db.connection import get_db
from app.services.shipping import DeliveryAction, DeliveryMode, ShippingService
from tests.helpers import make_test_db


class TestShippingService(unittest.TestCase):
    db_path: str = ""
    service: ShippingService = cast(ShippingService, cast(object, None))

    def setUp(self) -> None:
        self.db_path = make_test_db()
        self.service = ShippingService(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _insert_card(
        self,
        name: str,
        content_type: str,
        content: str,
        account_id: str = "account-1",
    ) -> int:
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO delivery_cards (name, content_type, content, account_id) VALUES (?, ?, ?, ?)",
                (name, content_type, content, account_id),
            )
            lastrowid = cursor.lastrowid
        if lastrowid is None:
            self.fail("delivery_cards insert did not return a row id")
        return lastrowid

    def _insert_rule(
        self,
        item_id: str,
        card_id: int,
        priority: int,
        enabled: int = 1,
        account_id: str = "account-1",
    ) -> int:
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO delivery_rules (item_id, card_id, priority, enabled, account_id) VALUES (?, ?, ?, ?, ?)",
                (item_id, card_id, priority, enabled, account_id),
            )
            lastrowid = cursor.lastrowid
        if lastrowid is None:
            self.fail("delivery_rules insert did not return a row id")
        return lastrowid

    def test_resolve_delivery_rule_returns_none_when_no_rules_exist(self) -> None:
        action = self.service.resolve_delivery_rule("item-1", "account-1")

        self.assertIsNone(action)

    def test_resolve_delivery_rule_returns_highest_priority_rule(self) -> None:
        low_card_id = self._insert_card("low", "text", "low content")
        high_card_id = self._insert_card("high", "api", "high content")
        _ = self._insert_rule("item-1", low_card_id, priority=1)
        high_rule_id = self._insert_rule("item-1", high_card_id, priority=10)

        action = self.service.resolve_delivery_rule("item-1", "account-1")

        self.assertIsNotNone(action)
        action = cast(DeliveryAction, action)
        self.assertEqual(action.rule_id, high_rule_id)
        self.assertEqual(action.card_id, high_card_id)
        self.assertIs(action.mode, DeliveryMode.API_CARD)
        self.assertEqual(action.content, "high content")

    def test_resolve_delivery_rule_maps_content_type_to_delivery_mode(self) -> None:
        cases = {
            "text": DeliveryMode.TEXT,
            "data": DeliveryMode.BATCH_DATA,
            "api": DeliveryMode.API_CARD,
            "image": DeliveryMode.IMAGE,
            "yifan": DeliveryMode.YIFAN,
        }

        for content_type, expected_mode in cases.items():
            with self.subTest(content_type=content_type):
                card_id = self._insert_card(
                    f"card-{content_type}",
                    content_type,
                    f"content-{content_type}",
                )
                item_id = f"item-{content_type}"
                _ = self._insert_rule(item_id, card_id, priority=1)

                action = self.service.resolve_delivery_rule(item_id, "account-1")

                self.assertIsNotNone(action)
                action = cast(DeliveryAction, action)
                self.assertIs(action.mode, expected_mode)

    def test_log_delivery_inserts_record_into_delivery_logs(self) -> None:
        card_id = self._insert_card("card", "text", "card content")

        self.service.log_delivery("order-1", card_id, "sent")

        with get_db(self.db_path) as conn:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    "SELECT order_id, card_id, status FROM delivery_logs WHERE order_id=?",
                    ("order-1",),
                ).fetchone(),
            )

        self.assertIsNotNone(row)
        row = cast(sqlite3.Row, row)
        self.assertEqual(cast(str, row["order_id"]), "order-1")
        self.assertEqual(cast(int, row["card_id"]), card_id)
        self.assertEqual(cast(str, row["status"]), "sent")

    def test_delivery_mode_enum_values(self) -> None:
        self.assertEqual(
            {mode.name: mode.value for mode in DeliveryMode},
            {
                "TEXT": "text",
                "BATCH_DATA": "batch_data",
                "API_CARD": "api_card",
                "IMAGE": "image",
                "YIFAN": "yifan",
                "UNKNOWN": "unknown",
            },
        )


if __name__ == "__main__":
    _ = unittest.main()
