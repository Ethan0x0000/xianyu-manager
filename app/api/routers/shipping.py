from __future__ import annotations

import json
import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.api.dependencies import get_db_path, verify_token
from app.db.connection import get_db

router = APIRouter(prefix="/api/shipping", tags=["shipping"])
delivery_router = APIRouter(prefix="/api/delivery", tags=["shipping"])
cards_router = APIRouter(prefix="/api/cards", tags=["cards"])

_ALLOWED_CARD_CONTENT_TYPES = frozenset({"text", "data", "api", "image", "yifan"})


class DeliveryCardRequest(BaseModel):
    name: str
    content_type: str
    content: str
    account_id: str


class DeliveryRuleCreateRequest(BaseModel):
    item_id: str
    card_id: int
    account_id: str
    priority: int = 0
    enabled: bool = True


class DeliveryRuleUpdateRequest(BaseModel):
    card_id: int | None = None
    priority: int | None = None
    enabled: bool | None = None


def _map_row(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _map_delivery_rule_row(row: sqlite3.Row) -> dict[str, object]:
    payload = _map_row(row)
    payload["enabled"] = bool(payload["enabled"])
    return payload


def _fetch_card_row(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT * FROM delivery_cards WHERE id = ? LIMIT 1", (card_id,)
        ).fetchone(),
    )


def _fetch_delivery_rule_row(
    conn: sqlite3.Connection, rule_id: int
) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT * FROM delivery_rules WHERE id = ? LIMIT 1", (rule_id,)
        ).fetchone(),
    )


def _require_card_row(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row:
    row = _fetch_card_row(conn, card_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    return row


def _require_delivery_rule_row(conn: sqlite3.Connection, rule_id: int) -> sqlite3.Row:
    row = _fetch_delivery_rule_row(conn, rule_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery rule not found",
        )
    return row


def _require_matching_card_account(card_row: sqlite3.Row, account_id: str) -> None:
    card_account_id = str(cast(str | None, card_row["account_id"]) or "")
    if card_account_id != account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Card account does not match the requested account",
        )


def _item_account_id(conn: sqlite3.Connection, item_id: str) -> str | None:
    row = cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT account_id FROM items WHERE item_id = ? ORDER BY id DESC LIMIT 1",
            (item_id,),
        ).fetchone(),
    )
    if row is None:
        return None
    return str(cast(str | None, row["account_id"]) or "")


def _require_matching_item_account(
    conn: sqlite3.Connection,
    item_id: str,
    account_id: str,
) -> None:
    item_account_id = _item_account_id(conn, item_id)
    if item_account_id is None:
        return
    if item_account_id != account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Item account does not match the requested account",
        )


def _validate_yifan_content(content: str) -> None:
    try:
        parsed = cast(object, json.loads(content))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Yifan content must be valid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Yifan content must be a JSON object",
        )

    payload = cast(dict[str, object], parsed)
    for field_name in ("callback_url", "merchant_id"):
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Yifan content requires non-empty {field_name}",
            )


def _normalize_content_type(content_type: str, content: str) -> str:
    normalized = content_type.strip().lower()
    if normalized not in _ALLOWED_CARD_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=("content_type must be one of: text, data, api, image, yifan"),
        )
    if normalized == "yifan":
        _validate_yifan_content(content)
    return normalized


def _list_cards(db_path: str, account_id: str) -> list[dict[str, object]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM delivery_cards WHERE account_id = ? ORDER BY id ASC",
            (account_id,),
        ).fetchall()
    return [_map_row(row) for row in cast(list[sqlite3.Row], rows)]


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
    return [_map_row(row) for row in cast(list[sqlite3.Row], rows)]


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
    return [_map_row(row) for row in cast(list[sqlite3.Row], rows)]


@cards_router.get("")
async def list_cards(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    account_id: Annotated[str, Query()],
) -> dict[str, object]:
    del token
    return {"cards": _list_cards(db_path, account_id)}


@cards_router.get("/{card_id}")
async def get_card(
    card_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    with get_db(db_path) as conn:
        row = _fetch_card_row(conn, card_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    return _map_row(row)


@cards_router.post("", status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: DeliveryCardRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    content_type = _normalize_content_type(payload.content_type, payload.content)
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO delivery_cards (name, content_type, content, account_id) VALUES (?, ?, ?, ?)",
            (payload.name, content_type, payload.content, payload.account_id),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        row = _require_card_row(conn, row_id)
    return _map_row(row)


@cards_router.put("/{card_id}")
async def update_card(
    card_id: int,
    payload: DeliveryCardRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    content_type = _normalize_content_type(payload.content_type, payload.content)
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE delivery_cards
            SET name = ?, content_type = ?, content = ?, account_id = ?
            WHERE id = ?
            """,
            (payload.name, content_type, payload.content, payload.account_id, card_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found",
            )
        row = _require_card_row(conn, card_id)
    return _map_row(row)


@cards_router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    with get_db(db_path) as conn:
        deleted = conn.execute(
            "DELETE FROM delivery_cards WHERE id = ?",
            (card_id,),
        ).rowcount
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@delivery_router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_delivery_rule(
    payload: DeliveryRuleCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    with get_db(db_path) as conn:
        card_row = _require_card_row(conn, payload.card_id)
        _require_matching_card_account(card_row, payload.account_id)
        _require_matching_item_account(conn, payload.item_id, payload.account_id)
        cursor = conn.execute(
            """
            INSERT INTO delivery_rules (item_id, card_id, priority, enabled, account_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.item_id,
                payload.card_id,
                payload.priority,
                int(payload.enabled),
                payload.account_id,
            ),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        row = _require_delivery_rule_row(conn, row_id)
    return _map_delivery_rule_row(row)


@delivery_router.put("/rules/{rule_id}")
async def update_delivery_rule(
    rule_id: int,
    payload: DeliveryRuleUpdateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    assignments: list[str] = []
    params: list[object] = []
    if payload.card_id is not None:
        assignments.append("card_id = ?")
        params.append(payload.card_id)
    if payload.priority is not None:
        assignments.append("priority = ?")
        params.append(payload.priority)
    if payload.enabled is not None:
        assignments.append("enabled = ?")
        params.append(int(payload.enabled))
    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one delivery rule field must be provided",
        )

    with get_db(db_path) as conn:
        existing_rule = _require_delivery_rule_row(conn, rule_id)
        rule_account_id = str(cast(str | None, existing_rule["account_id"]) or "")
        if payload.card_id is not None:
            card_row = _require_card_row(conn, payload.card_id)
            _require_matching_card_account(card_row, rule_account_id)
        sql = "UPDATE delivery_rules SET " + ", ".join(assignments) + " WHERE id = ?"
        cursor = conn.execute(sql, tuple([*params, rule_id]))
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery rule not found",
            )
        row = _require_delivery_rule_row(conn, rule_id)
    return _map_delivery_rule_row(row)


@delivery_router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_delivery_rule(
    rule_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> Response:
    del token
    with get_db(db_path) as conn:
        deleted = conn.execute(
            "DELETE FROM delivery_rules WHERE id = ?",
            (rule_id,),
        ).rowcount
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery rule not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@delivery_router.get("/logs/recent")
async def list_delivery_logs_alias(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"logs": _list_logs(db_path)}


__all__ = ["cards_router", "delivery_router", "router"]
