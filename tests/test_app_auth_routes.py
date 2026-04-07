import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.dependencies import get_runtime_settings
from app.auth.sessions import SessionStore
from app.api.routers.auth import _get_client_ip
from app.bootstrap.app_factory import create_app
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class AppAuthRouteTests(unittest.TestCase):
    @staticmethod
    def _make_client(settings=None) -> TestClient:
        effective_settings = settings or make_settings()
        app = create_app(settings=effective_settings)
        return TestClient(app)

    def test_login_html_alias_served_by_spa_fallback(self) -> None:
        client = self._make_client()

        response = client.get("/login.html", follow_redirects=False)

        # The SPA mount serves index.html for unknown paths (200)
        # or falls through to 404 when index.html hasn't been built yet.
        self.assertIn(response.status_code, (200, 404))

    def test_root_uses_bundled_frontend_when_runtime_dist_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            temp_path = Path(temp_dir)
            missing_dist = temp_path / "missing-dist"
            bundled_dist = temp_path / "bundled-dist"
            bundled_dist.mkdir(parents=True, exist_ok=True)
            _ = (bundled_dist / "index.html").write_text(
                "<html><body>bundled frontend</body></html>",
                encoding="utf-8",
            )

            app = create_app(
                settings=make_settings(
                    frontend_dist_dir=str(missing_dist),
                    frontend_bundled_dist_dir=str(bundled_dist),
                )
            )
            client = TestClient(app)

            response = client.get("/", follow_redirects=False)

        self.assertEqual(200, response.status_code)
        self.assertIn("bundled frontend", response.text)

    def test_login_info_status_enabled_for_default_admin_credentials(self) -> None:
        settings = make_settings(
            admin_username="admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )
        client = self._make_client(settings)

        response = client.get("/login-info-status")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"enabled": True}, response.json())

    def test_login_info_status_disabled_for_custom_admin_credentials(self) -> None:
        settings = make_settings(
            admin_username="custom-admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )
        client = self._make_client(settings)

        response = client.get("/login-info-status")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"enabled": False}, response.json())

    def test_legacy_verify_route_returns_authenticated_state_for_valid_session(
        self,
    ) -> None:
        settings = make_settings(admin_username="admin")
        client = self._make_client(settings)
        store = SessionStore()
        _ = store.create_session("legacy-token", ttl_seconds=60)

        with (
            patch("app.api.dependencies.get_session_store", return_value=store),
        ):
            response = client.get(
                "/verify",
                headers={"Authorization": "Bearer legacy-token"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "authenticated": True,
                "is_admin": True,
                "username": "admin",
            },
            response.json(),
        )

    def test_legacy_logout_route_revokes_session(self) -> None:
        client = self._make_client()
        store = SessionStore()
        _ = store.create_session("legacy-token", ttl_seconds=60)

        with (
            patch("app.api.dependencies.get_session_store", return_value=store),
            patch("app.api.routers.auth.get_session_store", return_value=store),
        ):
            response = client.post(
                "/logout",
                headers={"Authorization": "Bearer legacy-token"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"success": True}, response.json())
        self.assertFalse(store.validate_session("legacy-token"))

    def test_login_sets_http_only_cookie_and_verify_accepts_cookie(self) -> None:
        settings = make_settings(
            admin_username="admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )
        client = self._make_client(settings)

        login_response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )

        self.assertEqual(200, login_response.status_code)
        self.assertEqual({"token": ""}, login_response.json())
        set_cookie_header = login_response.headers.get("set-cookie", "")
        self.assertIn("HttpOnly", set_cookie_header)
        self.assertIn("SameSite=lax", set_cookie_header)

        verify_response = client.get("/api/auth/verify")

        self.assertEqual(200, verify_response.status_code)
        self.assertEqual("admin", verify_response.json()["username"])

    def test_create_app_validates_required_settings(self) -> None:
        with self.assertRaises(ValueError):
            _ = create_app(
                settings=make_settings(
                    secret_key="",
                    secret_encryption_key="",
                )
            )

    def test_options_preflight_includes_cors_headers_for_allowed_origin(self) -> None:
        client = self._make_client()

        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            "http://localhost:5173",
            response.headers.get("access-control-allow-origin"),
        )
        self.assertEqual(
            "true",
            response.headers.get("access-control-allow-credentials"),
        )

    def test_get_client_ip_ignores_forwarded_header_from_untrusted_peer(self) -> None:
        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/auth/login",
                "raw_path": b"/api/auth/login",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"1.2.3.4")],
                "client": ("203.0.113.5", 3210),
                "server": ("testserver", 80),
            }
        )

        self.assertEqual("203.0.113.5", _get_client_ip(request))

    def test_get_client_ip_accepts_forwarded_header_from_trusted_proxy(self) -> None:
        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/auth/login",
                "raw_path": b"/api/auth/login",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"198.51.100.8")],
                "client": ("127.0.0.1", 3210),
                "server": ("testserver", 80),
            }
        )

        self.assertEqual("198.51.100.8", _get_client_ip(request))
