from __future__ import annotations

from . import BaseRepository


class OrderRepository(BaseRepository):
    """Repository stub for order-domain persistence.

    Primary table: orders
    Related tables: items, delivery_cards, delivery_rules, delivery_logs,
    risk_logs, polish_schedule
    """

    table_name: str = "orders"
