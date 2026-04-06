import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class AppAuthRouteTests(unittest.TestCase):
    @staticmethod
    def _make_client() -> TestClient:
        app = create_app(settings=make_settings())
        return TestClient(app)

    def test_login_html_alias_redirects_to_static_login_page(self) -> None:
        client = self._make_client()

        response = client.get("/login.html", follow_redirects=False)

        self.assertEqual(307, response.status_code)
        self.assertEqual("/static/login.html", response.headers["location"])

    def test_login_info_status_enabled_for_default_admin_credentials(self) -> None:
        client = self._make_client()
        settings = make_settings(
            admin_username="admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )

        with patch("app.api.routers.auth.load_settings", return_value=settings):
            response = client.get("/login-info-status")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"enabled": True}, response.json())

    def test_login_info_status_disabled_for_custom_admin_credentials(self) -> None:
        client = self._make_client()
        settings = make_settings(
            admin_username="custom-admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )

        with patch("app.api.routers.auth.load_settings", return_value=settings):
            response = client.get("/login-info-status")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"enabled": False}, response.json())

    def test_legacy_verify_route_returns_authenticated_state_for_valid_session(
        self,
    ) -> None:
        client = self._make_client()
        store = SessionStore()
        _ = store.create_session("legacy-token", ttl_seconds=60)
        settings = make_settings(admin_username="admin")

        with (
            patch("app.api.dependencies.get_session_store", return_value=store),
            patch("app.api.routers.auth.load_settings", return_value=settings),
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
