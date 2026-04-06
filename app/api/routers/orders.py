from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import get_db_path, verify_token
from app.db.connection import get_db

orders_router = APIRouter(tags=["orders"])


class OrderBatchDeleteRequest(BaseModel):
    account_id: str
    order_ids: list[str]


def _map_order_row(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def _fetch_order_row(conn: sqlite3.Connection, order_id: str) -> sqlite3.Row | None:
    return cast(
        sqlite3.Row | None,
        conn.execute(
            "SELECT * FROM orders WHERE order_id = ? LIMIT 1",
            (order_id,),
        ).fetchone(),
    )


def _format_amount(value: object | None) -> str:
    if value in (None, ""):
        return "0.00"

    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return "0.00"

    return str(amount.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))


@orders_router.get("/api/orders")
async def list_orders(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    account_id: Annotated[str | None, Query()] = None,
    order_status: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
) -> dict[str, object]:
    del token
    conditions: list[str] = []
    params: list[object] = []

    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if order_status:
        conditions.append("status = ?")
        params.append(order_status)

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    with get_db(db_path) as conn:
        total = cast(
            int,
            conn.execute(
                f"SELECT COUNT(*) FROM orders{where_clause}",
                tuple(params),
            ).fetchone()[0],
        )
        rows = conn.execute(
            f"SELECT * FROM orders{where_clause} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            tuple([*params, page_size, offset]),
        ).fetchall()

    return {
        "orders": [_map_order_row(row) for row in cast(list[sqlite3.Row], rows)],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@orders_router.get("/api/orders/{order_id}")
async def get_order(
    order_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    with get_db(db_path) as conn:
        row = _fetch_order_row(conn, order_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return _map_order_row(row)


@orders_router.post("/api/orders/{order_id}/refresh")
async def refresh_order(
    order_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, str]:
    del token
    with get_db(db_path) as conn:
        row = _fetch_order_row(conn, order_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return {"status": "triggered", "order_id": order_id}


@orders_router.delete("/api/orders")
async def delete_orders_batch(
    payload: OrderBatchDeleteRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, int]:
    del token
    if not payload.order_ids:
        return {"deleted": 0}

    placeholders = ", ".join("?" for _ in payload.order_ids)
    with get_db(db_path) as conn:
        deleted = conn.execute(
            f"DELETE FROM orders WHERE account_id = ? AND order_id IN ({placeholders})",
            tuple([payload.account_id, *payload.order_ids]),
        ).rowcount
    return {"deleted": deleted}


@orders_router.get("/api/sales/summary")
async def get_sales_summary(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    today = date.today().isoformat()

    with get_db(db_path) as conn:
        row = cast(
            sqlite3.Row,
            conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN DATE(created_at) = ? THEN CAST(amount AS REAL) ELSE 0 END), 0) AS today_amount,
                    COALESCE(SUM(CASE WHEN DATE(created_at) = ? THEN 1 ELSE 0 END), 0) AS today_orders,
                    COALESCE(SUM(CAST(amount AS REAL)), 0) AS total_amount,
                    COUNT(*) AS total_orders
                FROM orders
                """,
                (today, today),
            ).fetchone(),
        )

    return {
        "today_amount": _format_amount(cast(object | None, row["today_amount"])),
        "today_orders": cast(int, row["today_orders"]),
        "total_amount": _format_amount(cast(object | None, row["total_amount"])),
        "total_orders": cast(int, row["total_orders"]),
    }


@orders_router.get("/api/sales/trend")
async def get_sales_trend(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    days: Annotated[int, Query(ge=1)] = 7,
) -> list[dict[str, object]]:
    del token
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                DATE(created_at) AS order_date,
                COALESCE(SUM(CAST(amount AS REAL)), 0) AS amount,
                COUNT(*) AS count
            FROM orders
            WHERE DATE(created_at) BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    grouped = {
        cast(str, row["order_date"]): {
            "amount": row["amount"],
            "count": cast(int, row["count"]),
        }
        for row in cast(list[sqlite3.Row], rows)
    }

    trend: list[dict[str, object]] = []
    for day_offset in range(days):
        current_date = (start_date + timedelta(days=day_offset)).isoformat()
        payload = grouped.get(current_date, {"amount": 0, "count": 0})
        trend.append(
            {
                "date": current_date,
                "amount": _format_amount(payload["amount"]),
                "count": cast(int, payload["count"]),
            }
        )
    return trend


__all__ = ["orders_router"]
