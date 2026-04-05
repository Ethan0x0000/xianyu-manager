"""Local reply policy service.

Resolves non-AI replies in priority order:
1. Item-specific reply (highest)
2. Item-specific keyword match
3. General keyword match
4. Default reply
5. None → AI fallback (lowest)

FROZEN PRIORITY ORDER — do not change.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReplyResult:
    reply_text: str
    source: str  # "item_reply", "item_keyword", "keyword", "default", "ai_fallback"
    matched_pattern: str = ""


class ReplyPolicyService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def resolve(self, item_id: str, message_text: str) -> ReplyResult | None:
        """Resolve a local reply or return None for AI fallback.

        Priority order (FROZEN):
        1. Item-specific reply (for this exact item_id)
        2. Item-specific keyword match (keyword tied to this item_id)
        3. General keyword match
        4. Default reply
        5. None → caller should use AI
        """
        # Load data (in real implementation, uses repositories)
        # For now: use DB directly as stub
        from app.db.connection import get_db

        with get_db(self.db_path) as conn:
            # 1. Item-specific reply
            row = conn.execute(
                "SELECT reply_content FROM item_replies WHERE item_id=? AND enabled=1 LIMIT 1",
                (item_id,),
            ).fetchone()
            if row:
                return ReplyResult(reply_text=row["reply_content"], source="item_reply")

            # 2. Item-specific keyword match
            rows = conn.execute(
                "SELECT pattern, reply_content, is_regex FROM item_keywords WHERE item_id=? AND enabled=1",
                (item_id,),
            ).fetchall()
            for row in rows:
                if self._matches(message_text, row["pattern"], bool(row["is_regex"])):
                    return ReplyResult(
                        reply_text=row["reply_content"],
                        source="item_keyword",
                        matched_pattern=row["pattern"],
                    )

            # 3. General keyword match
            rows = conn.execute(
                "SELECT pattern, reply_content, is_regex FROM keywords WHERE enabled=1"
            ).fetchall()
            for row in rows:
                if self._matches(message_text, row["pattern"], bool(row["is_regex"])):
                    return ReplyResult(
                        reply_text=row["reply_content"],
                        source="keyword",
                        matched_pattern=row["pattern"],
                    )

            # 4. Default reply
            row = conn.execute(
                "SELECT content FROM default_replies WHERE enabled=1 LIMIT 1"
            ).fetchone()
            if row:
                return ReplyResult(reply_text=row["content"], source="default")

        # 5. No local match → AI fallback
        return None

    def _matches(self, text: str, pattern: str, is_regex: bool) -> bool:
        """Check if text matches the pattern."""
        try:
            if is_regex:
                return bool(re.search(pattern, text))
            return pattern.lower() in text.lower()
        except Exception:
            return False
