from __future__ import annotations

from . import BaseRepository


class SettingsRepository(BaseRepository):
    """Repository stub for global settings and admin sessions."""

    table_name: str = "system_settings"
    id_column: str = "key"
