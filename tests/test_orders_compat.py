from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from datetime import date, timedelta
from typing import cast
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from app.db.connection import get_db
from tests.helpers import make_settings, make_test_db

AUTH_TOKEN = "compat-token"


@pytest.fixture
def compat_client() -> Iterator[tuple[TestClient, str]]:
    db_path = make_test_db()
    store = SessionStore()
    _ = store.create_session(AUTH_TOKEN, ttl_seconds=60)

    with patch("app.api.dependencies.get_session_store", return_value=store):
        app = create_app(settings=make_settings(db_path=db_path))
        with TestClient(app) as client:
            yield client, db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def _insert_order(
    db_path: str,
    *,
    order_id: str,
    account_id: str,
    status: str,
    amount: str,
    item_id: str = "item-1",
    buyer_id: str = "buyer-1",
    created_at: str = "2026-04-06 10:00:00",
    updated_at: str = "2026-04-06 10:00:00",
) -> int:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO orders (
                order_id, item_id, buyer_id, status, amount, account_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                item_id,
                buyer_id,
                status,
                amount,
                account_id,
                created_at,
                updated_at,
            ),
        )
        row_id = cursor.lastrowid
        assert row_id is not None
        return row_id


def _fetch_order(db_path: str, order_id: str) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT * FROM orders WHERE order_id = ? LIMIT 1",
                (order_id,),
            ).fetchone(),
        )


def test_list_orders_supports_filters_and_pagination(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="paid",
        amount="10.00",
        updated_at="2026-04-06 10:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-2",
        account_id="acct-1",
        status="paid",
        amount="20.00",
        updated_at="2026-04-06 11:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-3",
        account_id="acct-1",
        status="pending",
        amount="30.00",
        updated_at="2026-04-06 12:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-4",
        account_id="acct-2",
        status="paid",
        amount="40.00",
        updated_at="2026-04-06 13:00:00",
    )

    response = client.get(
        "/api/orders",
        headers=_auth_headers(),
        params={"account_id": "acct-1", "status": "paid", "page": 2, "page_size": 1},
    )

    assert response.status_code == 200
    assert response.json() == {
        "orders": [
            {
                "id": 1,
                "order_id": "order-1",
                "item_id": "item-1",
                "buyer_id": "buyer-1",
                "status": "paid",
                "amount": "10.00",
                "account_id": "acct-1",
                "created_at": "2026-04-06 10:00:00",
                "updated_at": "2026-04-06 10:00:00",
            }
        ],
        "total": 2,
        "page": 2,
        "page_size": 1,
    }


def test_get_order_detail_returns_row(compat_client: tuple[TestClient, str]) -> None:
    client, db_path = compat_client
    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="pending",
        amount="88.00",
        item_id="item-9",
        buyer_id="buyer-9",
    )

    response = client.get("/api/orders/order-1", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "order_id": "order-1",
        "item_id": "item-9",
        "buyer_id": "buyer-9",
        "status": "pending",
        "amount": "88.00",
        "account_id": "acct-1",
        "created_at": "2026-04-06 10:00:00",
        "updated_at": "2026-04-06 10:00:00",
    }


def test_get_missing_order_returns_404(compat_client: tuple[TestClient, str]) -> None:
    client, _ = compat_client

    response = client.get("/api/orders/missing-order", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_refresh_existing_order_returns_triggered_status(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="pending",
        amount="10.00",
    )

    response = client.post("/api/orders/order-1/refresh", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "triggered", "order_id": "order-1"}


def test_refresh_missing_order_returns_404(
    compat_client: tuple[TestClient, str],
) -> None:
    client, _ = compat_client

    response = client.post("/api/orders/missing-order/refresh", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_batch_delete_orders_removes_only_matching_account_rows(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="paid",
        amount="10.00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-2",
        account_id="acct-1",
        status="paid",
        amount="20.00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-3",
        account_id="acct-1",
        status="paid",
        amount="30.00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-4",
        account_id="acct-2",
        status="paid",
        amount="40.00",
    )

    response = client.request(
        "DELETE",
        "/api/orders",
        headers=_auth_headers(),
        json={"account_id": "acct-1", "order_ids": ["order-1", "order-2", "order-4"]},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    assert _fetch_order(db_path, "order-1") is None
    assert _fetch_order(db_path, "order-2") is None
    assert _fetch_order(db_path, "order-3") is not None
    assert _fetch_order(db_path, "order-4") is not None


def test_sales_summary_returns_aggregated_amounts(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="paid",
        amount="10.50",
        created_at=f"{today} 09:00:00",
        updated_at=f"{today} 09:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-2",
        account_id="acct-1",
        status="pending",
        amount="5.25",
        created_at=f"{today} 10:00:00",
        updated_at=f"{today} 10:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-3",
        account_id="acct-2",
        status="paid",
        amount="7.00",
        created_at=f"{yesterday} 11:00:00",
        updated_at=f"{yesterday} 11:00:00",
    )

    response = client.get("/api/sales/summary", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "today_amount": "15.75",
        "today_orders": 2,
        "total_amount": "22.75",
        "total_orders": 3,
    }


def test_sales_trend_returns_requested_number_of_days_with_zero_fills(
    compat_client: tuple[TestClient, str],
) -> None:
    client, db_path = compat_client
    today = date.today()
    day_minus_1 = today - timedelta(days=1)
    day_minus_3 = today - timedelta(days=3)

    _ = _insert_order(
        db_path,
        order_id="order-1",
        account_id="acct-1",
        status="paid",
        amount="5.00",
        created_at=f"{day_minus_3.isoformat()} 09:00:00",
        updated_at=f"{day_minus_3.isoformat()} 09:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-2",
        account_id="acct-1",
        status="paid",
        amount="2.50",
        created_at=f"{day_minus_3.isoformat()} 10:00:00",
        updated_at=f"{day_minus_3.isoformat()} 10:00:00",
    )
    _ = _insert_order(
        db_path,
        order_id="order-3",
        account_id="acct-2",
        status="pending",
        amount="1.25",
        created_at=f"{day_minus_1.isoformat()} 11:00:00",
        updated_at=f"{day_minus_1.isoformat()} 11:00:00",
    )

    response = client.get(
        "/api/sales/trend",
        headers=_auth_headers(),
        params={"days": 4},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"date": day_minus_3.isoformat(), "amount": "7.50", "count": 2},
        {"date": (today - timedelta(days=2)).isoformat(), "amount": "0.00", "count": 0},
        {"date": day_minus_1.isoformat(), "amount": "1.25", "count": 1},
        {"date": today.isoformat(), "amount": "0.00", "count": 0},
    ]
