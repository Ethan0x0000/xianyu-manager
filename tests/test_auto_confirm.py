import unittest

from app.services.auto_confirm import (
    AutoConfirmService,
    CONFIRMABLE_STATUSES,
    OrderStatus,
    VALID_TRANSITIONS,
)


class TestOrderStatusConstants(unittest.TestCase):
    def test_order_status_enum_values(self) -> None:
        expected_values = {
            "PENDING": "pending",
            "PAID": "paid",
            "SHIPPED": "shipped",
            "DELIVERED": "delivered",
            "WAIT_CONFIRM": "wait_confirm",
            "COMPLETED": "completed",
            "CANCELLED": "cancelled",
            "UNKNOWN": "unknown",
        }

        self.assertEqual(
            {status.name: status.value for status in OrderStatus}, expected_values
        )

    def test_confirmable_statuses_constant(self) -> None:
        self.assertEqual(
            CONFIRMABLE_STATUSES,
            frozenset(
                {
                    OrderStatus.DELIVERED,
                    OrderStatus.WAIT_CONFIRM,
                    OrderStatus.COMPLETED,
                }
            ),
        )

    def test_valid_transitions_completeness(self) -> None:
        self.assertEqual(set(VALID_TRANSITIONS), set(OrderStatus))
        self.assertEqual(VALID_TRANSITIONS[OrderStatus.COMPLETED], set())
        self.assertEqual(VALID_TRANSITIONS[OrderStatus.CANCELLED], set())
        self.assertEqual(VALID_TRANSITIONS[OrderStatus.UNKNOWN], set(OrderStatus))


class TestAutoConfirmService(unittest.TestCase):
    def test_normalize_status_handles_all_known_aliases_and_unknown_values(
        self,
    ) -> None:
        service = AutoConfirmService()
        cases = {
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

        for raw_status, expected in cases.items():
            with self.subTest(raw_status=raw_status):
                self.assertIs(service.normalize_status(raw_status), expected)

        self.assertIs(
            service.normalize_status("  WAIT_CONFIRM  "), OrderStatus.WAIT_CONFIRM
        )
        self.assertIs(service.normalize_status("not-a-status"), OrderStatus.UNKNOWN)
        self.assertIs(service.normalize_status(""), OrderStatus.UNKNOWN)
        self.assertIs(service.normalize_status(None), OrderStatus.UNKNOWN)

    def test_check_confirm_eligibility_for_confirmable_and_non_confirmable_statuses(
        self,
    ) -> None:
        service = AutoConfirmService()
        for status in CONFIRMABLE_STATUSES:
            with self.subTest(status=status):
                result = service.check_confirm_eligibility("order-1", status)
                self.assertEqual(result.order_id, "order-1")
                self.assertIs(result.status, status)
                self.assertTrue(result.confirmable)
                self.assertEqual(result.reason, f"status={status.value}")

        result = service.check_confirm_eligibility("order-2", "waitbuyerpay")
        self.assertEqual(result.order_id, "order-2")
        self.assertIs(result.status, OrderStatus.PENDING)
        self.assertFalse(result.confirmable)
        self.assertIn("status=pending", result.reason)
        self.assertIn("delivered", result.reason)
        self.assertIn("wait_confirm", result.reason)
        self.assertIn("completed", result.reason)

    def test_validate_transition_for_valid_and_invalid_pairs(self) -> None:
        service = AutoConfirmService()
        valid_cases = [
            (OrderStatus.PENDING, OrderStatus.PAID),
            (OrderStatus.PENDING, OrderStatus.CANCELLED),
            (OrderStatus.PAID, OrderStatus.SHIPPED),
            (OrderStatus.SHIPPED, OrderStatus.DELIVERED),
            (OrderStatus.DELIVERED, OrderStatus.WAIT_CONFIRM),
            (OrderStatus.DELIVERED, OrderStatus.COMPLETED),
            (OrderStatus.WAIT_CONFIRM, OrderStatus.COMPLETED),
            (OrderStatus.UNKNOWN, OrderStatus.PAID),
        ]
        invalid_cases = [
            (OrderStatus.PENDING, OrderStatus.COMPLETED),
            (OrderStatus.PAID, OrderStatus.DELIVERED),
            (OrderStatus.COMPLETED, OrderStatus.PAID),
            (OrderStatus.CANCELLED, OrderStatus.PENDING),
            (OrderStatus.DELIVERED, OrderStatus.SHIPPED),
        ]

        for from_status, to_status in valid_cases:
            with self.subTest(from_status=from_status, to_status=to_status, valid=True):
                self.assertTrue(service.validate_transition(from_status, to_status))

        for from_status, to_status in invalid_cases:
            with self.subTest(
                from_status=from_status, to_status=to_status, valid=False
            ):
                self.assertFalse(service.validate_transition(from_status, to_status))


if __name__ == "__main__":
    _ = unittest.main()
