from __future__ import annotations

import sqlite3
from typing import cast

from .connection import get_db

EXPECTED_TABLES: tuple[str, ...] = (
    "admin_sessions",
    "ai_settings",
    "conversations",
    "default_replies",
    "delivery_cards",
    "delivery_logs",
    "delivery_rules",
    "item_keywords",
    "item_replies",
    "items",
    "keywords",
    "orders",
    "polish_schedule",
    "risk_logs",
    "system_settings",
    "xianyu_accounts",
)

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS xianyu_accounts (
        id INTEGER PRIMARY KEY,
        account_id TEXT NOT NULL UNIQUE,
        cookie_str TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL DEFAULT '',
        password TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        show_browser INTEGER NOT NULL DEFAULT 0 CHECK (show_browser IN (0, 1)),
        pause_duration INTEGER NOT NULL DEFAULT 10 CHECK (pause_duration BETWEEN 0 AND 60),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY,
        pattern TEXT NOT NULL,
        reply_content TEXT NOT NULL,
        is_regex INTEGER NOT NULL DEFAULT 0 CHECK (is_regex IN (0, 1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS item_keywords (
        id INTEGER PRIMARY KEY,
        item_id TEXT NOT NULL,
        pattern TEXT NOT NULL,
        reply_content TEXT NOT NULL,
        is_regex INTEGER NOT NULL DEFAULT 0 CHECK (is_regex IN (0, 1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS default_replies (
        id INTEGER PRIMARY KEY,
        content TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS item_replies (
        id INTEGER PRIMARY KEY,
        item_id TEXT NOT NULL,
        reply_content TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_settings (
        id INTEGER PRIMARY KEY,
        provider_type TEXT NOT NULL,
        api_key TEXT NOT NULL DEFAULT '',
        base_url TEXT NOT NULL DEFAULT '',
        model_name TEXT NOT NULL DEFAULT '',
        system_prompt TEXT NOT NULL DEFAULT '',
        max_tokens INTEGER NOT NULL DEFAULT 512,
        enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY,
        session_key TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        item_id TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        price TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        raw_data TEXT NOT NULL DEFAULT '',
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        order_id TEXT NOT NULL UNIQUE,
        item_id TEXT,
        buyer_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        amount TEXT NOT NULL DEFAULT '',
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS delivery_cards (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        content_type TEXT NOT NULL CHECK (content_type IN ('text', 'data', 'api', 'image', 'yifan')),
        content TEXT NOT NULL DEFAULT '',
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS delivery_rules (
        id INTEGER PRIMARY KEY,
        item_id TEXT NOT NULL,
        card_id INTEGER NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        account_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (card_id) REFERENCES delivery_cards(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS delivery_logs (
        id INTEGER PRIMARY KEY,
        order_id TEXT NOT NULL,
        card_id INTEGER,
        status TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_logs (
        id INTEGER PRIMARY KEY,
        account_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        details TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polish_schedule (
        id INTEGER PRIMARY KEY,
        account_id TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        start_hour INTEGER NOT NULL DEFAULT 8 CHECK (start_hour BETWEEN 0 AND 23),
        end_hour INTEGER NOT NULL DEFAULT 22 CHECK (end_hour BETWEEN 0 AND 23),
        random_delay_minutes INTEGER NOT NULL DEFAULT 0 CHECK (random_delay_minutes >= 0),
        last_run_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


def _ensure_account_compat_columns(conn: sqlite3.Connection) -> None:
    pragma_rows = cast(
        list[tuple[int, str, str, int, object | None, int]],
        conn.execute("PRAGMA table_info(xianyu_accounts)").fetchall(),
    )
    columns = {str(row[1]) for row in pragma_rows}
    if "pause_duration" not in columns:
        _ = conn.execute(
            "ALTER TABLE xianyu_accounts ADD COLUMN pause_duration INTEGER NOT NULL DEFAULT 10"
        )


def _ensure_yifan_content_type(conn: sqlite3.Connection) -> None:
    row = cast(
        tuple[str | None] | None,
        conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'delivery_cards'"
        ).fetchone(),
    )
    create_sql = str(row[0] or "") if row is not None else ""
    if "'yifan'" in create_sql:
        return

    conn.commit()
    _ = conn.execute("PRAGMA foreign_keys=OFF")
    try:
        _ = conn.execute(
            """
            CREATE TABLE delivery_cards_new (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                content_type TEXT NOT NULL CHECK (content_type IN ('text', 'data', 'api', 'image', 'yifan')),
                content TEXT NOT NULL DEFAULT '',
                account_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ = conn.execute(
            """
            INSERT INTO delivery_cards_new (id, name, content_type, content, account_id, created_at)
            SELECT id, name, content_type, content, account_id, created_at
            FROM delivery_cards
            """
        )
        _ = conn.execute("DROP TABLE delivery_cards")
        _ = conn.execute("ALTER TABLE delivery_cards_new RENAME TO delivery_cards")
        conn.commit()
    finally:
        _ = conn.execute("PRAGMA foreign_keys=ON")


def initialize_database(db_path: str) -> None:
    """Create the fresh single-admin schema."""
    with get_db(db_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            _ = conn.execute(statement)
        _ensure_account_compat_columns(conn)
        _ensure_yifan_content_type(conn)
