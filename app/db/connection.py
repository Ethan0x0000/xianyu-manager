from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

_local = threading.local()


@contextmanager
def get_db(db_path: str) -> Iterator[sqlite3.Connection]:
    """Thread-safe SQLite connection context manager."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _ = conn.execute("PRAGMA journal_mode=WAL")
    _ = conn.execute("PRAGMA foreign_keys=ON")
    _local.connection = conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if getattr(_local, "connection", None) is conn:
            delattr(_local, "connection")
        conn.close()
