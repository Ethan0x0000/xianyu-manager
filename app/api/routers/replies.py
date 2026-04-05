from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import KeywordCreateRequest, KeywordResponse
from app.db.connection import get_db

router = APIRouter(prefix="/api/replies", tags=["replies"])
keywords_router = APIRouter(prefix="/api/keywords", tags=["replies"])


def _query_keywords(db_path: str) -> list[KeywordResponse]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, pattern, reply_content, NULL AS item_id, is_regex, enabled, 'general' AS scope
            FROM keywords
            UNION ALL
            SELECT id, pattern, reply_content, item_id, is_regex, enabled, 'item' AS scope
            FROM item_keywords
            ORDER BY pattern, item_id
            """
        ).fetchall()

    return [
        KeywordResponse(
            id=int(str(row["id"])),
            pattern=str(cast(object, row["pattern"])),
            reply_content=str(cast(object, row["reply_content"])),
            item_id=str(row["item_id"]) if row["item_id"] is not None else None,
            is_regex=bool(cast(object, row["is_regex"])),
            enabled=bool(cast(object, row["enabled"])),
            scope=str(cast(object, row["scope"])),
        )
        for row in cast(list[sqlite3.Row], rows)
    ]


def _create_keyword(db_path: str, payload: KeywordCreateRequest) -> KeywordResponse:
    table_name = "item_keywords" if payload.item_id else "keywords"
    columns = (
        "item_id, pattern, reply_content, is_regex, enabled"
        if payload.item_id
        else "pattern, reply_content, is_regex, enabled"
    )
    params: tuple[object, ...] = (
        (
            payload.item_id,
            payload.pattern,
            payload.reply_content,
            int(payload.is_regex),
            int(payload.enabled),
        )
        if payload.item_id
        else (
            payload.pattern,
            payload.reply_content,
            int(payload.is_regex),
            int(payload.enabled),
        )
    )

    with get_db(db_path) as conn:
        cursor = conn.execute(
            f"INSERT INTO {table_name} ({columns}) VALUES ({', '.join('?' for _ in params)})",
            params,
        )
        if payload.item_id:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    """
                    SELECT id, pattern, reply_content, item_id, is_regex, enabled
                    FROM item_keywords
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone(),
            )
        else:
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    """
                    SELECT id, pattern, reply_content, NULL AS item_id, is_regex, enabled
                    FROM keywords
                    WHERE id = ?
                    """,
                    (cursor.lastrowid,),
                ).fetchone(),
            )

    assert row is not None
    return KeywordResponse(
        id=int(str(row["id"])),
        pattern=str(cast(object, row["pattern"])),
        reply_content=str(cast(object, row["reply_content"])),
        item_id=str(row["item_id"]) if row["item_id"] is not None else None,
        is_regex=bool(cast(object, row["is_regex"])),
        enabled=bool(cast(object, row["enabled"])),
        scope="item" if payload.item_id else "general",
    )


@router.get("/keywords", response_model=list[KeywordResponse])
async def list_reply_keywords(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[KeywordResponse]:
    del token
    return _query_keywords(db_path)


@router.post(
    "/keywords", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED
)
async def add_reply_keyword(
    payload: KeywordCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> KeywordResponse:
    del token
    return _create_keyword(db_path, payload)


@keywords_router.get("", response_model=list[KeywordResponse])
async def list_keywords_alias(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[KeywordResponse]:
    del token
    return _query_keywords(db_path)


@keywords_router.post(
    "", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED
)
async def add_keyword_alias(
    payload: KeywordCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> KeywordResponse:
    del token
    return _create_keyword(db_path, payload)


__all__ = ["keywords_router", "router"]
