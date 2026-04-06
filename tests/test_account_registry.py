import unittest
from unittest.mock import patch

from app.runtime.account_registry import (
    AccountEntry,
    AccountNotFoundError,
    AccountRegistry,
    DuplicateAccountError,
    get_registry,
)


class TestAccountRegistry(unittest.TestCase):
    registry: AccountRegistry = AccountRegistry()

    def setUp(self) -> None:
        self.registry = AccountRegistry()

    def test_add_account_creates_entry_with_expected_fields(self) -> None:
        entry = self.registry.add_account(
            account_id="account-1",
            cookie_str="cookie=value",
            username="seller",
            notes="primary account",
        )

        self.assertIsInstance(entry, AccountEntry)
        self.assertEqual(entry.account_id, "account-1")
        self.assertEqual(entry.cookie_str, "cookie=value")
        self.assertEqual(entry.username, "seller")
        self.assertEqual(entry.notes, "primary account")
        self.assertTrue(entry.enabled)
        self.assertIsNone(entry.runtime_instance)
        self.assertIsNone(entry.background_task)

    def test_add_account_raises_duplicate_error_for_same_account_id(self) -> None:
        _ = self.registry.add_account("account-1", "cookie=value")

        with self.assertRaises(DuplicateAccountError):
            _ = self.registry.add_account("account-1", "cookie=other")

    def test_remove_account_deletes_entry_and_missing_account_raises(self) -> None:
        _ = self.registry.add_account("account-1", "cookie=value")

        self.registry.remove_account("account-1")

        self.assertIsNone(self.registry.get_account("account-1"))
        with self.assertRaises(AccountNotFoundError):
            self.registry.remove_account("account-1")

    def test_get_account_returns_entry_or_none(self) -> None:
        self.assertIsNone(self.registry.get_account("missing"))

        created = self.registry.add_account("account-1", "cookie=value")

        self.assertIs(self.registry.get_account("account-1"), created)

    def test_list_accounts_returns_all_entries(self) -> None:
        _ = self.registry.add_account("account-1", "cookie=1", username="one")
        _ = self.registry.add_account("account-2", "cookie=2", username="two")

        entries = self.registry.list_accounts()

        self.assertEqual(len(entries), 2)
        self.assertCountEqual(
            [entry.account_id for entry in entries], ["account-1", "account-2"]
        )

    def test_enable_and_disable_account_toggle_enabled_flag(self) -> None:
        _ = self.registry.add_account("account-1", "cookie=value")

        self.registry.disable_account("account-1")
        entry_after_disable = self.registry.get_account("account-1")
        self.assertIsNotNone(entry_after_disable)
        assert entry_after_disable is not None
        self.assertFalse(entry_after_disable.enabled)

        self.registry.enable_account("account-1")
        entry_after_enable = self.registry.get_account("account-1")
        self.assertIsNotNone(entry_after_enable)
        assert entry_after_enable is not None
        self.assertTrue(entry_after_enable.enabled)

    def test_disable_account_raises_for_missing_account(self) -> None:
        with self.assertRaises(AccountNotFoundError):
            self.registry.disable_account("missing")

    def test_register_runtime_updates_runtime_state(self) -> None:
        runtime_instance = object()
        _ = self.registry.add_account("account-1", "cookie=value")

        self.registry.register_runtime("account-1", runtime_instance)

        entry = self.registry.get_account("account-1")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertIs(entry.runtime_instance, runtime_instance)
        self.assertIsNone(entry.background_task)

    def test_register_runtime_raises_for_missing_account(self) -> None:
        with self.assertRaises(AccountNotFoundError):
            self.registry.register_runtime("missing", object())

    def test_count_returns_number_of_registered_accounts(self) -> None:
        self.assertEqual(self.registry.count(), 0)

        _ = self.registry.add_account("account-1", "cookie=1")
        _ = self.registry.add_account("account-2", "cookie=2")

        self.assertEqual(self.registry.count(), 2)

    def test_get_registry_returns_singleton_instance(self) -> None:
        with patch("app.runtime.account_registry._default_registry", None):
            first = get_registry()
            second = get_registry()

        self.assertIs(first, second)


if __name__ == "__main__":
    _ = unittest.main()
