from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Annotated, cast

import bcrypt
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import HealthResponse, SettingEntry, SettingsResponse
from app.auth.service import verify_admin_login
from app.bootstrap.settings import Settings, load_settings
from app.db.connection import get_db
from app.db.repositories.settings_repository import SettingsRepository

router = APIRouter(prefix="", tags=["system"])

THEME_COLOR_KEY = "theme_color"
MENU_SETTINGS_KEY = "menu_settings"
MENU_VISIBILITY_KEY = "menu_visibility"
MENU_ORDER_KEY = "menu_order"
LOGIN_INFO_KEY = "show_default_login_info"
LOGIN_CAPTCHA_KEY = "login_captcha_enabled"
REGISTRATION_KEY = "registration_enabled"
ADMIN_PASSWORD_HASH_KEY = "admin_password_hash"
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class MenuEntry(BaseModel):
    key: str = Field(min_length=1)
    label: str = ""
    visible: bool = True
    order: int = Field(ge=0)


class MenuSettingsPayload(BaseModel):
    menu: list[MenuEntry]


class ThemePayload(BaseModel):
    color: str


class PasswordChangePayload(BaseModel):
    new_password: str
    current_password: str | None = None


class LoginInfoPayload(BaseModel):
    show_default_credentials: bool


class TogglePayload(BaseModel):
    enabled: bool


class LegacySettingPayload(BaseModel):
    key: str | None = None
    value: object | None = None
    description: str | None = None


def _load_runtime_settings(request: Request | None = None) -> Settings:
    if request is not None:
        app = cast(FastAPI, request.app)
        app_settings = cast(Settings | None, getattr(app.state, "settings", None))
        if isinstance(app_settings, Settings):
            return app_settings
    return load_settings()


def _serialize_setting_value(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _load_settings_rows(db_path: str) -> list[dict[str, object]]:
    return SettingsRepository(db_path).get_all()


def _load_settings_map(db_path: str) -> dict[str, str]:
    settings = {
        str(item["key"]): str(item["value"])
        for item in _load_settings_rows(db_path)
        if str(item["key"]) != ADMIN_PASSWORD_HASH_KEY
    }
    return settings


def _upsert_setting(db_path: str, key: str, value: object | None) -> None:
    serialized_value = _serialize_setting_value(value)
    with get_db(db_path) as conn:
        _ = conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, serialized_value),
        )


def _upsert_many_settings(db_path: str, entries: list[SettingEntry]) -> int:
    for entry in entries:
        _upsert_setting(db_path, entry.key, entry.value)
    return len(entries)


def _setting_enabled(
    settings_map: dict[str, str], key: str, default: bool = False
) -> bool:
    raw_value = settings_map.get(key)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_json_list(value: str | None) -> list[object]:
    if not value:
        return []
    try:
        parsed = cast(object, json.loads(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in cast(list[object], parsed)]


def _parse_json_dict(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = cast(object, json.loads(value))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    parsed_dict = cast(dict[object, object], parsed)
    return {str(key): item for key, item in parsed_dict.items()}


def _build_legacy_user_settings_payload(db_path: str) -> dict[str, dict[str, object]]:
    return {
        str(item["key"]): {
            "key": str(item["key"]),
            "value": item["value"],
            "updated_at": item.get("updated_at"),
        }
        for item in _load_settings_rows(db_path)
        if str(item["key"]) != ADMIN_PASSWORD_HASH_KEY
    }


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _build_menu_payload(settings_map: dict[str, str]) -> list[dict[str, object]]:
    stored_menu = _parse_json_list(settings_map.get(MENU_SETTINGS_KEY))
    if stored_menu:
        stored_menu_payload: list[dict[str, object]] = []
        for raw_item in stored_menu:
            if not isinstance(raw_item, dict):
                continue
            item = cast(dict[str, object], raw_item)
            if not item.get("key"):
                continue
            stored_menu_payload.append(
                {
                    "key": str(item.get("key", "")),
                    "label": str(item.get("label", "")),
                    "visible": bool(item.get("visible", True)),
                    "order": _as_int(item.get("order", 0)),
                }
            )
        return stored_menu_payload

    visibility = _parse_json_dict(settings_map.get(MENU_VISIBILITY_KEY))
    order = _parse_json_list(settings_map.get(MENU_ORDER_KEY))
    if not order:
        return []

    menu: list[dict[str, object]] = []
    for index, raw_key in enumerate(order):
        if not isinstance(raw_key, str):
            continue
        menu.append(
            {
                "key": raw_key,
                "label": raw_key,
                "visible": bool(visibility.get(raw_key, True)),
                "order": index,
            }
        )
    return menu


def _save_menu_settings(
    db_path: str, entries: list[MenuEntry]
) -> list[dict[str, object]]:
    menu = [
        entry.model_dump() for entry in sorted(entries, key=lambda entry: entry.order)
    ]
    visibility = {entry.key: entry.visible for entry in entries}
    order = [entry.key for entry in sorted(entries, key=lambda entry: entry.order)]

    _upsert_setting(db_path, MENU_SETTINGS_KEY, menu)
    _upsert_setting(db_path, MENU_VISIBILITY_KEY, visibility)
    _upsert_setting(db_path, MENU_ORDER_KEY, order)
    return menu


def _build_login_info_payload(
    request: Request | None, db_path: str
) -> dict[str, object]:
    app_settings = _load_runtime_settings(request)
    settings_map = _load_settings_map(db_path)
    show_default_credentials = _setting_enabled(settings_map, LOGIN_INFO_KEY)
    payload: dict[str, object] = {
        "show_default_credentials": show_default_credentials,
    }
    if show_default_credentials:
        payload["default_username"] = app_settings.admin_username
    return payload


def _update_admin_password(
    request: Request,
    db_path: str,
    payload: PasswordChangePayload,
) -> dict[str, object]:
    new_password = payload.new_password.strip()
    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="new_password must not be empty",
        )

    app_settings = _load_runtime_settings(request)
    if payload.current_password and not verify_admin_login(
        app_settings.admin_username,
        payload.current_password,
        app_settings,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is invalid",
        )

    password_hash = bcrypt.hashpw(
        new_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")
    app_settings.admin_password_hash = password_hash
    _upsert_setting(db_path, ADMIN_PASSWORD_HASH_KEY, password_hash)
    return {"success": True}


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version="0.1.0")


@router.get("/api/settings", response_model=SettingsResponse)
async def get_system_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> SettingsResponse:
    del token
    try:
        payload = _load_settings_map(db_path)
    except Exception:
        payload = asdict(load_settings())

    _ = payload.pop("admin_password_hash", None)
    return SettingsResponse(settings=cast(dict[str, object | None], payload))


@router.post("/api/settings")
async def upsert_system_settings(
    payload: SettingEntry | list[SettingEntry],
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    entries = payload if isinstance(payload, list) else [payload]
    updated = _upsert_many_settings(db_path, entries)
    return {"updated": updated}


@router.get("/api/settings/menu")
async def get_menu_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"menu": _build_menu_payload(_load_settings_map(db_path))}


@router.post("/api/settings/menu")
async def save_menu_settings(
    payload: MenuSettingsPayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"menu": _save_menu_settings(db_path, payload.menu)}


@router.post("/api/settings/theme")
async def save_theme_color(
    payload: ThemePayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    color = payload.color.strip()
    if not HEX_COLOR_PATTERN.match(color):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Theme color must be a 6-digit hex value",
        )
    _upsert_setting(db_path, THEME_COLOR_KEY, color)
    return {"color": color}


@router.get("/api/settings/login-info")
async def get_login_info_settings(
    request: Request,
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    return _build_login_info_payload(request, db_path)


@router.post("/api/settings/login-info")
async def save_login_info_settings(
    payload: LoginInfoPayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    _upsert_setting(db_path, LOGIN_INFO_KEY, payload.show_default_credentials)
    return {"show_default_credentials": payload.show_default_credentials}


@router.post("/api/admin/password")
async def change_admin_password(
    payload: PasswordChangePayload,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return _update_admin_password(request, db_path, payload)


@router.get("/user-settings", include_in_schema=False)
async def legacy_get_user_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, dict[str, object]]:
    del token
    return _build_legacy_user_settings_payload(db_path)


@router.put("/user-settings/{key}", include_in_schema=False)
async def legacy_upsert_user_setting(
    key: str,
    payload: LegacySettingPayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    _upsert_setting(db_path, key, payload.value)
    return {"key": key, "value": _serialize_setting_value(payload.value)}


@router.get("/system-settings", include_in_schema=False)
async def legacy_get_system_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, str]:
    del token
    return _load_settings_map(db_path)


@router.put("/system-settings/{key}", include_in_schema=False)
async def legacy_upsert_system_setting(
    key: str,
    payload: LegacySettingPayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    _upsert_setting(db_path, key, payload.value)
    return {"key": key, "value": _serialize_setting_value(payload.value)}


@router.post("/change-admin-password", include_in_schema=False)
async def legacy_change_admin_password(
    payload: PasswordChangePayload,
    request: Request,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return _update_admin_password(request, db_path, payload)


@router.get("/registration-status", include_in_schema=False)
async def registration_status(
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, bool]:
    return {"enabled": _setting_enabled(_load_settings_map(db_path), REGISTRATION_KEY)}


@router.put("/registration-settings", include_in_schema=False)
async def update_registration_settings(
    payload: TogglePayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, bool]:
    del token
    _upsert_setting(db_path, REGISTRATION_KEY, payload.enabled)
    return {"enabled": payload.enabled}


@router.put("/login-info-settings", include_in_schema=False)
async def legacy_update_login_info_settings(
    payload: TogglePayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, bool]:
    del token
    _upsert_setting(db_path, LOGIN_INFO_KEY, payload.enabled)
    return {"enabled": payload.enabled}


@router.put("/login-captcha-settings", include_in_schema=False)
async def update_login_captcha_settings(
    payload: TogglePayload,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, bool]:
    del token
    _upsert_setting(db_path, LOGIN_CAPTCHA_KEY, payload.enabled)
    return {"enabled": payload.enabled}


@router.delete("/api/settings/{key}")
async def delete_system_setting(
    key: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    _ = SettingsRepository(db_path).delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
