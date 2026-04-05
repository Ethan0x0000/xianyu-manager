from __future__ import annotations

import asyncio
import threading
from _thread import LockType
from dataclasses import dataclass, field

__all__ = [
    "AccountEntry",
    "AccountNotFoundError",
    "AccountRegistry",
    "DuplicateAccountError",
    "get_registry",
]


class DuplicateAccountError(Exception):
    """Raised when attempting to add an account that already exists."""


class AccountNotFoundError(Exception):
    """Raised when an account is not found in the registry."""


@dataclass
class AccountEntry:
    account_id: str
    cookie_str: str
    username: str = ""
    notes: str = ""
    enabled: bool = True
    # Runtime state (not persisted)
    runtime_instance: object | None = field(default=None, repr=False)
    background_task: asyncio.Task[object] | None = field(default=None, repr=False)


class AccountRegistry:
    """
    In-memory registry for multiple Xianyu seller accounts.

    Manages the lifecycle and runtime state of all active Xianyu accounts
    for a single admin. Thread-safe for concurrent asyncio + threading access.

    PROTOCOL: Implements AccountRegistryProtocol from app.shared.types.
    """

    def __init__(self) -> None:
        self._accounts: dict[str, AccountEntry] = {}
        self._lock: LockType = threading.Lock()

    def add_account(
        self,
        account_id: str,
        cookie_str: str,
        username: str = "",
        notes: str = "",
    ) -> AccountEntry:
        """Add a new account. Raises DuplicateAccountError if account_id already exists."""
        with self._lock:
            if account_id in self._accounts:
                raise DuplicateAccountError(
                    f"Account '{account_id}' already exists. Remove it first to re-add."
                )

            entry = AccountEntry(
                account_id=account_id,
                cookie_str=cookie_str,
                username=username,
                notes=notes,
            )
            self._accounts[account_id] = entry
            return entry

    def remove_account(self, account_id: str) -> None:
        """Remove an account. Raises AccountNotFoundError if not found."""
        with self._lock:
            if account_id not in self._accounts:
                raise AccountNotFoundError(f"Account '{account_id}' not found")

            del self._accounts[account_id]

    def get_account(self, account_id: str) -> AccountEntry | None:
        """Get account by ID, returns None if not found."""
        with self._lock:
            return self._accounts.get(account_id)

    def list_accounts(self) -> list[AccountEntry]:
        """List all registered accounts."""
        with self._lock:
            return list(self._accounts.values())

    def enable_account(self, account_id: str) -> None:
        """Enable an account. Raises AccountNotFoundError if not found."""
        with self._lock:
            entry = self._accounts.get(account_id)
            if entry is None:
                raise AccountNotFoundError(f"Account '{account_id}' not found")

            entry.enabled = True

    def disable_account(self, account_id: str) -> None:
        """Disable an account. Raises AccountNotFoundError if not found."""
        with self._lock:
            entry = self._accounts.get(account_id)
            if entry is None:
                raise AccountNotFoundError(f"Account '{account_id}' not found")

            entry.enabled = False

    def register_runtime(
        self,
        account_id: str,
        instance: object,
        task: asyncio.Task[object] | None = None,
    ) -> None:
        """Register a runtime instance and optional asyncio task for an account."""
        with self._lock:
            entry = self._accounts.get(account_id)
            if entry is None:
                raise AccountNotFoundError(f"Account '{account_id}' not found")

            entry.runtime_instance = instance
            entry.background_task = task

    def count(self) -> int:
        """Return the number of registered accounts."""
        with self._lock:
            return len(self._accounts)


# Module-level singleton (will be replaced by DI in full app, usable for testing)
_default_registry: AccountRegistry | None = None


def get_registry() -> AccountRegistry:
    """Get or create the default registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = AccountRegistry()
    return _default_registry
