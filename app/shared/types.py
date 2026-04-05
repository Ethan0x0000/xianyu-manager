"""Shared runtime protocols, typed payloads, and service keys.

These types define the explicit boundaries that future extraction tasks plug
into, without importing legacy runtime modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypedDict, runtime_checkable

DEFAULT_DB_PATH = "data/xianyu_data.db"


class ServiceKey(str, Enum):
    """Stable container keys for the bootstrap composition root."""

    ACCOUNT_REGISTRY = "account_registry"
    WS_CLIENT = "ws_client"
    TOKEN_REFRESH = "token_refresh"
    REPLY_POLICY = "reply_policy"
    AI_REPLY = "ai_reply"
    SHIPPING = "shipping"
    ITEM_POLISH = "item_polish"
    AUTO_CONFIRM = "auto_confirm"
    LOGIN_SERVICE = "login_service"
    SETTINGS = "settings"
    DB_PATH = "db_path"


@dataclass(frozen=True, slots=True)
class StubBinding:
    """Placeholder service binding used until real implementations are extracted."""

    key: str
    package: str
    description: str = ""


class AccountRecord(TypedDict, total=False):
    """Minimal account registry payload shared across runtime modules."""

    account_id: str
    cookie_str: str
    enabled: bool
    metadata: dict[str, object]


class ReplyEvent(TypedDict, total=False):
    """Normalized event payload that reply policy services consume."""

    account_id: str
    session_key: str
    item_id: str
    message: str
    metadata: dict[str, object]


class ReplyDecision(TypedDict, total=False):
    """Reply decision returned by policy services."""

    reply: str
    strategy: str
    should_send: bool
    metadata: dict[str, object]


@runtime_checkable
class AccountRegistryProtocol(Protocol):
    """Runtime account registry boundary."""

    async def add_account(self, account_id: str, cookie_str: str) -> None: ...

    async def remove_account(self, account_id: str) -> None: ...

    async def get_account(self, account_id: str) -> AccountRecord | None: ...

    def list_accounts(self) -> list[AccountRecord]: ...

    async def enable_account(self, account_id: str) -> None: ...

    async def disable_account(self, account_id: str) -> None: ...


@runtime_checkable
class WebSocketClientProtocol(Protocol):
    """WebSocket lifecycle boundary."""

    async def connect(self, account_id: str, cookie_str: str) -> None: ...

    async def disconnect(self, account_id: str) -> None: ...

    async def send(self, account_id: str, payload: dict[str, object]) -> None: ...


@runtime_checkable
class TokenRefreshProtocol(Protocol):
    """Cookie/token refresh boundary."""

    async def refresh(self, account_id: str) -> bool: ...

    async def merge_cookies(
        self, existing: dict[str, str], incoming: dict[str, str]
    ) -> dict[str, str]: ...


@runtime_checkable
class ReplyPolicyProtocol(Protocol):
    """Reply policy boundary."""

    async def resolve(self, event: ReplyEvent) -> ReplyDecision | None: ...


@runtime_checkable
class ShippingServiceProtocol(Protocol):
    """Shipping orchestration boundary."""

    async def process_order(
        self, order_id: str, item_id: str, account_id: str
    ) -> None: ...


@runtime_checkable
class AIReplyProtocol(Protocol):
    """AI reply generation boundary."""

    async def generate_reply(
        self, session_key: str, message: str, context: list[dict[str, object]]
    ) -> str: ...


class ServiceContainerDict(TypedDict, total=False):
    """Typed view of the bootstrap service container."""

    account_registry: AccountRegistryProtocol | StubBinding | None
    ws_client: WebSocketClientProtocol | StubBinding | None
    token_refresh: TokenRefreshProtocol | StubBinding | None
    reply_policy: ReplyPolicyProtocol | StubBinding | None
    ai_reply: AIReplyProtocol | StubBinding | None
    shipping: ShippingServiceProtocol | StubBinding | None
    item_polish: StubBinding | None
    auto_confirm: StubBinding | None
    login_service: StubBinding | None
    settings: object | None
    db_path: str


__all__ = [
    "AIReplyProtocol",
    "AccountRecord",
    "AccountRegistryProtocol",
    "DEFAULT_DB_PATH",
    "ReplyDecision",
    "ReplyEvent",
    "ReplyPolicyProtocol",
    "ServiceContainerDict",
    "ServiceKey",
    "ShippingServiceProtocol",
    "StubBinding",
    "TokenRefreshProtocol",
    "WebSocketClientProtocol",
]
