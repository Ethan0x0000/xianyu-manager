from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_path, verify_token
from app.db.connection import get_db

router = APIRouter(prefix="/api/shipping", tags=["shipping"])
delivery_router = APIRouter(prefix="/api/delivery", tags=["shipping"])


def _list_rules(db_path: str) -> list[dict[str, object]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                dr.id,
                dr.item_id,
                dr.priority,
                dr.enabled,
                dr.account_id,
                dc.id AS card_id,
                dc.name AS card_name,
                dc.content_type
            FROM delivery_rules dr
            LEFT JOIN delivery_cards dc ON dc.id = dr.card_id
            ORDER BY dr.priority DESC, dr.id ASC
            """
        ).fetchall()
    return [
        {key: row[key] for key in row.keys()} for row in cast(list[sqlite3.Row], rows)
    ]


def _list_logs(db_path: str) -> list[dict[str, object]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, order_id, card_id, status, created_at
            FROM delivery_logs
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()
    return [
        {key: row[key] for key in row.keys()} for row in cast(list[sqlite3.Row], rows)
    ]


@router.get("/rules")
async def list_shipping_rules(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"rules": _list_rules(db_path)}


@router.get("/logs")
async def list_shipping_logs(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"logs": _list_logs(db_path)}


@delivery_router.get("/rules")
async def list_delivery_rules_alias(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"rules": _list_rules(db_path)}


@delivery_router.get("/logs/recent")
async def list_delivery_logs_alias(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"logs": _list_logs(db_path)}


__all__ = ["delivery_router", "router"]
