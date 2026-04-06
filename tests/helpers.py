"""Shared test helpers — temp DB fixture and Settings factory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.db.schema import initialize_database
from app.bootstrap.settings import Settings


def make_test_db() -> str:
    """Create a temporary SQLite database with the full schema.

    Returns the file path.  Caller is responsible for cleanup.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    initialize_database(path)
    return path


def make_settings(**overrides: object) -> Settings:
    """Build a Settings instance with safe test defaults."""
    defaults = dict(
        api_host="127.0.0.1",
        api_port=8848,
        db_path=":memory:",
        admin_username="testadmin",
        admin_password_hash="$2b$12$KIXqzFJKQfWnJbTjW8z5IOxfakehashjustfortest000000000",
        secret_key="test-secret-key-not-for-production",
        secret_encryption_key="test-enc-key-not-for-production",
    )
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]
