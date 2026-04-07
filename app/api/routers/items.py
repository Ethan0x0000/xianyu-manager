from __future__ import annotations

import logging
import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.api.dependencies import get_db_path, verify_token
from app.db.connection import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"])


class ItemUpdateRequest(BaseModel):
    title: str | None = None
    price: str | None = None
    status: str | None = None
    raw_data: str | None = None


class ItemBatchDeleteRequest(BaseModel):
    account_id: str
    item_ids: list[str]


class ItemSyncRequest(BaseModel):
    account_id: str | None = None


def _map_item_row(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _fetch_item_row(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    item_id: str,
) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT * FROM items WHERE account_id = ? AND item_id = ? LIMIT 1",
            (account_id, item_id),
        ).fetchone(),
    )


@router.get("")
async def list_items(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    account_id: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
) -> dict[str, object]:
    del token
    logger.info(
        "Listing items: account_id=%s, q=%s, page=%d, page_size=%d",
        account_id or "(all)",
        q or "(none)",
        page,
        page_size,
    )
    conditions: list[str] = []
    params: list[object] = []
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if q:
        conditions.append("(title LIKE ? OR item_id LIKE ?)")
        params.append(f"%{q}%")
        params.append(f"%{q}%")

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    with get_db(db_path) as conn:
        total = cast(
            int,
            conn.execute(
                f"SELECT COUNT(*) FROM items{where_clause}",
                tuple(params),
            ).fetchone()[0],
        )
        rows = conn.execute(
            f"SELECT * FROM items{where_clause} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            tuple([*params, page_size, offset]),
        ).fetchall()
    logger.debug("Items query returned %d / %d results", len(rows), total)
    return {
        "items": [_map_item_row(row) for row in cast(list[sqlite3.Row], rows)],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/sync")
async def trigger_item_sync(
    payload: ItemSyncRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, str]:
    del token
    del db_path
    logger.info("Item sync triggered for account_id=%s", payload.account_id or "(none)")
    if not payload.account_id:
        logger.warning("Item sync rejected: no account_id provided")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return {"status": "triggered", "account_id": payload.account_id}


@router.put("/{account_id}/{item_id}")
async def update_item(
    account_id: str,
    item_id: str,
    payload: ItemUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    logger.info(
        "Updating item: account_id=%s, item_id=%s, fields=%s",
        account_id,
        item_id,
        [
            f
            for f, v in [
                ("title", payload.title),
                ("price", payload.price),
                ("status", payload.status),
                ("raw_data", payload.raw_data),
            ]
            if v is not None
        ],
    )
    assignments: list[str] = []
    params: list[object] = []
    for field_name, value in (
        ("title", payload.title),
        ("price", payload.price),
        ("status", payload.status),
        ("raw_data", payload.raw_data),
    ):
        if value is not None:
            assignments.append(f"{field_name} = ?")
            params.append(value)
    assignments.append("updated_at = CURRENT_TIMESTAMP")

    with get_db(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE items SET {', '.join(assignments)} WHERE account_id = ? AND item_id = ?",
            tuple([*params, account_id, item_id]),
        )
        if cursor.rowcount == 0:
            logger.warning(
                "Item not found for update: account_id=%s, item_id=%s",
                account_id,
                item_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found",
            )
        row = _fetch_item_row(conn, account_id=account_id, item_id=item_id)

    assert row is not None
    logger.info(
        "Item updated successfully: account_id=%s, item_id=%s", account_id, item_id
    )
    return _map_item_row(row)


@router.delete("/{account_id}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    account_id: str,
    item_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    logger.info("Deleting item: account_id=%s, item_id=%s", account_id, item_id)
    with get_db(db_path) as conn:
        deleted = conn.execute(
            "DELETE FROM items WHERE account_id = ? AND item_id = ?",
            (account_id, item_id),
        ).rowcount
    if deleted == 0:
        logger.warning(
            "Item not found for deletion: account_id=%s, item_id=%s",
            account_id,
            item_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    logger.info("Item deleted: account_id=%s, item_id=%s", account_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("")
async def delete_items_batch(
    payload: ItemBatchDeleteRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, int]:
    del token
    if not payload.item_ids:
        logger.debug(
            "Batch delete called with empty item_ids for account_id=%s",
            payload.account_id,
        )
        return {"deleted": 0}

    logger.info(
        "Batch deleting %d items: account_id=%s, item_ids=%s",
        len(payload.item_ids),
        payload.account_id,
        payload.item_ids[:5] if len(payload.item_ids) > 5 else payload.item_ids,
    )
    placeholders = ", ".join("?" for _ in payload.item_ids)
    with get_db(db_path) as conn:
        deleted = conn.execute(
            f"DELETE FROM items WHERE account_id = ? AND item_id IN ({placeholders})",
            tuple([payload.account_id, *payload.item_ids]),
        ).rowcount
    logger.info(
        "Batch delete completed: %d items deleted for account_id=%s",
        deleted,
        payload.account_id,
    )
    return {"deleted": deleted}


@router.get("/{account_id}/{item_id}")
async def get_item(
    account_id: str,
    item_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    logger.debug("Fetching item: account_id=%s, item_id=%s", account_id, item_id)
    with get_db(db_path) as conn:
        row = _fetch_item_row(conn, account_id=account_id, item_id=item_id)
    if row is None:
        logger.warning("Item not found: account_id=%s, item_id=%s", account_id, item_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    return _map_item_row(row)


__all__ = ["router"]
