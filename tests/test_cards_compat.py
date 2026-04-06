from __future__ import annotations

import json
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


def _insert_card(
    db_path: str,
    *,
    name: str,
    content_type: str,
    content: str,
    account_id: str = "acct-1",
) -> int:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO delivery_cards (name, content_type, content, account_id) VALUES (?, ?, ?, ?)",
            (name, content_type, content, account_id),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        return row_id


def _fetch_one(
    db_path: str,
    sql: str,
    params: tuple[object, ...],
) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(sqlite3.Row | None, conn.execute(sql, params).fetchone())


def test_create_text_card_and_list_cards_by_account(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    create_response = client.post(
        "/api/cards",
        headers=_auth_headers(),
        json={
            "name": "Welcome card",
            "content_type": "text",
            "content": "hello buyer",
            "account_id": "acct-1",
        },
    )

    assert create_response.status_code == 201
    created = cast(dict[str, object], create_response.json())
    assert created["name"] == "Welcome card"
    assert created["content_type"] == "text"
    assert created["content"] == "hello buyer"
    assert created["account_id"] == "acct-1"
    assert isinstance(created["id"], int)

    list_response = client.get(
        "/api/cards",
        headers=_auth_headers(),
        params={"account_id": "acct-1"},
    )

    assert list_response.status_code == 200
    assert list_response.json() == {
        "cards": [
            {
                "id": created["id"],
                "name": "Welcome card",
                "content_type": "text",
                "content": "hello buyer",
                "account_id": "acct-1",
                "created_at": created["created_at"],
            }
        ]
    }


def test_get_and_update_card_by_id(compat_client: tuple[TestClient, str]) -> None:
    client, db_path = compat_client
    card_id = _insert_card(
        db_path,
        name="Before",
        content_type="text",
        content="old",
    )

    detail_response = client.get(f"/api/cards/{card_id}", headers=_auth_headers())

    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Before"

    update_response = client.put(
        f"/api/cards/{card_id}",
        headers=_auth_headers(),
        json={
            "name": "After",
            "content_type": "image",
            "content": "https://cdn.example.test/card.png",
            "account_id": "acct-1",
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "After"
    assert update_response.json()["content_type"] == "image"

    row = _fetch_one(
        db_path,
        "SELECT name, content_type, content, account_id FROM delivery_cards WHERE id = ?",
        (card_id,),
    )
    assert row is not None
    assert dict(row) == {
        "name": "After",
        "content_type": "image",
        "content": "https://cdn.example.test/card.png",
        "account_id": "acct-1",
    }


def test_create_yifan_card_accepts_valid_json_config(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.post(
        "/api/cards",
        headers=_auth_headers(),
        json={
            "name": "Yifan card",
            "content_type": "yifan",
            "content": json.dumps(
                {
                    "callback_url": "https://vendor.example.test/callback",
                    "merchant_id": "merchant-123",
                }
            ),
            "account_id": "acct-1",
        },
    )

    assert response.status_code == 201
    payload = cast(dict[str, object], response.json())
    assert payload["content_type"] == "yifan"
    assert payload["name"] == "Yifan card"


def test_create_yifan_card_requires_merchant_id(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.post(
        "/api/cards",
        headers=_auth_headers(),
        json={
            "name": "Broken yifan",
            "content_type": "yifan",
            "content": json.dumps(
                {
                    "callback_url": "https://vendor.example.test/callback",
                }
            ),
            "account_id": "acct-1",
        },
    )

    assert response.status_code == 422
    payload = cast(dict[str, object], response.json())
    assert "merchant_id" in str(payload)


def test_create_update_and_delete_delivery_rule(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    old_card_id = _insert_card(
        db_path,
        name="Old card",
        content_type="text",
        content="old",
    )
    new_card_id = _insert_card(
        db_path,
        name="New card",
        content_type="image",
        content="new",
    )

    create_response = client.post(
        "/api/delivery/rules",
        headers=_auth_headers(),
        json={
            "item_id": "item-1",
            "card_id": old_card_id,
            "priority": 3,
            "enabled": True,
            "account_id": "acct-1",
        },
    )

    assert create_response.status_code == 201
    created_rule = cast(dict[str, object], create_response.json())
    assert created_rule == {
        "id": created_rule["id"],
        "item_id": "item-1",
        "card_id": old_card_id,
        "priority": 3,
        "enabled": True,
        "account_id": "acct-1",
        "created_at": created_rule["created_at"],
    }

    list_response = client.get("/api/delivery/rules", headers=_auth_headers())

    assert list_response.status_code == 200
    assert list_response.json() == {
        "rules": [
            {
                "id": created_rule["id"],
                "item_id": "item-1",
                "priority": 3,
                "enabled": 1,
                "account_id": "acct-1",
                "card_id": old_card_id,
                "card_name": "Old card",
                "content_type": "text",
            }
        ]
    }

    update_response = client.put(
        f"/api/delivery/rules/{created_rule['id']}",
        headers=_auth_headers(),
        json={"card_id": new_card_id, "priority": 8, "enabled": False},
    )

    assert update_response.status_code == 200
    assert update_response.json()["card_id"] == new_card_id
    assert update_response.json()["priority"] == 8
    assert update_response.json()["enabled"] is False

    delete_response = client.delete(
        f"/api/delivery/rules/{created_rule['id']}",
        headers=_auth_headers(),
    )

    assert delete_response.status_code == 204
    assert client.get("/api/delivery/rules", headers=_auth_headers()).json() == {
        "rules": []
    }


def test_delete_card_removes_it_and_subsequent_get_returns_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    card_id = _insert_card(
        db_path,
        name="Delete me",
        content_type="text",
        content="bye",
    )

    delete_response = client.delete(f"/api/cards/{card_id}", headers=_auth_headers())

    assert delete_response.status_code == 204
    assert (
        client.get(f"/api/cards/{card_id}", headers=_auth_headers()).status_code == 404
    )
    assert (
        _fetch_one(db_path, "SELECT * FROM delivery_cards WHERE id = ?", (card_id,))
        is None
    )


def test_delete_missing_card_returns_404(compat_client: tuple[TestClient, str]) -> None:
    client, _ = compat_client

    response = client.delete("/api/cards/9999", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Card not found"}
