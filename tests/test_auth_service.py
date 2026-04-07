import unittest

import bcrypt

from app.auth.service import create_session_token, verify_admin_login
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class VerifyAdminLoginTests(unittest.TestCase):
    def test_returns_true_for_matching_bcrypt_password_hash(self) -> None:
        settings = make_settings(admin_password_hash=VALID_BCRYPT_HASH)

        result = verify_admin_login("testadmin", "admin123", settings)

        self.assertTrue(result)

    def test_returns_true_for_dynamically_hashed_password(self) -> None:
        password = "my-secure-password"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        settings = make_settings(admin_password_hash=hashed)

        result = verify_admin_login("testadmin", password, settings)

        self.assertTrue(result)

    def test_returns_false_for_plaintext_hash_no_fallback(self) -> None:
        """Plaintext fallback was removed — unrecognised formats must be rejected."""
        settings = make_settings(admin_password_hash="expected-password")

        result = verify_admin_login("testadmin", "expected-password", settings)

        self.assertFalse(result)

    def test_returns_false_when_admin_username_is_empty(self) -> None:
        settings = make_settings(
            admin_username="", admin_password_hash=VALID_BCRYPT_HASH
        )

        result = verify_admin_login("testadmin", "admin123", settings)

        self.assertFalse(result)

    def test_returns_false_when_admin_password_hash_is_empty(self) -> None:
        settings = make_settings(admin_password_hash="")

        result = verify_admin_login("testadmin", "any-password", settings)

        self.assertFalse(result)

    def test_returns_false_for_wrong_username(self) -> None:
        settings = make_settings(admin_password_hash=VALID_BCRYPT_HASH)

        result = verify_admin_login("wrong-user", "admin123", settings)

        self.assertFalse(result)

    def test_returns_false_for_wrong_password(self) -> None:
        settings = make_settings(admin_password_hash=VALID_BCRYPT_HASH)

        result = verify_admin_login("testadmin", "wrong-password", settings)

        self.assertFalse(result)


class CreateSessionTokenTests(unittest.TestCase):
    def test_returns_64_character_hex_string(self) -> None:
        token = create_session_token("unused-secret")

        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertEqual(64, len(token))

    def test_returns_different_tokens_on_successive_calls(self) -> None:
        first_token = create_session_token("unused-secret")
        second_token = create_session_token("unused-secret")

        self.assertNotEqual(first_token, second_token)
