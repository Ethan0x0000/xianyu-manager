"""Centralized settings module for application configuration.

Loads settings from environment variables and YAML config file.
Environment variables take precedence over YAML defaults.
"""

from __future__ import annotations

import os
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import bcrypt

CONFIG_FILE = "global_config.yml"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_PASSWORD_HASH = bcrypt.hashpw(
    DEFAULT_ADMIN_PASSWORD.encode("utf-8"),
    bcrypt.gensalt(),
).decode("utf-8")


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    typed_value = cast(dict[object, object], value)
    return {str(key): nested_value for key, nested_value in typed_value.items()}


def _normalize_bind_host(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        candidate = normalized[1:-1]
        if ":" in candidate:
            return candidate
    return normalized


@dataclass
class Settings:
    """Application settings dataclass.

    All settings are loaded from environment variables (with precedence)
    and YAML config file.
    """

    # Server configuration
    api_host: str = "::"
    api_port: int = 8848

    # Database
    db_path: str = "data/xianyu_data.db"

    # Frontend build output and upload paths
    frontend_dist_dir: str = "frontend/dist"
    frontend_bundled_dist_dir: str = "/opt/xianyu-manager/frontend-dist"
    uploads_dir: str = "data/uploads"

    # Admin bootstrap defaults for first-time login; operators should override them.
    admin_username: str = DEFAULT_ADMIN_USERNAME
    admin_password_hash: str = DEFAULT_ADMIN_PASSWORD_HASH

    # Secret key for session signing (REQUIRED)
    secret_key: str = ""

    # Secret encryption key for stored credentials (REQUIRED)
    secret_encryption_key: str = ""

    # AI configuration (optional at startup)
    ai_enabled: bool = False

    # Docker/headful flags
    enable_headful: bool = False
    use_xvfb: bool = False
    enable_vnc: bool = False

    # SQL logging
    sql_log_enabled: bool = False
    sql_log_level: str = "INFO"

    # Logging configuration (from global_config.yml LOG_CONFIG)
    log_level: str = "INFO"
    log_format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level>"
        " | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        " - <level>{message}</level>"
    )
    log_rotation: str = "1 day"
    log_retention: str = "7 days"
    log_compression: str = "zip"

    # Goofish endpoints (loaded from global_config.yml)
    websocket_url: str = "wss://wss-goofish.dingtalk.com/"

    # Feature flags
    auto_reply_enabled: bool = True
    auto_shipping_enabled: bool = True
    auto_confirm_enabled: bool = True


def load_settings(config_path: str = CONFIG_FILE) -> Settings:
    """Load settings from environment variables and YAML config.

    Environment variables take precedence over YAML values.

    Args:
        config_path: Path to YAML config file (default: global_config.yml)

    Returns:
        Settings dataclass instance with all configuration values
    """
    raw: dict[str, object] = {}
    if Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            loaded = cast(object, yaml.safe_load(f))
        raw = _as_mapping(loaded)

    # Extract nested config values with safe defaults
    auto_reply_config = _as_mapping(raw.get("AUTO_REPLY", {}))
    api_config = _as_mapping(auto_reply_config.get("api", {}))
    log_config = _as_mapping(raw.get("LOG_CONFIG", {}))

    # Build settings with env var overrides (env vars take precedence)
    settings = Settings(
        api_host=_normalize_bind_host(
            os.environ.get("API_HOST") or str(api_config.get("host", "::"))
        ),
        api_port=int(os.environ.get("API_PORT") or str(api_config.get("port", 8848))),
        db_path=os.environ.get("DB_PATH", "data/xianyu_data.db"),
        frontend_dist_dir=os.environ.get("FRONTEND_DIST_DIR", "frontend/dist"),
        frontend_bundled_dist_dir=os.environ.get(
            "FRONTEND_BUNDLED_DIST_DIR", "/opt/xianyu-manager/frontend-dist"
        ),
        uploads_dir=os.environ.get("UPLOADS_DIR", "data/uploads"),
        admin_username=os.environ.get("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME),
        admin_password_hash=os.environ.get(
            "ADMIN_PASSWORD_HASH", DEFAULT_ADMIN_PASSWORD_HASH
        ),
        secret_key=os.environ.get("SECRET_KEY")
        or os.environ.get("ADMIN_SECRET_KEY", ""),
        secret_encryption_key=os.environ.get("SECRET_ENCRYPTION_KEY", ""),
        ai_enabled=os.environ.get("AI_ENABLED", "false").lower() == "true",
        enable_headful=os.environ.get("ENABLE_HEADFUL", "false").lower() == "true",
        use_xvfb=os.environ.get("USE_XVFB", "false").lower() == "true",
        enable_vnc=os.environ.get("ENABLE_VNC", "false").lower() == "true",
        sql_log_enabled=os.environ.get("SQL_LOG_ENABLED", "false").lower() == "true",
        sql_log_level=os.environ.get("SQL_LOG_LEVEL", "INFO"),
        log_level=os.environ.get("LOG_LEVEL") or str(log_config.get("level", "INFO")),
        log_format=str(log_config.get("format"))
        if log_config.get("format")
        else Settings.log_format,
        log_rotation=str(log_config.get("rotation", "1 day")),
        log_retention=str(log_config.get("retention", "7 days")),
        log_compression=str(log_config.get("compression", "zip")),
        websocket_url=os.environ.get("WEBSOCKET_URL")
        or str(raw.get("WEBSOCKET_URL", "wss://wss-goofish.dingtalk.com/")),
        auto_reply_enabled=os.environ.get("AUTO_REPLY_ENABLED", "true").lower()
        == "true",
        auto_shipping_enabled=os.environ.get("AUTO_SHIPPING_ENABLED", "true").lower()
        == "true",
        auto_confirm_enabled=os.environ.get("AUTO_CONFIRM_ENABLED", "true").lower()
        == "true",
    )

    return settings


def validate_settings(settings: Settings) -> None:
    """Validate required settings are present.

    Raises ValueError with clear message if required settings are missing.

    Args:
        settings: Settings instance to validate

    Raises:
        ValueError: If required settings are not set
    """
    errors: list[str] = []

    if not settings.secret_key:
        errors.append("SECRET_KEY env var is required but not set")

    if not settings.secret_encryption_key:
        errors.append("SECRET_ENCRYPTION_KEY env var is required but not set")

    if errors:
        error_msg = (
            "Missing required configuration:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nSet these environment variables before starting the app."
        )
        raise ValueError(error_msg)


def apply_db_overrides(settings: Settings, db_path: str) -> None:
    """Apply database-stored overrides to settings.

    Reads ``admin_password_hash`` from the ``system_settings`` table and
    overrides the default value loaded from env/YAML.  This ensures that
    password changes made via the admin API persist across restarts.

    Args:
        settings: Mutable Settings instance to update in-place.
        db_path: Path to the SQLite database.
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?",
            ("admin_password_hash",),
        ).fetchone()
        if row and row["value"]:
            settings.admin_password_hash = str(row["value"])
        conn.close()
    except Exception:
        # Database may not exist yet on first run — silently fall back to
        # the default loaded from env/YAML.
        pass
