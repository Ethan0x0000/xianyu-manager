"""Shipping/auto-delivery service.

Handles retained local delivery modes only:
- text: Send plain text card
- batch_data: Send from a batch/pool of data
- api_card: Send via a configured API endpoint
- image: Send image file

Excluded: legacy external vendor integrations, comment-based delivery flows,
and hardcoded third-party hosts.
"""

from __future__ import annotations

import enum
import logging
import sqlite3
from dataclasses import dataclass
from typing import cast

logger = logging.getLogger(__name__)


class DeliveryMode(enum.Enum):
    TEXT = "text"
    BATCH_DATA = "batch_data"
    API_CARD = "api_card"
    IMAGE = "image"
    UNKNOWN = "unknown"


_MODE_ALIASES: dict[str, DeliveryMode] = {
    "text": DeliveryMode.TEXT,
    "data": DeliveryMode.BATCH_DATA,
    "batch_data": DeliveryMode.BATCH_DATA,
    "api": DeliveryMode.API_CARD,
    "api_card": DeliveryMode.API_CARD,
    "image": DeliveryMode.IMAGE,
}


@dataclass
class DeliveryAction:
    mode: DeliveryMode
    content: str
    card_id: int = 0
    rule_id: int = 0


class ShippingService:
    """Retained local delivery service only."""

    def __init__(self, db_path: str) -> None:
        self.db_path: str
        self.db_path = db_path

    def resolve_delivery_rule(
        self,
        item_id: str,
        account_id: str,
    ) -> DeliveryAction | None:
        """Find the highest-priority delivery rule for an item/account pair."""
        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    """
                SELECT
                    dr.id AS rule_id,
                    dc.id AS card_id,
                    dc.content_type,
                    dc.content
                FROM delivery_rules dr
                JOIN delivery_cards dc ON dr.card_id = dc.id
                WHERE dr.item_id = ?
                  AND dr.enabled = 1
                  AND dr.account_id = ?
                  AND dc.account_id = ?
                ORDER BY dr.priority DESC, dr.id ASC
                LIMIT 1
                """,
                    (item_id, account_id, account_id),
                ).fetchone(),
            )

        if not row:
            return None

        rule_id = int(cast(int | None, row["rule_id"]) or 0)
        card_id = int(cast(int | None, row["card_id"]) or 0)
        content_type = str(cast(str | None, row["content_type"]) or "").strip().lower()
        content = str(cast(str | None, row["content"]) or "")

        mode = _MODE_ALIASES.get(content_type)
        if mode is None:
            logger.warning(
                "Unknown delivery content_type for rule %s: %r",
                rule_id,
                content_type,
            )
            mode = DeliveryMode.UNKNOWN

        return DeliveryAction(
            mode=mode,
            content=content,
            card_id=card_id,
            rule_id=rule_id,
        )

    async def execute_delivery(
        self,
        order_id: str,
        item_id: str,
        account_id: str,
        buyer_id: str,
    ) -> bool:
        """Resolve and log a retained local delivery action."""
        action = self.resolve_delivery_rule(item_id, account_id)
        if not action:
            logger.info("No delivery rule for item %s", item_id)
            return False

        logger.info(
            "[%s] Delivery triggered for order %s, buyer=%s, mode=%s",
            account_id,
            order_id,
            buyer_id,
            action.mode.value,
        )
        # Actual delivery execution will be wired in a later bootstrap task.
        return True

    def log_delivery(self, order_id: str, card_id: int, status: str) -> None:
        """Record a delivery attempt in delivery_logs."""
        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            _ = conn.execute(
                "INSERT INTO delivery_logs (order_id, card_id, status) VALUES (?, ?, ?)",
                (order_id, card_id, status),
            )
