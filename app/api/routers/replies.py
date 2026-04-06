from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import (
    DefaultReplyCreateRequest,
    DefaultReplyResponse,
    DefaultReplyUpdateRequest,
    ItemReplyCreateRequest,
    ItemReplyResponse,
    ItemReplyUpdateRequest,
    KeywordCreateRequest,
    KeywordExportResponse,
    KeywordImportRequest,
    KeywordImportResponse,
    KeywordResponse,
    KeywordUpdateRequest,
)
from app.db.connection import get_db

router = APIRouter(prefix="/api/replies", tags=["replies"])
keywords_router = APIRouter(prefix="/api/keywords", tags=["replies"])


def _map_keyword_row(row: sqlite3.Row, scope: str) -> KeywordResponse:
    item_id = cast(str | None, row["item_id"])
    return KeywordResponse(
        id=cast(int, row["id"]),
        pattern=str(cast(object, row["pattern"])),
        reply_content=str(cast(object, row["reply_content"])),
        item_id=item_id,
        is_regex=bool(cast(object, row["is_regex"])),
        enabled=bool(cast(object, row["enabled"])),
        scope=scope,
    )


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
        _map_keyword_row(row, str(cast(object, row["scope"])))
        for row in cast(list[sqlite3.Row], rows)
    ]


def _insert_keyword_row(
    conn: sqlite3.Connection,
    payload: KeywordCreateRequest | KeywordImportRequest,
) -> KeywordResponse:
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
    cursor = conn.execute(
        f"INSERT INTO {table_name} ({columns}) VALUES ({', '.join('?' for _ in params)})",
        params,
    )
    row_id = cursor.lastrowid
    assert row_id is not None
    row = _select_keyword_row(conn, table_name, row_id)
    assert row is not None
    return _map_keyword_row(row, "item" if payload.item_id else "general")


def _select_keyword_row(
    conn: sqlite3.Connection,
    table_name: str,
    keyword_id: int,
) -> sqlite3.Row | None:
    if table_name == "item_keywords":
        return cast(
            sqlite3.Row | None,
            conn.execute(
                """
                SELECT id, pattern, reply_content, item_id, is_regex, enabled
                FROM item_keywords
                WHERE id = ?
                """,
                (keyword_id,),
            ).fetchone(),
        )
    return cast(
        sqlite3.Row | None,
        conn.execute(
            """
            SELECT id, pattern, reply_content, NULL AS item_id, is_regex, enabled
            FROM keywords
            WHERE id = ?
            """,
            (keyword_id,),
        ).fetchone(),
    )


def _find_keyword_location(
    conn: sqlite3.Connection,
    keyword_id: int,
) -> tuple[str, str, sqlite3.Row] | None:
    keyword_row = _select_keyword_row(conn, "keywords", keyword_id)
    if keyword_row is not None:
        return ("keywords", "general", keyword_row)

    item_keyword_row = _select_keyword_row(conn, "item_keywords", keyword_id)
    if item_keyword_row is not None:
        return ("item_keywords", "item", item_keyword_row)

    return None


def _create_keyword(db_path: str, payload: KeywordCreateRequest) -> KeywordResponse:
    with get_db(db_path) as conn:
        return _insert_keyword_row(conn, payload)


def _require_keyword_location(
    conn: sqlite3.Connection,
    keyword_id: int,
) -> tuple[str, str, sqlite3.Row]:
    location = _find_keyword_location(conn, keyword_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Keyword not found",
        )
    return location


def _map_default_reply_row(row: sqlite3.Row) -> DefaultReplyResponse:
    return DefaultReplyResponse(
        id=cast(int, row["id"]),
        content=str(cast(object, row["content"])),
        enabled=bool(cast(object, row["enabled"])),
        created_at=cast(str | None, row["created_at"]),
    )


def _map_item_reply_row(row: sqlite3.Row) -> ItemReplyResponse:
    return ItemReplyResponse(
        id=cast(int, row["id"]),
        item_id=str(cast(object, row["item_id"])),
        reply_content=str(cast(object, row["reply_content"])),
        enabled=bool(cast(object, row["enabled"])),
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


@router.put("/keywords/{keyword_id}", response_model=KeywordResponse)
async def update_reply_keyword(
    keyword_id: int,
    payload: KeywordUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> KeywordResponse:
    del token
    with get_db(db_path) as conn:
        table_name, scope, _ = _require_keyword_location(conn, keyword_id)
        _ = conn.execute(
            f"UPDATE {table_name} SET pattern = ?, reply_content = ?, is_regex = ?, enabled = ? WHERE id = ?",
            (
                payload.pattern,
                payload.reply_content,
                int(payload.is_regex),
                int(payload.enabled),
                keyword_id,
            ),
        )
        updated_row = _select_keyword_row(conn, table_name, keyword_id)

    assert updated_row is not None
    return _map_keyword_row(updated_row, scope)


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply_keyword(
    keyword_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    with get_db(db_path) as conn:
        deleted_general = conn.execute(
            "DELETE FROM keywords WHERE id = ?",
            (keyword_id,),
        ).rowcount
        if deleted_general:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        deleted_item = conn.execute(
            "DELETE FROM item_keywords WHERE id = ?",
            (keyword_id,),
        ).rowcount
        if deleted_item:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Keyword not found",
    )


@router.get("/default", response_model=list[DefaultReplyResponse])
async def list_default_replies(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[DefaultReplyResponse]:
    del token
    with get_db(db_path) as conn:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT id, content, enabled, created_at FROM default_replies ORDER BY id"
            ).fetchall(),
        )
    return [_map_default_reply_row(row) for row in rows]


@router.post(
    "/default",
    response_model=DefaultReplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_default_reply(
    payload: DefaultReplyCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> DefaultReplyResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO default_replies (content, enabled) VALUES (?, ?)",
            (payload.content, int(payload.enabled)),
        )
        row = cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT id, content, enabled, created_at FROM default_replies WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone(),
        )
    assert row is not None
    return _map_default_reply_row(row)


@router.put("/default/{reply_id}", response_model=DefaultReplyResponse)
async def update_default_reply(
    reply_id: int,
    payload: DefaultReplyUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> DefaultReplyResponse:
    del token
    with get_db(db_path) as conn:
        updated = conn.execute(
            "UPDATE default_replies SET content = ?, enabled = ? WHERE id = ?",
            (payload.content, int(payload.enabled), reply_id),
        ).rowcount
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Default reply not found",
            )
        row = cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT id, content, enabled, created_at FROM default_replies WHERE id = ?",
                (reply_id,),
            ).fetchone(),
        )
    assert row is not None
    return _map_default_reply_row(row)


@router.delete("/default/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_default_reply(
    reply_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    with get_db(db_path) as conn:
        deleted = conn.execute(
            "DELETE FROM default_replies WHERE id = ?",
            (reply_id,),
        ).rowcount
        if deleted:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Default reply not found",
    )


@router.get("/item-replies", response_model=list[ItemReplyResponse])
async def list_item_replies(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    item_id: Annotated[str, Query(min_length=1)],
) -> list[ItemReplyResponse]:
    del token
    with get_db(db_path) as conn:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT id, item_id, reply_content, enabled FROM item_replies WHERE item_id = ? ORDER BY id",
                (item_id,),
            ).fetchall(),
        )
    return [_map_item_reply_row(row) for row in rows]


@router.post(
    "/item-replies",
    response_model=ItemReplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_reply(
    payload: ItemReplyCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> ItemReplyResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO item_replies (item_id, reply_content, enabled) VALUES (?, ?, ?)",
            (payload.item_id, payload.reply_content, int(payload.enabled)),
        )
        row = cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT id, item_id, reply_content, enabled FROM item_replies WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone(),
        )
    assert row is not None
    return _map_item_reply_row(row)


@router.put("/item-replies/{reply_id}", response_model=ItemReplyResponse)
async def update_item_reply(
    reply_id: int,
    payload: ItemReplyUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> ItemReplyResponse:
    del token
    with get_db(db_path) as conn:
        updated = conn.execute(
            "UPDATE item_replies SET item_id = ?, reply_content = ?, enabled = ? WHERE id = ?",
            (payload.item_id, payload.reply_content, int(payload.enabled), reply_id),
        ).rowcount
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item reply not found",
            )
        row = cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT id, item_id, reply_content, enabled FROM item_replies WHERE id = ?",
                (reply_id,),
            ).fetchone(),
        )
    assert row is not None
    return _map_item_reply_row(row)


@router.delete("/item-replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_reply(
    reply_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    with get_db(db_path) as conn:
        deleted = conn.execute(
            "DELETE FROM item_replies WHERE id = ?",
            (reply_id,),
        ).rowcount
        if deleted:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Item reply not found",
    )


@router.post("/keywords/import", response_model=KeywordImportResponse)
async def import_reply_keywords(
    payload: list[KeywordImportRequest],
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> KeywordImportResponse:
    del token
    with get_db(db_path) as conn:
        for entry in payload:
            _ = _insert_keyword_row(conn, entry)
    return KeywordImportResponse(imported=len(payload))


@router.get("/keywords/export", response_model=KeywordExportResponse)
async def export_reply_keywords(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> KeywordExportResponse:
    del token
    with get_db(db_path) as conn:
        keyword_rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT id, pattern, reply_content, NULL AS item_id, is_regex, enabled FROM keywords ORDER BY id"
            ).fetchall(),
        )
        item_keyword_rows = cast(
            list[sqlite3.Row],
            conn.execute(
                "SELECT id, pattern, reply_content, item_id, is_regex, enabled FROM item_keywords ORDER BY id"
            ).fetchall(),
        )
    return KeywordExportResponse(
        keywords=[_map_keyword_row(row, "general") for row in keyword_rows],
        item_keywords=[_map_keyword_row(row, "item") for row in item_keyword_rows],
    )


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
