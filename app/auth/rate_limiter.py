from __future__ import annotations

"""In-memory login rate limiting utilities."""

import math
import threading
import time
from dataclasses import dataclass
from typing import Final

__all__ = ["LoginRateLimiter", "get_rate_limiter"]

IP_MAX_ATTEMPTS: Final[int] = 5
IP_WINDOW_SECONDS: Final[int] = 300
IP_BLOCK_SECONDS: Final[int] = 1800
USER_MAX_ATTEMPTS: Final[int] = 10
USER_WINDOW_SECONDS: Final[int] = 600
USER_LOCK_SECONDS: Final[int] = 3600
AUTO_BLACKLIST_THRESHOLD: Final[int] = 20
RESPONSE_DELAY_BASE: Final[float] = 1.0
RESPONSE_DELAY_MULTIPLIER: Final[float] = 0.5
MAX_RESPONSE_DELAY: Final[float] = 10.0


@dataclass(slots=True)
class IPRecord:
    """Track failed login attempts for a single IP address."""

    attempts: int = 0
    first_attempt: float = 0.0
    blocked_until: float = 0.0
    total_failures: int = 0


@dataclass(slots=True)
class UserRecord:
    """Track failed login attempts for a single username."""

    attempts: int = 0
    first_attempt: float = 0.0
    locked_until: float = 0.0


class LoginRateLimiter:
    """Thread-safe, in-memory rate limiter for login attempts."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._ip_records: dict[str, IPRecord] = {}
        self._user_records: dict[str, UserRecord] = {}
        self._blacklisted_ips: set[str] = set()

    def check_ip(self, ip: str) -> tuple[bool, str, int]:
        """Return the current block status for an IP address."""

        with self._lock:
            now = self._now()
            if ip in self._blacklisted_ips:
                return True, "This IP address is permanently blacklisted.", 0

            record = self._ip_records.get(ip)
            if record is None:
                return False, "", 0

            if record.blocked_until > now:
                remaining = self._remaining_seconds(record.blocked_until, now)
                return (
                    True,
                    "Too many failed login attempts from this IP address.",
                    remaining,
                )

            record.blocked_until = 0.0
            self._reset_ip_window_if_needed(record, now)
            return False, "", 0

    def check_user(self, username: str) -> tuple[bool, str, int]:
        """Return the current lock status for a username."""

        with self._lock:
            now = self._now()
            record = self._user_records.get(username)
            if record is None:
                return False, "", 0

            if record.locked_until > now:
                remaining = self._remaining_seconds(record.locked_until, now)
                return (
                    True,
                    "Too many failed login attempts for this account.",
                    remaining,
                )

            record.locked_until = 0.0
            self._reset_user_window_if_needed(record, now)
            return False, "", 0

    def record_failure(self, ip: str, username: str) -> None:
        """Record a failed login attempt for both IP and username."""

        with self._lock:
            now = self._now()

            ip_record = self._ip_records.get(ip)
            if ip_record is None:
                ip_record = IPRecord(first_attempt=now)
                self._ip_records[ip] = ip_record
            elif ip_record.blocked_until <= now:
                ip_record.blocked_until = 0.0
                self._reset_ip_window_if_needed(ip_record, now)

            if ip_record.first_attempt == 0.0:
                ip_record.first_attempt = now

            ip_record.attempts += 1
            ip_record.total_failures += 1

            if ip_record.total_failures >= AUTO_BLACKLIST_THRESHOLD:
                self._blacklisted_ips.add(ip)
            elif ip_record.attempts >= IP_MAX_ATTEMPTS:
                ip_record.blocked_until = now + IP_BLOCK_SECONDS

            user_record = self._user_records.get(username)
            if user_record is None:
                user_record = UserRecord(first_attempt=now)
                self._user_records[username] = user_record
            elif user_record.locked_until <= now:
                user_record.locked_until = 0.0
                self._reset_user_window_if_needed(user_record, now)

            if user_record.first_attempt == 0.0:
                user_record.first_attempt = now

            user_record.attempts += 1

            if user_record.attempts >= USER_MAX_ATTEMPTS:
                user_record.locked_until = now + USER_LOCK_SECONDS

    def record_success(self, ip: str, username: str) -> None:
        """Clear tracked failures for the given IP and username."""

        with self._lock:
            _ = self._ip_records.pop(ip, None)
            _ = self._user_records.pop(username, None)

    def get_response_delay(self, ip: str) -> float:
        """Return the response delay for the given IP address."""

        with self._lock:
            if ip in self._blacklisted_ips:
                return MAX_RESPONSE_DELAY

            now = self._now()
            record = self._ip_records.get(ip)
            if record is None:
                return 0.0

            if record.blocked_until <= now:
                record.blocked_until = 0.0
                self._reset_ip_window_if_needed(record, now)

            if record.attempts <= 0:
                return 0.0

            delay = (
                RESPONSE_DELAY_BASE
                + max(0, record.attempts - 1) * RESPONSE_DELAY_MULTIPLIER
            )
            return min(MAX_RESPONSE_DELAY, delay)

    def is_ip_blacklisted(self, ip: str) -> bool:
        """Return whether an IP address is permanently blacklisted."""

        with self._lock:
            return ip in self._blacklisted_ips

    def cleanup_expired(self) -> int:
        """Remove expired IP and user records and return how many were removed."""

        with self._lock:
            now = self._now()
            removed = 0

            expired_ips: list[str] = []
            for ip, record in self._ip_records.items():
                if ip not in self._blacklisted_ips and record.blocked_until > now:
                    continue

                if (
                    record.first_attempt == 0.0
                    or now - record.first_attempt > IP_WINDOW_SECONDS
                ):
                    expired_ips.append(ip)

            for ip in expired_ips:
                _ = self._ip_records.pop(ip, None)
                removed += 1

            expired_users: list[str] = []
            for username, record in self._user_records.items():
                if record.locked_until > now:
                    continue

                if (
                    record.first_attempt == 0.0
                    or now - record.first_attempt > USER_WINDOW_SECONDS
                ):
                    expired_users.append(username)

            for username in expired_users:
                _ = self._user_records.pop(username, None)
                removed += 1

            return removed

    def _now(self) -> float:
        """Return the current monotonic time."""

        return time.monotonic()

    def _remaining_seconds(self, deadline: float, now: float) -> int:
        """Return the remaining whole seconds until a deadline."""

        return max(0, math.ceil(deadline - now))

    def _reset_ip_window_if_needed(self, record: IPRecord, now: float) -> None:
        """Reset IP attempts when the tracking window has expired."""

        if (
            record.first_attempt > 0.0
            and now - record.first_attempt > IP_WINDOW_SECONDS
        ):
            record.attempts = 0
            record.first_attempt = 0.0

    def _reset_user_window_if_needed(self, record: UserRecord, now: float) -> None:
        """Reset user attempts when the tracking window has expired."""

        if (
            record.first_attempt > 0.0
            and now - record.first_attempt > USER_WINDOW_SECONDS
        ):
            record.attempts = 0
            record.first_attempt = 0.0


_rate_limiter: LoginRateLimiter | None = None
_rate_limiter_lock: threading.Lock = threading.Lock()


def get_rate_limiter() -> LoginRateLimiter:
    """Return the process-wide login rate limiter instance."""

    global _rate_limiter

    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = LoginRateLimiter()

    return _rate_limiter
