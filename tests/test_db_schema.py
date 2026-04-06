import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from typing import cast, override

from app.db.schema import EXPECTED_TABLES, initialize_database
from tests.helpers import make_test_db


class TestDatabaseSchema(unittest.TestCase):
    db_paths: list[str] = []

    @override
    def setUp(self) -> None:
        self.db_paths = []

    @override
    def tearDown(self) -> None:
        for db_path in self.db_paths:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def _make_blank_db_path(self) -> str:
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_paths.append(db_path)
        return db_path

    def _table_columns(self, db_path: str, table_name: str) -> list[str]:
        with closing(sqlite3.connect(db_path)) as conn:
            rows = cast(
                list[tuple[int, str, str, int, object | None, int]],
                conn.execute(f"PRAGMA table_info({table_name})").fetchall(),
            )
        return [name for _, name, _, _, _, _ in rows]

    def test_initialize_database_creates_all_expected_tables(self) -> None:
        db_path = self._make_blank_db_path()

        initialize_database(db_path)

        with closing(sqlite3.connect(db_path)) as conn:
            rows = cast(
                list[tuple[str]],
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall(),
            )

        self.assertEqual({name for (name,) in rows}, set(EXPECTED_TABLES))

    def test_initialize_database_is_idempotent(self) -> None:
        db_path = make_test_db()
        self.db_paths.append(db_path)

        initialize_database(db_path)
        initialize_database(db_path)

        with closing(sqlite3.connect(db_path)) as conn:
            rows = cast(
                list[tuple[str]],
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall(),
            )

        self.assertEqual({name for (name,) in rows}, set(EXPECTED_TABLES))

    def test_expected_tables_have_spot_checked_columns(self) -> None:
        db_path = make_test_db()
        self.db_paths.append(db_path)

        self.assertTrue(
            {
                "id",
                "account_id",
                "cookie_str",
                "enabled",
                "pause_duration",
                "show_browser",
                "created_at",
                "updated_at",
            }.issubset(set(self._table_columns(db_path, "xianyu_accounts")))
        )
        self.assertTrue(
            {
                "id",
                "order_id",
                "item_id",
                "buyer_id",
                "status",
                "amount",
                "account_id",
            }.issubset(set(self._table_columns(db_path, "orders")))
        )
        self.assertTrue(
            {
                "id",
                "provider_type",
                "api_key",
                "base_url",
                "model_name",
                "system_prompt",
                "max_tokens",
                "enabled",
            }.issubset(set(self._table_columns(db_path, "ai_settings")))
        )


if __name__ == "__main__":
    _ = unittest.main()
