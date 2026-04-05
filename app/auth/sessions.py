"""In-memory session store for single-admin authentication.

Manages opaque session tokens with expiration. Sessions are stored in-memory
and are not persisted to the database. This is suitable for a single-admin
model where sessions are short-lived and the admin is typically the only user.

Thread-safe using a simple lock-based approach.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class SessionEntry:
    """A single session entry in the session store.

    Attributes:
        token: The opaque session token (hex string)
        created_at: Unix timestamp when the session was created
        expires_at: Unix timestamp when the session expires
    """

    token: str
    created_at: float
    expires_at: float

    def is_expired(self) -> bool:
        """Check if this session has expired.

        Returns:
            True if the current time is past expires_at, False otherwise
        """
        return time.time() > self.expires_at


class SessionStore:
    """In-memory session store with expiration and thread-safety.

    Stores active sessions in a dict keyed by token. Sessions expire after
    a configurable TTL. Provides methods to create, validate, and revoke sessions.

    Thread-safe using a threading.Lock for all operations.
    """

    def __init__(self) -> None:
        """Initialize an empty session store."""
        self._sessions: dict[str, SessionEntry] = {}
        self._lock: threading.Lock = threading.Lock()

    def create_session(self, token: str, ttl_seconds: int = 86400) -> SessionEntry:
        """Create a new session with the given token.

        Args:
            token: The opaque session token (typically from create_session_token())
            ttl_seconds: Time-to-live in seconds (default: 24 hours)

        Returns:
            The created SessionEntry

        Raises:
            ValueError: If the token already exists in the store
        """
        with self._lock:
            if token in self._sessions:
                raise ValueError(f"Session token already exists: {token}")

            now = time.time()
            entry = SessionEntry(
                token=token, created_at=now, expires_at=now + ttl_seconds
            )
            self._sessions[token] = entry
            return entry

    def validate_session(self, token: str) -> bool:
        """Validate that a session token is active and not expired.

        Args:
            token: The session token to validate

        Returns:
            True if the token exists and is not expired, False otherwise
        """
        with self._lock:
            if token not in self._sessions:
                return False

            entry = self._sessions[token]
            if entry.is_expired():
                # Clean up expired session
                del self._sessions[token]
                return False

            return True

    def revoke_session(self, token: str) -> None:
        """Revoke (delete) a session token.

        Args:
            token: The session token to revoke

        Note:
            Does not raise an error if the token doesn't exist.
        """
        with self._lock:
            self._sessions.pop(token, None)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions from the store.

        Returns:
            The number of sessions that were cleaned up

        Note:
            This is a maintenance operation that can be called periodically
            to prevent unbounded memory growth. In practice, validate_session()
            also cleans up expired sessions on access.
        """
        with self._lock:
            expired_tokens = [
                token for token, entry in self._sessions.items() if entry.is_expired()
            ]
            for token in expired_tokens:
                del self._sessions[token]
            return len(expired_tokens)

    def get_session(self, token: str) -> SessionEntry | None:
        """Get a session entry by token (for debugging/inspection only).

        Args:
            token: The session token to retrieve

        Returns:
            The SessionEntry if found and not expired, None otherwise

        Note:
            This is primarily for testing and debugging. Normal auth flow
            should use validate_session() instead.
        """
        with self._lock:
            if token not in self._sessions:
                return None

            entry = self._sessions[token]
            if entry.is_expired():
                del self._sessions[token]
                return None

            return entry

    def session_count(self) -> int:
        """Get the current number of active (non-expired) sessions.

        Returns:
            The count of sessions in the store (including expired ones)

        Note:
            This count includes expired sessions that haven't been cleaned up yet.
            Call cleanup_expired() first for an accurate count of valid sessions.
        """
        with self._lock:
            return len(self._sessions)


# Global singleton instance
_session_store: SessionStore | None = None
_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    """Get the global session store singleton.

    Returns:
        The global SessionStore instance, creating it if necessary

    Note:
        This is thread-safe and uses double-checked locking.
    """
    global _session_store
    if _session_store is None:
        with _store_lock:
            if _session_store is None:
                _session_store = SessionStore()
    return _session_store
