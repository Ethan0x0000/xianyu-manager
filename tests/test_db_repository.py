import os
import unittest
from typing import cast

from app.db.repositories.account_repository import AccountRepository
from tests.helpers import make_test_db


class TestAccountRepository(unittest.TestCase):
    db_path: str = ""
    repo: AccountRepository = cast(AccountRepository, cast(object, None))

    def setUp(self) -> None:
        self.db_path = make_test_db()
        self.repo = AccountRepository(self.db_path)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_create_inserts_record_and_returns_id(self) -> None:
        record_id = cast(
            int, self.repo.create(account_id="account-1", username="seller-one")
        )

        self.assertIsInstance(record_id, int)
        record = self.repo.get_by_id(record_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["account_id"], "account-1")
        self.assertEqual(record["username"], "seller-one")

    def test_get_all_returns_all_records(self) -> None:
        first_id = cast(
            int, self.repo.create(account_id="account-1", username="seller-one")
        )
        second_id = cast(
            int, self.repo.create(account_id="account-2", username="seller-two")
        )

        records = self.repo.get_all()

        self.assertEqual(len(records), 2)
        self.assertEqual([record["id"] for record in records], [first_id, second_id])
        self.assertEqual(
            [record["account_id"] for record in records], ["account-1", "account-2"]
        )

    def test_get_by_id_returns_record_or_none(self) -> None:
        record_id = cast(
            int, self.repo.create(account_id="account-1", username="seller-one")
        )

        record = self.repo.get_by_id(record_id)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["id"], record_id)
        self.assertEqual(record["account_id"], "account-1")
        self.assertIsNone(self.repo.get_by_id(record_id + 1000))

    def test_update_modifies_record_and_returns_true_or_false_for_missing(self) -> None:
        record_id = cast(
            int, self.repo.create(account_id="account-1", username="seller-one")
        )

        updated = self.repo.update(record_id, username="renamed", enabled=0)

        self.assertTrue(updated)
        record = self.repo.get_by_id(record_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["username"], "renamed")
        self.assertEqual(record["enabled"], 0)
        self.assertFalse(self.repo.update(record_id + 1000, username="missing"))

    def test_delete_removes_record_and_returns_true_or_false_for_missing(self) -> None:
        record_id = cast(
            int, self.repo.create(account_id="account-1", username="seller-one")
        )

        deleted = self.repo.delete(record_id)

        self.assertTrue(deleted)
        self.assertIsNone(self.repo.get_by_id(record_id))
        self.assertFalse(self.repo.delete(record_id))

    def test_create_with_no_values_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            _ = self.repo.create()

    def test_update_with_no_values_raises_value_error(self) -> None:
        record_id = cast(int, self.repo.create(account_id="account-1"))

        with self.assertRaises(ValueError):
            _ = self.repo.update(record_id)


if __name__ == "__main__":
    _ = unittest.main()
