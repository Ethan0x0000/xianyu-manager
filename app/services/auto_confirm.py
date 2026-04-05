"""Auto-confirm and order-status domain service.

Normalizes order status and evaluates auto-confirm eligibility.
Extracted from XianyuAutoAsync.py and order_status_handler.py.

FROZEN GATING RULES:
- Only confirm orders in: DELIVERED, WAIT_CONFIRM, COMPLETED states
- Never fire auto-confirm outside these states
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class OrderStatus(enum.Enum):
    PENDING = "pending"  # Waiting for payment
    PAID = "paid"  # Payment received
    SHIPPED = "shipped"  # Item shipped
    DELIVERED = "delivered"  # Delivered, waiting confirm
    WAIT_CONFIRM = "wait_confirm"  # Waiting for buyer to confirm
    COMPLETED = "completed"  # Order completed
    CANCELLED = "cancelled"  # Order cancelled
    UNKNOWN = "unknown"  # Unrecognized status


CONFIRMABLE_STATUSES = frozenset(
    [
        OrderStatus.DELIVERED,
        OrderStatus.WAIT_CONFIRM,
        OrderStatus.COMPLETED,
    ]
)

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.CANCELLED},
    OrderStatus.DELIVERED: {OrderStatus.WAIT_CONFIRM, OrderStatus.COMPLETED},
    OrderStatus.WAIT_CONFIRM: {OrderStatus.COMPLETED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.UNKNOWN: {status for status in OrderStatus},
}


@dataclass
class ConfirmEligibility:
    order_id: str
    status: OrderStatus
    confirmable: bool
    reason: str = ""


class AutoConfirmService:
    """Order status normalization and auto-confirm eligibility."""

    def normalize_status(self, raw_status: str | None) -> OrderStatus:
        """Normalize a raw status string to OrderStatus enum."""
        if not raw_status:
            return OrderStatus.UNKNOWN

        raw = raw_status.lower().strip()

        mapping = {
            "waitbuyerpay": OrderStatus.PENDING,
            "wait_buyer_pay": OrderStatus.PENDING,
            "paied": OrderStatus.PAID,
            "paid": OrderStatus.PAID,
            "waitbuyerconfirmgoods": OrderStatus.SHIPPED,
            "wait_buyer_confirm_goods": OrderStatus.SHIPPED,
            "delivered": OrderStatus.DELIVERED,
            "waitsellerdelivergoods": OrderStatus.PAID,
            "tradefinished": OrderStatus.COMPLETED,
            "trade_finished": OrderStatus.COMPLETED,
            "completed": OrderStatus.COMPLETED,
            "wait_confirm": OrderStatus.WAIT_CONFIRM,
            "waitconfirm": OrderStatus.WAIT_CONFIRM,
            "tradeclosed": OrderStatus.CANCELLED,
            "trade_closed": OrderStatus.CANCELLED,
            "cancelled": OrderStatus.CANCELLED,
        }

        normalized = mapping.get(raw, OrderStatus.UNKNOWN)
        if normalized is OrderStatus.UNKNOWN:
            logger.debug("Unrecognized auto-confirm status: %r", raw_status)
        return normalized

    def check_confirm_eligibility(
        self,
        order_id: str,
        status: OrderStatus | str,
    ) -> ConfirmEligibility:
        """Check if an order is eligible for auto-confirm."""
        if isinstance(status, str):
            status = self.normalize_status(status)

        confirmable = status in CONFIRMABLE_STATUSES
        confirmable_values = ", ".join(
            sorted(candidate.value for candidate in CONFIRMABLE_STATUSES)
        )
        reason = f"status={status.value}"
        if not confirmable:
            reason += f" not in confirmable set [{confirmable_values}]"

        return ConfirmEligibility(
            order_id=order_id,
            status=status,
            confirmable=confirmable,
            reason=reason,
        )

    def validate_transition(
        self,
        from_status: OrderStatus,
        to_status: OrderStatus,
    ) -> bool:
        """Check if a status transition is valid. Returns False for invalid transitions."""
        valid_nexts = VALID_TRANSITIONS.get(from_status, set())
        return to_status in valid_nexts


__all__ = [
    "AutoConfirmService",
    "CONFIRMABLE_STATUSES",
    "ConfirmEligibility",
    "OrderStatus",
    "VALID_TRANSITIONS",
]
