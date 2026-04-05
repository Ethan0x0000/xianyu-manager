"""Repository stubs for the fresh sqlite schema."""

from __future__ import annotations

import sqlite3
from typing import cast

from ..connection import get_db

RowDict = dict[str, object]


def _row_to_dict(row: sqlite3.Row) -> RowDict:
    keys = row.keys()
    return {key: row[key] for key in keys}


class BaseRepository:
    """Minimal sqlite repository helper for table-backed stubs."""

    table_name: str = ""
    id_column: str = "id"
    db_path: str

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def get_all(self) -> list[RowDict]:
        with get_db(self.db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                    f"SELECT * FROM {self.table_name} ORDER BY {self.id_column}"
                ).fetchall(),
            )
        return [_row_to_dict(row) for row in rows]

    def get_by_id(self, record_id: object) -> RowDict | None:
        with get_db(self.db_path) as conn:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    f"SELECT * FROM {self.table_name} WHERE {self.id_column} = ?",
                    (record_id,),
                ).fetchone(),
            )
        return _row_to_dict(row) if row else None

    def create(self, **values: object) -> int | str:
        if not values:
            raise ValueError("create() requires at least one value")

        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )

        record_id = values.get(self.id_column)
        if isinstance(record_id, (int, str)):
            return record_id
        if cursor.lastrowid is None:
            raise RuntimeError(f"Insert into {self.table_name} did not return a row id")
        return cursor.lastrowid

    def update(self, record_id: object, **values: object) -> bool:
        if not values:
            raise ValueError("update() requires at least one value")

        assignments = ", ".join(f"{column} = ?" for column in values)
        params = tuple(values.values()) + (record_id,)
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE {self.id_column} = ?",
                params,
            )

        return cursor.rowcount > 0

    def delete(self, record_id: object) -> bool:
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE {self.id_column} = ?",
                (record_id,),
            )

        return cursor.rowcount > 0


__all__ = ["BaseRepository", "RowDict"]
