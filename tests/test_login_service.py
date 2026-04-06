import time
import unittest
import uuid

from app.services.login_service import (
    LoginService,
    LoginValidationError,
    QRLoginSession,
)


class TestLoginServiceSync(unittest.TestCase):
    def test_create_qr_session_returns_session_with_valid_fields(self) -> None:
        service = LoginService()
        session = service.create_qr_session()

        self.assertIsInstance(uuid.UUID(session.session_id), uuid.UUID)
        self.assertEqual(
            session.qr_code_url,
            f"https://oauth.m.taobao.com/login/qr/code?sessionId={session.session_id}",
        )
        self.assertEqual(session.qr_image_data, "")
        self.assertEqual(session.status, "pending")
        self.assertEqual(session.result_cookie, "")
        self.assertLess(session.created_at, session.expires_at)
        self.assertIs(service.get_session(session.session_id), session)

    def test_get_session_returns_session_or_none_for_unknown_id(self) -> None:
        service = LoginService()
        session = service.create_qr_session()

        self.assertIs(service.get_session(session.session_id), session)
        self.assertIsNone(service.get_session("missing-session"))

    def test_invalidate_session_marks_session_as_expired(self) -> None:
        service = LoginService()
        session = service.create_qr_session()

        service.invalidate_session(session.session_id)

        self.assertEqual(session.status, "expired")

    def test_active_session_count_counts_only_non_expired_sessions(self) -> None:
        service = LoginService()
        active_session = service.create_qr_session()
        expired_session = service.create_qr_session()
        expired_session.expires_at = time.time() - 1

        self.assertEqual(service.active_session_count(), 1)
        self.assertFalse(active_session.is_expired)
        self.assertTrue(expired_session.is_expired)

    def test_qr_login_session_is_expired_returns_true_after_expiry(self) -> None:
        session = QRLoginSession(session_id="session-1", expires_at=time.time() - 1)

        self.assertTrue(session.is_expired)


class TestLoginServiceAsync(unittest.IsolatedAsyncioTestCase):
    async def test_initiate_password_login_raises_for_missing_fields(self) -> None:
        service = LoginService()
        invalid_cases = [
            ("account-1", "", "password", "username and password are required"),
            ("account-1", "username", "", "username and password are required"),
            ("", "username", "password", "account_id is required"),
        ]

        for account_id, username, password, message in invalid_cases:
            with self.subTest(
                account_id=account_id,
                username=username,
                password=password,
            ):
                with self.assertRaisesRegex(LoginValidationError, message):
                    _ = await service.initiate_password_login(
                        account_id, username, password
                    )

    async def test_initiate_password_login_returns_pending_for_valid_input(
        self,
    ) -> None:
        service = LoginService()

        result = await service.initiate_password_login(
            account_id="account-1",
            username="seller-user",
            password="seller-pass",
        )

        self.assertEqual(result, {"status": "pending", "message": "login_initiated"})


if __name__ == "__main__":
    _ = unittest.main()
