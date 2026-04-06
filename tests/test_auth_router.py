import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.auth import router
from app.auth.sessions import SessionStore
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class AuthRouterTests(unittest.TestCase):
    @staticmethod
    def _make_client() -> TestClient:
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_login_returns_token_for_default_admin_credentials(self) -> None:
        client = self._make_client()
        store = SessionStore()
        settings = make_settings(
            admin_username="admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )

        with (
            patch("app.api.routers.auth.load_settings", return_value=settings),
            patch("app.api.routers.auth.get_session_store", return_value=store),
        ):
            response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin123"},
            )

        self.assertEqual(200, response.status_code)
        self.assertIn("token", response.json())

    def test_verify_returns_authenticated_state_for_valid_session(self) -> None:
        client = self._make_client()
        store = SessionStore()
        _ = store.create_session("token-1", ttl_seconds=60)
        settings = make_settings(admin_username="admin")

        with (
            patch("app.api.dependencies.get_session_store", return_value=store),
            patch("app.api.routers.auth.load_settings", return_value=settings),
        ):
            response = client.get(
                "/api/auth/verify",
                headers={"Authorization": "Bearer token-1"},
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
