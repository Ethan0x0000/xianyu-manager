"""Message deduplication store.

Prevents the same message from being processed multiple times within a TTL window.
Preserves existing deduplication semantics from XianyuAutoAsync.py.
"""

from __future__ import annotations

import threading
import time
from _thread import LockType
from typing import ClassVar

__all__ = ["MessageDeduplicator"]


class MessageDeduplicator:
    """
    In-memory deduplication store for Goofish messages.

    Uses a sliding window with TTL eviction. Thread-safe.

    FROZEN: TTL and max size preserve original behavior from XianyuAutoAsync.py.
    """

    DEFAULT_TTL: ClassVar[float] = 300  # 5 minutes
    DEFAULT_MAX_SIZE: ClassVar[int] = 1000

    def __init__(
        self, ttl: float = DEFAULT_TTL, max_size: int = DEFAULT_MAX_SIZE
    ) -> None:
        self._seen: dict[str, float] = {}
        self._ttl: float = ttl
        self._max_size: int = max_size
        self._lock: LockType = threading.Lock()

    def is_duplicate(self, message_id: str) -> bool:
        """Return True if this message was already seen within TTL."""
        if not message_id:
            return False

        with self._lock:
            now = time.time()
            self._evict_expired(now)
            if message_id in self._seen:
                return True

            if len(self._seen) >= self._max_size:
                oldest = min(self._seen.items(), key=lambda item: item[1])[0]
                del self._seen[oldest]

            self._seen[message_id] = now
            return False

    def _evict_expired(self, now: float) -> None:
        expired = [
            message_id
            for message_id, seen_at in self._seen.items()
            if now - seen_at > self._ttl
        ]
        for message_id in expired:
            del self._seen[message_id]

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()
