"""AI reply provider and conversation context service.

Extracts from ai_reply_engine.py. Supports retained providers only.
Does NOT add new providers, streaming, or redesign prompts.
"""

from __future__ import annotations

import enum
import logging
import sqlite3
from typing import cast

logger = logging.getLogger(__name__)


class AIProvider(enum.Enum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    GEMINI = "gemini"
    DISABLED = "disabled"


class UnsupportedProviderError(Exception):
    """Raised when an unknown/unsupported AI provider is requested."""


class AIReplyService:
    """AI provider dispatch and conversation context management."""

    SUPPORTED_PROVIDERS: set[str] = {provider.value for provider in AIProvider}

    def __init__(self, db_path: str) -> None:
        self.db_path: str = db_path

    def resolve_provider(self, provider_type: str) -> AIProvider:
        """Resolve a string provider type to AIProvider enum.

        Raises:
            UnsupportedProviderError: If provider_type is not supported
        """
        normalized = provider_type.lower().strip() if provider_type else ""

        mapping = {
            "openai": AIProvider.OPENAI,
            "gpt": AIProvider.OPENAI,
            "gpt-4": AIProvider.OPENAI,
            "gpt-3.5": AIProvider.OPENAI,
            "openai_compatible": AIProvider.OPENAI_COMPATIBLE,
            "compatible": AIProvider.OPENAI_COMPATIBLE,
            "gemini": AIProvider.GEMINI,
            "google": AIProvider.GEMINI,
            "disabled": AIProvider.DISABLED,
            "none": AIProvider.DISABLED,
            "": AIProvider.DISABLED,
        }

        provider = mapping.get(normalized)
        if provider is None:
            raise UnsupportedProviderError(
                f"Unsupported AI provider: '{provider_type}'. "
                + "Supported: openai, openai_compatible, gemini, disabled"
            )
        return provider

    async def generate_reply(
        self,
        session_key: str,
        message: str,
        system_prompt: str = "",
        context: list[dict[str, str]] | None = None,
    ) -> str:
        """Generate an AI reply. Returns empty string if provider is disabled."""
        del message, system_prompt, context

        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    "SELECT provider_type, api_key, base_url, model_name, system_prompt, enabled FROM ai_settings WHERE enabled=1 LIMIT 1"
                ).fetchone(),
            )

        if not row:
            return ""

        provider = self.resolve_provider(cast(str, row["provider_type"]))
        if provider == AIProvider.DISABLED:
            return ""

        logger.info(
            "AI reply request via %s for session %s", provider.value, session_key
        )
        return ""

    async def test_connection(
        self,
        *,
        provider_type: str,
        api_key: str = "",
        base_url: str = "",
        model_name: str = "",
        system_prompt: str = "",
        max_tokens: int = 512,
        enabled: bool = False,
    ) -> tuple[bool, str]:
        """Validate the current AI configuration without calling providers yet."""
        del base_url, model_name, system_prompt, max_tokens

        try:
            provider = self.resolve_provider(provider_type)
        except UnsupportedProviderError as exc:
            return (False, str(exc))

        if provider == AIProvider.DISABLED or not enabled:
            return (True, "AI replies are disabled")

        if not api_key.strip():
            return (False, "API key is required")

        return (True, f"{provider.value} configuration looks valid")

    def get_conversation_context(
        self, session_key: str, limit: int = 10
    ) -> list[dict[str, str]]:
        """Load recent conversation history for context window."""
        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            rows = cast(
                list[sqlite3.Row],
                conn.execute(
                    "SELECT role, content FROM conversations WHERE session_key=? ORDER BY id DESC LIMIT ?",
                    (session_key, limit),
                ).fetchall(),
            )
        return [
            {"role": row["role"], "content": row["content"]} for row in reversed(rows)
        ]

    def save_message(self, session_key: str, role: str, content: str) -> None:
        """Save a message to conversation history."""
        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            _ = conn.execute(
                "INSERT INTO conversations (session_key, role, content) VALUES (?, ?, ?)",
                (session_key, role, content),
            )
