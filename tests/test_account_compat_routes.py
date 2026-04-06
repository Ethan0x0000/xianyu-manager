from __future__ import annotations

import os
import time
from typing import cast
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from app.db.connection import get_db
from app.services.login_service import LoginService
from app.shared.types import ServiceKey
from tests.helpers import make_settings, make_test_db


class TestAccountCompatibilityRoutes(TestCase):
    def setUp(self) -> None:
        self.db_path = make_test_db()
        self._store = SessionStore()
        _ = self._store.create_session("compat-token", ttl_seconds=60)
        self._session_patch = patch(
            "app.api.dependencies.get_session_store",
            return_value=self._store,
        )
        self._session_patch.start()

        self.app = create_app(settings=make_settings(db_path=self.db_path))
        self.client = TestClient(self.app)
        self.login_service = cast(
            LoginService,
            self.app.state.container[ServiceKey.LOGIN_SERVICE.value],
        )

    def tearDown(self) -> None:
        self._session_patch.stop()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @staticmethod
    def _auth_headers() -> dict[str, str]:
        return {"Authorization": "Bearer compat-token"}

    def _insert_account(
        self,
        account_id: str = "seller-1",
        cookie_str: str = "cookie=value",
        username: str = "seller-user",
        password: str = "seller-pass",
        notes: str = "primary seller",
        enabled: bool = True,
        show_browser: bool = False,
        pause_duration: int = 10,
    ) -> None:
        with get_db(self.db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO xianyu_accounts (
                    account_id, cookie_str, username, password, notes, enabled, show_browser, pause_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    cookie_str,
                    username,
                    password,
                    notes,
                    int(enabled),
                    int(show_browser),
                    pause_duration,
                ),
            )

    def test_new_compatibility_endpoints_require_admin_token(self) -> None:
        self._insert_account()
        cases = [
            ("POST", "/api/qr-login/generate", {}),
            ("GET", "/api/qr-login/check/session-1", None),
            (
                "POST",
                "/api/password-login",
                {
                    "account_id": "seller-1",
                    "account": "seller-user",
                    "password": "seller-pass",
                },
            ),
            ("GET", "/api/password-login/check/session-1", None),
            ("GET", "/api/cookies/details", None),
            ("GET", "/api/cookie/seller-1/details", None),
            ("PUT", "/api/cookies/seller-1/status", {"enabled": False}),
            ("PUT", "/api/cookies/seller-1/remark", {"remark": "updated"}),
            ("PUT", "/api/cookies/seller-1/pause-duration", {"pause_duration": 0}),
            (
                "POST",
                "/api/qr-login/refresh-cookies",
                {"cookie_id": "seller-1", "qr_cookies": "unb=1; cookie2=2"},
            ),
        ]

        for method, path, payload in cases:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, json=payload)
                self.assertEqual(401, response.status_code)

    def test_qr_login_generate_and_check_return_pending_expired_and_success_states(
        self,
    ) -> None:
        response = self.client.post(
            "/api/qr-login/generate",
            headers=self._auth_headers(),
            json={},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertIn("session_id", payload)
        self.assertIn("qr_code_url", payload)

        session_id = payload["session_id"]
        status_response = self.client.get(
            f"/api/qr-login/check/{session_id}",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, status_response.status_code)
        self.assertEqual("pending", status_response.json()["status"])

        session = self.login_service.get_session(session_id)
        self.assertIsNotNone(session)
        assert session is not None
        session.expires_at = time.time() - 1

        expired_response = self.client.get(
            f"/api/qr-login/check/{session_id}",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, expired_response.status_code)
        self.assertEqual("expired", expired_response.json()["status"])

        session.expires_at = time.time() + 60
        session.status = "success"
        session.result_cookie = "unb=1; cookie2=2"
        success_response = self.client.get(
            f"/api/qr-login/check/{session_id}",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, success_response.status_code)
        self.assertEqual("success", success_response.json()["status"])
        self.assertEqual("unb=1; cookie2=2", success_response.json()["result_cookie"])

    def test_password_login_start_and_check_return_processing_and_success(self) -> None:
        self._insert_account(cookie_str="")

        response = self.client.post(
            "/api/password-login",
            headers=self._auth_headers(),
            json={
                "account_id": "seller-1",
                "account": "seller-user",
                "password": "seller-pass",
                "show_browser": True,
            },
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual("processing", payload["status"])
        session_id = payload["session_id"]

        processing_response = self.client.get(
            f"/api/password-login/check/{session_id}",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, processing_response.status_code)
        self.assertEqual("processing", processing_response.json()["status"])

        session = self.login_service.get_password_session(session_id)
        self.assertIsNotNone(session)
        assert session is not None
        session.status = "success"
        session.result_cookie = "unb=1; cookie2=2"

        success_response = self.client.get(
            f"/api/password-login/check/{session_id}",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, success_response.status_code)
        self.assertEqual("success", success_response.json()["status"])

        detail_response = self.client.get(
            "/api/cookie/seller-1/details?include_secrets=true",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, detail_response.status_code)
        self.assertEqual("unb=1; cookie2=2", detail_response.json()["value"])
        self.assertEqual("available", detail_response.json()["cookie_status"])

    def test_password_login_rejects_unknown_account_and_missing_credentials(
        self,
    ) -> None:
        missing_response = self.client.post(
            "/api/password-login",
            headers=self._auth_headers(),
            json={
                "account_id": "missing-account",
                "account": "seller-user",
                "password": "seller-pass",
            },
        )
        self.assertEqual(404, missing_response.status_code)

        self._insert_account(
            account_id="seller-2",
            cookie_str="",
            username="",
            password="",
        )
        validation_response = self.client.post(
            "/api/password-login",
            headers=self._auth_headers(),
            json={"account_id": "seller-2", "refresh_mode": True},
        )
        self.assertEqual(422, validation_response.status_code)
        self.assertIn("stored username/password", validation_response.json()["detail"])

    def test_account_detail_and_mutation_routes_persist_updates(self) -> None:
        self._insert_account(notes="original remark", pause_duration=10)

        list_response = self.client.get(
            "/api/cookies/details",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, list_response.status_code)
        self.assertEqual(1, len(list_response.json()))
        account = list_response.json()[0]
        self.assertEqual("seller-1", account["id"])
        self.assertEqual("available", account["cookie_status"])
        self.assertTrue(account["has_password"])
        self.assertEqual("original remark", account["remark"])
        self.assertEqual(10, account["pause_duration"])

        status_response = self.client.put(
            "/api/cookies/seller-1/status",
            headers=self._auth_headers(),
            json={"enabled": False},
        )
        self.assertEqual(200, status_response.status_code)
        self.assertFalse(status_response.json()["enabled"])

        remark_response = self.client.put(
            "/api/cookies/seller-1/remark",
            headers=self._auth_headers(),
            json={"remark": "updated remark"},
        )
        self.assertEqual(200, remark_response.status_code)
        self.assertEqual("updated remark", remark_response.json()["remark"])

        pause_response = self.client.put(
            "/api/cookies/seller-1/pause-duration",
            headers=self._auth_headers(),
            json={"pause_duration": 0},
        )
        self.assertEqual(200, pause_response.status_code)
        self.assertEqual(0, pause_response.json()["pause_duration"])

        detail_response = self.client.get(
            "/api/cookie/seller-1/details?include_secrets=true",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, detail_response.status_code)
        detail_payload = detail_response.json()
        self.assertFalse(detail_payload["enabled"])
        self.assertEqual("updated remark", detail_payload["remark"])
        self.assertEqual(0, detail_payload["pause_duration"])

    def test_account_mutations_handle_not_found_and_validation_errors(self) -> None:
        status_response = self.client.put(
            "/api/cookies/missing-account/status",
            headers=self._auth_headers(),
            json={"enabled": False},
        )
        self.assertEqual(404, status_response.status_code)

        remark_response = self.client.put(
            "/api/cookies/missing-account/remark",
            headers=self._auth_headers(),
            json={"remark": "updated"},
        )
        self.assertEqual(404, remark_response.status_code)

        self._insert_account(cookie_str="")
        pause_response = self.client.put(
            "/api/cookies/seller-1/pause-duration",
            headers=self._auth_headers(),
            json={"pause_duration": 61},
        )
        self.assertEqual(422, pause_response.status_code)

    def test_refresh_cookie_flow_updates_account_cookie(self) -> None:
        self._insert_account(cookie_str="old=cookie")

        with patch(
            "app.api.routers.account_compat.refresh_token",
            new=AsyncMock(return_value=("token-1", {"unb": "1", "cookie2": "2"})),
        ) as refresh_mock:
            response = self.client.post(
                "/api/qr-login/refresh-cookies",
                headers=self._auth_headers(),
                json={"cookie_id": "seller-1", "qr_cookies": "old=cookie"},
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual("seller-1", payload["cookie_id"])
        self.assertEqual("available", payload["cookie_status"])
        refresh_mock.assert_awaited_once_with("old=cookie")

        detail_response = self.client.get(
            "/api/cookie/seller-1/details?include_secrets=true",
            headers=self._auth_headers(),
        )
        self.assertEqual(200, detail_response.status_code)
        self.assertEqual("unb=1; cookie2=2", detail_response.json()["value"])
