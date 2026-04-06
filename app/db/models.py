from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class XianyuAccount:
    account_id: str
    id: int | None = None
    cookie_str: str = ""
    username: str = ""
    password: str = ""
    notes: str = ""
    enabled: bool = True
    show_browser: bool = False
    pause_duration: int = 10
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class SystemSetting:
    key: str
    value: str
    updated_at: str | None = None


@dataclass(slots=True)
class AdminSession:
    session_id: str
    expires_at: str
    created_at: str | None = None


@dataclass(slots=True)
class Keyword:
    pattern: str
    reply_content: str
    id: int | None = None
    is_regex: bool = False
    enabled: bool = True
    created_at: str | None = None


@dataclass(slots=True)
class ItemKeyword:
    item_id: str
    pattern: str
    reply_content: str
    id: int | None = None
    is_regex: bool = False
    enabled: bool = True
    created_at: str | None = None


@dataclass(slots=True)
class DefaultReply:
    content: str
    id: int | None = None
    enabled: bool = True
    created_at: str | None = None


@dataclass(slots=True)
class ItemReply:
    item_id: str
    reply_content: str
    id: int | None = None
    enabled: bool = True
    created_at: str | None = None


@dataclass(slots=True)
class AISetting:
    provider_type: str
    id: int | None = None
    api_key: str = ""
    base_url: str = ""
    model_name: str = ""
    system_prompt: str = ""
    max_tokens: int = 512
    enabled: bool = False


@dataclass(slots=True)
class Conversation:
    session_key: str
    role: str
    content: str
    id: int | None = None
    created_at: str | None = None


@dataclass(slots=True)
class Item:
    item_id: str
    account_id: str
    id: int | None = None
    title: str = ""
    price: str = ""
    status: str = ""
    raw_data: str = ""
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class Order:
    order_id: str
    account_id: str
    id: int | None = None
    item_id: str | None = None
    buyer_id: str = ""
    status: str = ""
    amount: str = ""
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class DeliveryCard:
    name: str
    content_type: str
    content: str
    account_id: str
    id: int | None = None
    created_at: str | None = None


@dataclass(slots=True)
class DeliveryRule:
    item_id: str
    card_id: int
    account_id: str
    id: int | None = None
    priority: int = 0
    enabled: bool = True
    created_at: str | None = None


@dataclass(slots=True)
class DeliveryLog:
    order_id: str
    status: str
    id: int | None = None
    card_id: int | None = None
    created_at: str | None = None


@dataclass(slots=True)
class RiskLog:
    account_id: str
    event_type: str
    id: int | None = None
    details: str = ""
    created_at: str | None = None


@dataclass(slots=True)
class PolishSchedule:
    account_id: str
    id: int | None = None
    enabled: bool = True
    start_hour: int = 8
    end_hour: int = 22
    random_delay_minutes: int = 0
    last_run_at: str | None = None
    created_at: str | None = None
