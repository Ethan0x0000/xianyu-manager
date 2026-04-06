from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from typing import cast
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from app.db.connection import get_db
from tests.helpers import make_settings, make_test_db

AUTH_TOKEN = "compat-token"


@pytest.fixture
def compat_client() -> Iterator[tuple[TestClient, str]]:
    db_path = make_test_db()
    store = SessionStore()
    _ = store.create_session(AUTH_TOKEN, ttl_seconds=60)

    with patch("app.api.dependencies.get_session_store", return_value=store):
        app = create_app(settings=make_settings(db_path=db_path))
        with TestClient(app) as client:
            yield client, db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def _insert_item(
    db_path: str,
    *,
    item_id: str,
    account_id: str,
    title: str,
    price: str = "10.00",
    status: str = "active",
    raw_data: str = '{"source":"test"}',
    created_at: str = "2026-04-06 10:00:00",
    updated_at: str = "2026-04-06 10:00:00",
) -> int:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO items (
                item_id, title, price, status, raw_data, account_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                title,
                price,
                status,
                raw_data,
                account_id,
                created_at,
                updated_at,
            ),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        return row_id


def _fetch_item(db_path: str, account_id: str, item_id: str) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT * FROM items WHERE account_id = ? AND item_id = ? LIMIT 1",
                (account_id, item_id),
            ).fetchone(),
        )


def test_list_items_supports_search_filter_and_account_filter(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_item(db_path, item_id="item-1", account_id="acct-1", title="Phone Case")
    _ = _insert_item(db_path, item_id="item-2", account_id="acct-1", title="Desk Lamp")
    _ = _insert_item(
        db_path, item_id="item-3", account_id="acct-2", title="Leather Case"
    )

    response = client.get(
        "/api/items",
        headers=_auth_headers(),
        params={"account_id": "acct-1", "q": "Case"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "item_id": "item-1",
                "title": "Phone Case",
                "price": "10.00",
                "status": "active",
                "raw_data": '{"source":"test"}',
                "account_id": "acct-1",
                "created_at": "2026-04-06 10:00:00",
                "updated_at": "2026-04-06 10:00:00",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }


def test_list_items_supports_pagination(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_item(
        db_path,
        item_id="item-1",
        account_id="acct-1",
        title="First",
        updated_at="2026-04-06 10:00:00",
    )
    _ = _insert_item(
        db_path,
        item_id="item-2",
        account_id="acct-1",
        title="Second",
        updated_at="2026-04-06 11:00:00",
    )
    _ = _insert_item(
        db_path,
        item_id="item-3",
        account_id="acct-1",
        title="Third",
        updated_at="2026-04-06 12:00:00",
    )

    response = client.get(
        "/api/items",
        headers=_auth_headers(),
        params={"account_id": "acct-1", "page": 2, "page_size": 1},
    )

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["total"] == 3
    assert payload["page"] == 2
    assert payload["page_size"] == 1
    items = cast(list[dict[str, object]], payload["items"])
    assert [item["item_id"] for item in items] == ["item-2"]


def test_update_item_updates_title_and_timestamp(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    old_updated_at = "2000-01-01 00:00:00"
    _ = _insert_item(
        db_path,
        item_id="item-1",
        account_id="acct-1",
        title="Original title",
        updated_at=old_updated_at,
    )

    response = client.put(
        "/api/items/acct-1/item-1",
        headers=_auth_headers(),
        json={"title": "Updated title"},
    )

    assert response.status_code == 200
    payload = cast(dict[str, object], response.json())
    assert payload["item_id"] == "item-1"
    assert payload["account_id"] == "acct-1"
    assert payload["title"] == "Updated title"
    assert payload["updated_at"] != old_updated_at

    row = _fetch_item(db_path, "acct-1", "item-1")
    assert row is not None
    assert row["title"] == "Updated title"
    assert row["updated_at"] != old_updated_at


def test_update_missing_item_returns_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.put(
        "/api/items/acct-1/missing-item",
        headers=_auth_headers(),
        json={"title": "Updated title"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_delete_item_removes_row(compat_client: tuple[TestClient, str]) -> None:
    client, db_path = compat_client
    _ = _insert_item(db_path, item_id="item-1", account_id="acct-1", title="Delete me")

    response = client.delete(
        "/api/items/acct-1/item-1",
        headers=_auth_headers(),
    )

    assert response.status_code == 204
    assert _fetch_item(db_path, "acct-1", "item-1") is None


def test_delete_missing_item_returns_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.delete(
        "/api/items/acct-1/missing-item",
        headers=_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_batch_delete_removes_only_matching_account_items(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_item(db_path, item_id="item-1", account_id="acct-1", title="Delete 1")
    _ = _insert_item(db_path, item_id="item-2", account_id="acct-1", title="Delete 2")
    _ = _insert_item(db_path, item_id="item-3", account_id="acct-1", title="Keep 1")
    _ = _insert_item(db_path, item_id="item-1", account_id="acct-2", title="Keep other")

    response = client.request(
        "DELETE",
        "/api/items",
        headers=_auth_headers(),
        json={"account_id": "acct-1", "item_ids": ["item-1", "item-2"]},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    assert _fetch_item(db_path, "acct-1", "item-1") is None
    assert _fetch_item(db_path, "acct-1", "item-2") is None
    assert _fetch_item(db_path, "acct-1", "item-3") is not None
    assert _fetch_item(db_path, "acct-2", "item-1") is not None


def test_sync_returns_triggered_status(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.post(
        "/api/items/sync",
        headers=_auth_headers(),
        json={"account_id": "acct-1"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "triggered", "account_id": "acct-1"}


def test_sync_missing_account_id_returns_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.post(
        "/api/items/sync",
        headers=_auth_headers(),
        json={},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Account not found"}
