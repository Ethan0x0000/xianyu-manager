from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_db_path, verify_token
from app.db.connection import get_db

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("")
async def list_items(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    account_id: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    del token
    query = "SELECT * FROM items"
    params: tuple[object, ...] = ()
    if account_id:
        query += " WHERE account_id = ?"
        params = (account_id,)
    query += " ORDER BY updated_at DESC, id DESC"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return {
        "items": [
            {key: row[key] for key in row.keys()}
            for row in cast(list[sqlite3.Row], rows)
        ]
    }


@router.get("/{account_id}/{item_id}")
async def get_item(
    account_id: str,
    item_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE account_id = ? AND item_id = ? LIMIT 1",
            (account_id, item_id),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    row = cast(sqlite3.Row, row)
    return {key: row[key] for key in row.keys()}


__all__ = ["router"]
