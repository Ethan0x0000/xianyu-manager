from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "2.0"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class LogoutResponse(BaseModel):
    success: bool = True


class AccountCreateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    cookie_str: str = ""
    username: str = ""
    password: str = ""
    notes: str = ""
    enabled: bool = True
    show_browser: bool = False


class AccountResponse(BaseModel):
    account_id: str
    username: str = ""
    notes: str = ""
    enabled: bool = True
    show_browser: bool = False
    has_cookie: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class DeleteResponse(BaseModel):
    success: bool = True


class KeywordCreateRequest(BaseModel):
    pattern: str = Field(min_length=1)
    reply_content: str = ""
    item_id: str | None = None
    is_regex: bool = False
    enabled: bool = True


class KeywordResponse(BaseModel):
    id: int
    pattern: str
    reply_content: str
    item_id: str | None = None
    is_regex: bool = False
    enabled: bool = True
    scope: str = "general"


class RuntimeAccountResponse(BaseModel):
    account_id: str
    enabled: bool
    runtime_registered: bool
    runtime_active: bool
    username: str = ""
    notes: str = ""


class SettingEntry(BaseModel):
    key: str
    value: object | None = None


class SettingsResponse(BaseModel):
    settings: dict[str, object | None]


__all__ = [
    "AccountCreateRequest",
    "AccountResponse",
    "DeleteResponse",
    "HealthResponse",
    "KeywordCreateRequest",
    "KeywordResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "RuntimeAccountResponse",
    "SettingEntry",
    "SettingsResponse",
]
