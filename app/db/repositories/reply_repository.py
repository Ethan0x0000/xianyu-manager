from __future__ import annotations

from . import BaseRepository


class ReplyRepository(BaseRepository):
    """Repository stub for reply-rule storage.

    Primary table: keywords
    Related tables: item_keywords, default_replies, item_replies
    """

    table_name: str = "keywords"
