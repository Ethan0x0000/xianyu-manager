import unittest
from unittest.mock import patch

import app.auth.sessions as auth_sessions_module
from app.auth.sessions import SessionEntry, SessionStore, get_session_store


class SessionStoreTests(unittest.TestCase):
    def test_create_session_adds_entry_and_validate_session_returns_true(self) -> None:
        store = SessionStore()
        entry = store.create_session("token-1", ttl_seconds=60)

        self.assertEqual("token-1", entry.token)
        self.assertIs(store.get_session("token-1"), entry)
        self.assertTrue(store.validate_session("token-1"))

    def test_validate_session_returns_false_for_unknown_token(self) -> None:
        store = SessionStore()

        self.assertFalse(store.validate_session("missing-token"))

    def test_revoke_session_makes_validate_session_return_false(self) -> None:
        store = SessionStore()
        _ = store.create_session("token-2", ttl_seconds=60)

        store.revoke_session("token-2")

        self.assertFalse(store.validate_session("token-2"))

    def test_cleanup_expired_removes_expired_entries(self) -> None:
        store = SessionStore()

        with patch(
            "app.auth.sessions.time.time",
            side_effect=[100.0, 101.0, 107.0, 107.0, 107.0],
        ):
            _ = store.create_session("expired-token", ttl_seconds=5)
            _ = store.create_session("active-token", ttl_seconds=10)

            cleaned = store.cleanup_expired()

            self.assertEqual(1, cleaned)
            self.assertIsNone(store.get_session("expired-token"))
            self.assertIsNotNone(store.get_session("active-token"))

    def test_session_count_returns_correct_count(self) -> None:
        store = SessionStore()
        _ = store.create_session("token-a", ttl_seconds=60)
        _ = store.create_session("token-b", ttl_seconds=60)

        self.assertEqual(2, store.session_count())

    def test_duplicate_session_token_raises_value_error(self) -> None:
        store = SessionStore()
        _ = store.create_session("duplicate-token", ttl_seconds=60)

        with self.assertRaises(ValueError):
            _ = store.create_session("duplicate-token", ttl_seconds=60)


class SessionEntryTests(unittest.TestCase):
    def test_is_expired_returns_true_after_ttl(self) -> None:
        entry = SessionEntry(token="token-3", created_at=100.0, expires_at=105.0)

        with patch("app.auth.sessions.time.time", return_value=106.0):
            self.assertTrue(entry.is_expired())


class SessionStoreSingletonTests(unittest.TestCase):
    def test_get_session_store_returns_same_instance(self) -> None:
        with patch.object(auth_sessions_module, "_session_store", None):
            first_store = get_session_store()
            second_store = get_session_store()

        self.assertIs(first_store, second_store)
