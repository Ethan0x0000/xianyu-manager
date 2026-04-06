from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    authenticated: bool = True
    username: str
    is_admin: bool = True


class LoginInfoStatusResponse(BaseModel):
    enabled: bool


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


class QRLoginCreateResponse(BaseModel):
    success: bool = True
    session_id: str
    qr_code_url: str
    qr_image_data: str = ""
    status: str = "pending"
    expires_at: float


class QRLoginStatusResponse(BaseModel):
    success: bool = True
    session_id: str
    status: str
    qr_code_url: str = ""
    qr_image_data: str = ""
    expires_at: float | None = None
    result_cookie: str = ""


class PasswordLoginRequest(BaseModel):
    account_id: str = Field(min_length=1)
    account: str | None = None
    username: str | None = None
    password: str | None = None
    refresh_mode: bool = False
    show_browser: bool = False


class PasswordLoginCreateResponse(BaseModel):
    success: bool = True
    session_id: str
    status: str = "processing"
    message: str = "login_initiated"


class PasswordLoginStatusResponse(BaseModel):
    success: bool = True
    session_id: str
    status: str
    message: str = ""
    result_cookie: str = ""
    verification_url: str = ""
    qr_code_url: str = ""
    screenshot_path: str = ""
    verification_type: str = ""
    verification_message: str = ""


class AccountCompatDetailResponse(BaseModel):
    id: str
    value: str = ""
    username: str = ""
    enabled: bool = True
    show_browser: bool = False
    has_cookie: bool = False
    cookie_status: str = "missing"
    has_password: bool = False
    remark: str = ""
    pause_duration: int = 10
    created_at: str | None = None
    updated_at: str | None = None


class AccountStatusUpdateRequest(BaseModel):
    enabled: bool


class AccountRemarkUpdateRequest(BaseModel):
    remark: str = Field(default="", max_length=100)


class AccountPauseDurationUpdateRequest(BaseModel):
    pause_duration: int = Field(ge=0, le=60)


class RefreshCookieRequest(BaseModel):
    cookie_id: str = Field(min_length=1)
    qr_cookies: str = Field(min_length=1)


class RefreshCookieResponse(BaseModel):
    success: bool = True
    cookie_id: str
    message: str = "cookie_refreshed"
    cookie_status: str = "missing"
    value: str = ""


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
    "AccountCompatDetailResponse",
    "AccountPauseDurationUpdateRequest",
    "AccountRemarkUpdateRequest",
    "AccountResponse",
    "AccountStatusUpdateRequest",
    "DeleteResponse",
    "HealthResponse",
    "KeywordCreateRequest",
    "KeywordResponse",
    "LoginInfoStatusResponse",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "PasswordLoginCreateResponse",
    "PasswordLoginRequest",
    "PasswordLoginStatusResponse",
    "QRLoginCreateResponse",
    "QRLoginStatusResponse",
    "RefreshCookieRequest",
    "RefreshCookieResponse",
    "VerifyResponse",
    "RuntimeAccountResponse",
    "SettingEntry",
    "SettingsResponse",
]
