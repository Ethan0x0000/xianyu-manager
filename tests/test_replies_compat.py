from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

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


def _insert_keyword(
    db_path: str,
    *,
    pattern: str,
    reply_content: str,
    item_id: str | None = None,
    is_regex: bool = False,
    enabled: bool = True,
) -> int:
    sql = (
        "INSERT INTO item_keywords (item_id, pattern, reply_content, is_regex, enabled) VALUES (?, ?, ?, ?, ?)"
        if item_id
        else "INSERT INTO keywords (pattern, reply_content, is_regex, enabled) VALUES (?, ?, ?, ?)"
    )
    params: tuple[object, ...] = (
        (item_id, pattern, reply_content, int(is_regex), int(enabled))
        if item_id
        else (pattern, reply_content, int(is_regex), int(enabled))
    )
    with get_db(db_path) as conn:
        cursor = conn.execute(sql, params)
        row_id = cursor.lastrowid
        assert row_id is not None
        return row_id


def _insert_ai_settings(
    db_path: str,
    *,
    provider_type: str = "openai",
    api_key: str = "secret-key",
    base_url: str = "https://api.example.test/v1",
    model_name: str = "gpt-4o-mini",
    system_prompt: str = "be helpful",
    max_tokens: int = 256,
    enabled: bool = True,
) -> int:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_settings (
                provider_type, api_key, base_url, model_name, system_prompt, max_tokens, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_type,
                api_key,
                base_url,
                model_name,
                system_prompt,
                max_tokens,
                int(enabled),
            ),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        return row_id


def _fetch_one(
    db_path: str, sql: str, params: tuple[object, ...]
) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(sqlite3.Row | None, conn.execute(sql, params).fetchone())


def test_update_general_keyword_updates_keywords_table(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    keyword_id = _insert_keyword(
        db_path,
        pattern="hello",
        reply_content="world",
    )

    response = client.put(
        f"/api/replies/keywords/{keyword_id}",
        headers=_auth_headers(),
        json={
            "pattern": "updated",
            "reply_content": "changed",
            "is_regex": True,
            "enabled": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": keyword_id,
        "pattern": "updated",
        "reply_content": "changed",
        "item_id": None,
        "is_regex": True,
        "enabled": False,
        "scope": "general",
    }
    row = _fetch_one(
        db_path,
        "SELECT pattern, reply_content, is_regex, enabled FROM keywords WHERE id = ?",
        (keyword_id,),
    )
    assert row is not None
    assert dict(row) == {
        "pattern": "updated",
        "reply_content": "changed",
        "is_regex": 1,
        "enabled": 0,
    }


def test_update_item_keyword_updates_item_keywords_table(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    keyword_id = _insert_keyword(
        db_path,
        item_id="item-1",
        pattern="hello",
        reply_content="world",
    )

    response = client.put(
        f"/api/replies/keywords/{keyword_id}",
        headers=_auth_headers(),
        json={
            "pattern": "special",
            "reply_content": "item response",
            "is_regex": False,
            "enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": keyword_id,
        "pattern": "special",
        "reply_content": "item response",
        "item_id": "item-1",
        "is_regex": False,
        "enabled": True,
        "scope": "item",
    }
    row = _fetch_one(
        db_path,
        "SELECT item_id, pattern, reply_content, is_regex, enabled FROM item_keywords WHERE id = ?",
        (keyword_id,),
    )
    assert row is not None
    assert dict(row) == {
        "item_id": "item-1",
        "pattern": "special",
        "reply_content": "item response",
        "is_regex": 0,
        "enabled": 1,
    }


def test_delete_keyword_removes_rows_from_both_keyword_tables(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    general_id = _insert_keyword(db_path, pattern="hello", reply_content="world")
    item_id = _insert_keyword(
        db_path,
        item_id="item-1",
        pattern="special",
        reply_content="item response",
    )

    general_response = client.delete(
        f"/api/replies/keywords/{general_id}",
        headers=_auth_headers(),
    )
    item_response = client.delete(
        f"/api/replies/keywords/{item_id}",
        headers=_auth_headers(),
    )

    assert general_response.status_code == 204
    assert item_response.status_code == 204
    assert (
        _fetch_one(db_path, "SELECT id FROM keywords WHERE id = ?", (general_id,))
        is None
    )
    assert (
        _fetch_one(db_path, "SELECT id FROM item_keywords WHERE id = ?", (item_id,))
        is None
    )


def test_default_reply_round_trip_supports_create_list_update_and_delete(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    create_response = client.post(
        "/api/replies/default",
        headers=_auth_headers(),
        json={"content": "fallback", "enabled": True},
    )

    assert create_response.status_code == 201
    created = cast(dict[str, object], create_response.json())
    assert created["content"] == "fallback"
    assert created["enabled"] is True
    assert created["created_at"]

    list_response = client.get("/api/replies/default", headers=_auth_headers())
    assert list_response.status_code == 200
    assert list_response.json() == [created]

    update_response = client.put(
        f"/api/replies/default/{created['id']}",
        headers=_auth_headers(),
        json={"content": "updated fallback", "enabled": False},
    )
    assert update_response.status_code == 200
    updated = cast(dict[str, object], update_response.json())
    assert updated["id"] == created["id"]
    assert updated["content"] == "updated fallback"
    assert updated["enabled"] is False

    delete_response = client.delete(
        f"/api/replies/default/{created['id']}",
        headers=_auth_headers(),
    )
    assert delete_response.status_code == 204

    final_list_response = client.get("/api/replies/default", headers=_auth_headers())
    assert final_list_response.status_code == 200
    assert final_list_response.json() == []


def test_item_reply_round_trip_supports_create_list_update_and_delete(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    create_response = client.post(
        "/api/replies/item-replies",
        headers=_auth_headers(),
        json={"item_id": "item-1", "reply_content": "auto reply", "enabled": True},
    )

    assert create_response.status_code == 201
    created = cast(dict[str, object], create_response.json())
    assert created["item_id"] == "item-1"
    assert created["reply_content"] == "auto reply"
    assert created["enabled"] is True

    list_response = client.get(
        "/api/replies/item-replies",
        headers=_auth_headers(),
        params={"item_id": "item-1"},
    )
    assert list_response.status_code == 200
    assert list_response.json() == [created]

    update_response = client.put(
        f"/api/replies/item-replies/{created['id']}",
        headers=_auth_headers(),
        json={"item_id": "item-1", "reply_content": "updated reply", "enabled": False},
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "id": created["id"],
        "item_id": "item-1",
        "reply_content": "updated reply",
        "enabled": False,
    }

    delete_response = client.delete(
        f"/api/replies/item-replies/{created['id']}",
        headers=_auth_headers(),
    )
    assert delete_response.status_code == 204
    assert (
        client.get(
            "/api/replies/item-replies",
            headers=_auth_headers(),
            params={"item_id": "item-1"},
        ).json()
        == []
    )


def test_keyword_import_accepts_valid_payload_and_export_separates_scopes(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    import_response = client.post(
        "/api/replies/keywords/import",
        headers=_auth_headers(),
        json=[
            {"pattern": "hello", "reply_content": "world"},
            {
                "pattern": "special",
                "reply_content": "item response",
                "item_id": "item-1",
                "is_regex": True,
                "enabled": False,
            },
        ],
    )

    assert import_response.status_code == 200
    assert import_response.json() == {"imported": 2}

    export_response = client.get(
        "/api/replies/keywords/export",
        headers=_auth_headers(),
    )

    assert export_response.status_code == 200
    assert export_response.json() == {
        "keywords": [
            {
                "id": 1,
                "pattern": "hello",
                "reply_content": "world",
                "item_id": None,
                "is_regex": False,
                "enabled": True,
                "scope": "general",
            }
        ],
        "item_keywords": [
            {
                "id": 1,
                "pattern": "special",
                "reply_content": "item response",
                "item_id": "item-1",
                "is_regex": True,
                "enabled": False,
                "scope": "item",
            }
        ],
    }


def test_keyword_import_rejects_invalid_payload(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client

    response = client.post(
        "/api/replies/keywords/import",
        headers=_auth_headers(),
        json=[{"pattern": "hello"}],
    )

    assert response.status_code == 422
    assert _fetch_one(db_path, "SELECT id FROM keywords LIMIT 1", ()) is None
    assert _fetch_one(db_path, "SELECT id FROM item_keywords LIMIT 1", ()) is None


def test_ai_settings_put_get_and_test_mask_api_key(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client

    put_response = client.put(
        "/api/ai/settings",
        headers=_auth_headers(),
        json={
            "provider_type": "openai",
            "api_key": "super-secret",
            "base_url": "https://api.example.test/v1",
            "model_name": "gpt-4o-mini",
            "system_prompt": "be helpful",
            "max_tokens": 128,
            "enabled": True,
        },
    )

    assert put_response.status_code == 200
    updated = cast(dict[str, object], put_response.json())
    assert updated == {
        "id": 1,
        "provider_type": "openai",
        "api_key": "****",
        "base_url": "https://api.example.test/v1",
        "model_name": "gpt-4o-mini",
        "system_prompt": "be helpful",
        "max_tokens": 128,
        "enabled": True,
    }

    get_response = client.get("/api/ai/settings", headers=_auth_headers())
    assert get_response.status_code == 200
    assert get_response.json() == updated

    row = _fetch_one(
        db_path,
        "SELECT api_key FROM ai_settings WHERE id = ?",
        (1,),
    )
    assert row is not None
    assert row["api_key"] == "super-secret"

    test_response = client.post("/api/ai/test", headers=_auth_headers())
    assert test_response.status_code == 200
    assert test_response.json()["success"] is True
    assert test_response.json()["message"]


def test_ai_settings_update_preserves_existing_api_key_when_omitted(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_ai_settings(db_path, api_key="persist-me", model_name="gpt-4o-mini")

    response = client.put(
        "/api/ai/settings",
        headers=_auth_headers(),
        json={
            "provider_type": "openai",
            "base_url": "https://api.example.test/v2",
            "model_name": "gpt-4.1-mini",
            "system_prompt": "updated prompt",
            "max_tokens": 512,
            "enabled": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["api_key"] == "****"
    row = _fetch_one(
        db_path,
        "SELECT api_key, model_name, base_url FROM ai_settings WHERE id = 1",
        (),
    )
    assert row is not None
    assert dict(row) == {
        "api_key": "persist-me",
        "model_name": "gpt-4.1-mini",
        "base_url": "https://api.example.test/v2",
    }


def test_missing_resources_return_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    cases = [
        (
            "PUT",
            "/api/replies/keywords/999",
            {"pattern": "x", "reply_content": "y", "is_regex": False, "enabled": True},
        ),
        ("DELETE", "/api/replies/keywords/999", None),
        ("PUT", "/api/replies/default/999", {"content": "fallback", "enabled": True}),
        ("DELETE", "/api/replies/default/999", None),
        (
            "PUT",
            "/api/replies/item-replies/999",
            {"item_id": "item-1", "reply_content": "reply", "enabled": True},
        ),
        ("DELETE", "/api/replies/item-replies/999", None),
        ("GET", "/api/ai/settings", None),
    ]

    for method, path, payload in cases:
        response = client.request(method, path, headers=_auth_headers(), json=payload)
        assert response.status_code == 404
