from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import Response

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from app.db.connection import get_db
from tests.helpers import make_settings, make_test_db

AUTH_TOKEN = "admin-compat-token"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def _json_dict(response: Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


def _insert_setting(db_path: str, key: str, value: str) -> None:
    with get_db(db_path) as conn:
        _ = conn.execute(
            "INSERT INTO system_settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def _insert_risk_log(
    db_path: str,
    account_id: str = "seller-1",
    event_type: str = "slider_captcha",
    details: str = '{"status":"pending"}',
) -> None:
    with get_db(db_path) as conn:
        _ = conn.execute(
            "INSERT INTO risk_logs (account_id, event_type, details) VALUES (?, ?, ?)",
            (account_id, event_type, details),
        )


@contextmanager
def _auth_client() -> Iterator[tuple[TestClient, str]]:
    db_path = make_test_db()
    store = SessionStore()
    _ = store.create_session(AUTH_TOKEN, ttl_seconds=60)
    with patch("app.api.dependencies.get_session_store", return_value=store):
        with TestClient(create_app(settings=make_settings(db_path=db_path))) as client:
            try:
                yield client, db_path
            finally:
                if os.path.exists(db_path):
                    os.unlink(db_path)


def test_settings_round_trip_and_delete() -> None:
    with _auth_client() as (client, _):
        create_response = client.post(
            "/api/settings",
            headers=_auth_headers(),
            json={"key": "theme_color", "value": "#4f46e5"},
        )

        assert create_response.status_code == 200

        get_response = client.get("/api/settings", headers=_auth_headers())

        assert get_response.status_code == 200
        settings_payload = cast(dict[str, object], _json_dict(get_response)["settings"])
        assert settings_payload["theme_color"] == "#4f46e5"

        delete_response = client.delete(
            "/api/settings/theme_color",
            headers=_auth_headers(),
        )

        assert delete_response.status_code == 204

        after_delete_response = client.get("/api/settings", headers=_auth_headers())

        deleted_settings_payload = cast(
            dict[str, object], _json_dict(after_delete_response)["settings"]
        )
        assert "theme_color" not in deleted_settings_payload


def test_menu_settings_save_and_load() -> None:
    payload = {
        "menu": [
            {"key": "dashboard", "label": "仪表盘", "visible": True, "order": 1},
            {"key": "orders", "label": "订单管理", "visible": False, "order": 2},
        ]
    }

    with _auth_client() as (client, _):
        save_response = client.post(
            "/api/settings/menu",
            headers=_auth_headers(),
            json=payload,
        )

        assert save_response.status_code == 200

        get_response = client.get("/api/settings/menu", headers=_auth_headers())

        assert get_response.status_code == 200
        assert _json_dict(get_response)["menu"] == payload["menu"]


def test_theme_and_login_info_settings_round_trip() -> None:
    with _auth_client() as (client, _):
        theme_response = client.post(
            "/api/settings/theme",
            headers=_auth_headers(),
            json={"color": "#112233"},
        )

        assert theme_response.status_code == 200

        invalid_theme_response = client.post(
            "/api/settings/theme",
            headers=_auth_headers(),
            json={"color": "blue"},
        )

        assert invalid_theme_response.status_code == 422

        initial_login_info = client.get("/api/settings/login-info")

        assert initial_login_info.status_code == 200
        assert "default_password" not in _json_dict(initial_login_info)

        enable_response = client.post(
            "/api/settings/login-info",
            headers=_auth_headers(),
            json={"show_default_credentials": True},
        )

        assert enable_response.status_code == 200

        enabled_login_info = client.get("/api/settings/login-info")
        enabled_payload = _json_dict(enabled_login_info)

        assert enabled_payload["show_default_credentials"] is True
        assert enabled_payload["default_username"] == "testadmin"
        assert "default_password" not in enabled_payload

        disable_response = client.post(
            "/api/settings/login-info",
            headers=_auth_headers(),
            json={"show_default_credentials": False},
        )

        assert disable_response.status_code == 200
        assert (
            _json_dict(client.get("/api/settings/login-info"))[
                "show_default_credentials"
            ]
            is False
        )


def test_change_admin_password_validates_input() -> None:
    with _auth_client() as (client, _):
        invalid_response = client.post(
            "/api/admin/password",
            headers=_auth_headers(),
            json={"new_password": ""},
        )

        assert invalid_response.status_code == 422

        valid_response = client.post(
            "/api/admin/password",
            headers=_auth_headers(),
            json={"new_password": "new-secret-password"},
        )

        assert valid_response.status_code == 200
        assert "admin_password_hash" not in _json_dict(valid_response)


def test_log_listing_and_export_return_recent_lines() -> None:
    marker = "admin compat log marker"
    logger = logging.getLogger("tests.test_admin_compat")
    logger.warning(marker)

    with _auth_client() as (client, _):
        list_response = client.get(
            "/api/logs",
            headers=_auth_headers(),
            params={"limit": 20},
        )

        assert list_response.status_code == 200
        logs = cast(list[str], _json_dict(list_response)["logs"])
        assert isinstance(logs, list)
        assert any(marker in line for line in logs)

        export_response = client.get("/api/logs/export", headers=_auth_headers())

        assert export_response.status_code == 200
        assert marker in export_response.text


def test_risk_log_listing_and_clear() -> None:
    with _auth_client() as (client, db_path):
        _insert_risk_log(db_path, account_id="seller-1", event_type="slider_captcha")
        _insert_risk_log(db_path, account_id="seller-2", event_type="token_expired")

        list_response = client.get(
            "/api/risk-logs",
            headers=_auth_headers(),
            params={"account_id": "seller-1", "page": 1, "page_size": 20},
        )

        assert list_response.status_code == 200
        payload = _json_dict(list_response)
        assert payload["total"] == 1
        assert len(cast(list[dict[str, object]], payload["logs"])) == 1

        clear_response = client.delete("/api/risk-logs", headers=_auth_headers())

        assert clear_response.status_code == 200
        assert _json_dict(clear_response)["deleted"] == 2


def test_data_table_browser_lists_tables_and_rows() -> None:
    with _auth_client() as (client, db_path):
        _insert_setting(db_path, "feature_flag", "enabled")

        tables_response = client.get("/api/data/tables", headers=_auth_headers())

        assert tables_response.status_code == 200
        tables = cast(list[str], _json_dict(tables_response)["tables"])
        assert "system_settings" in tables
        assert "risk_logs" in tables

        rows_response = client.get(
            "/api/data/table/system_settings",
            headers=_auth_headers(),
            params={"page": 1, "page_size": 20},
        )

        assert rows_response.status_code == 200
        rows_payload = _json_dict(rows_response)
        assert cast(int, rows_payload["total"]) >= 1
        assert any(
            row["key"] == "feature_flag"
            for row in cast(list[dict[str, object]], rows_payload["rows"])
        )


def test_backup_export_returns_file_or_stub() -> None:
    with _auth_client() as (client, _):
        response = client.get("/api/backup/export", headers=_auth_headers())

        assert response.status_code in {200, 501}
        if response.status_code == 200:
            assert "attachment" in response.headers.get("content-disposition", "")


def test_invalid_backup_file_is_rejected() -> None:
    with _auth_client() as (client, _):
        response = client.post(
            "/api/backup/import",
            headers=_auth_headers(),
            files={"file": ("backup.txt", b"not-a-sqlite-file", "text/plain")},
        )

        assert response.status_code == 422


def test_captcha_stub_start_and_status() -> None:
    with _auth_client() as (client, _):
        start_response = client.post("/api/captcha/start", headers=_auth_headers())

        assert start_response.status_code == 200
        session_id = cast(str, _json_dict(start_response)["session_id"])
        assert session_id

        status_response = client.get(
            "/api/captcha/status",
            headers=_auth_headers(),
            params={"session_id": session_id},
        )

        assert status_response.status_code == 200
        status_payload = _json_dict(status_response)
        assert status_payload["session_id"] == session_id
        assert isinstance(status_payload["active"], bool)
