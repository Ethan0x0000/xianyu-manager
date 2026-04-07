import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_runtime_settings
from app.api.routers.auth import router
from app.auth.sessions import SessionStore
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class AuthRouterTests(unittest.TestCase):
    @staticmethod
    def _make_client(settings=None) -> TestClient:
        app = FastAPI()
        if settings is not None:
            app.state.settings = settings
            app.dependency_overrides[get_runtime_settings] = lambda: settings
        app.include_router(router)
        return TestClient(app)

    def test_login_returns_token_for_default_admin_credentials(self) -> None:
        store = SessionStore()
        settings = make_settings(
            admin_username="admin",
            admin_password_hash=VALID_BCRYPT_HASH,
        )
        client = self._make_client(settings)

        with (
            patch("app.api.routers.auth.get_session_store", return_value=store),
        ):
            response = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin123"},
            )

        self.assertEqual(200, response.status_code)
        self.assertIn("token", response.json())

    def test_verify_returns_authenticated_state_for_valid_session(self) -> None:
        store = SessionStore()
        _ = store.create_session("token-1", ttl_seconds=60)
        settings = make_settings(admin_username="admin")
        client = self._make_client(settings)

        with (
            patch("app.api.dependencies.get_session_store", return_value=store),
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
