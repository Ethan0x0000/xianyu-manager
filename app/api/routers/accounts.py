from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import AccountCreateRequest, AccountResponse, DeleteResponse
from app.db.connection import get_db

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _map_account(row: sqlite3.Row) -> AccountResponse:
    return AccountResponse(
        account_id=str(row["account_id"]),
        username=str(row["username"] or ""),
        notes=str(row["notes"] or ""),
        enabled=bool(row["enabled"]),
        show_browser=bool(row["show_browser"]),
        has_cookie=bool(row["cookie_str"]),
        created_at=str(row["created_at"]) if row["created_at"] is not None else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] is not None else None,
    )


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[AccountResponse]:
    del token
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT account_id, cookie_str, username, notes, enabled, show_browser, created_at, updated_at
            FROM xianyu_accounts
            ORDER BY account_id
            """
        ).fetchall()
    return [_map_account(cast(sqlite3.Row, row)) for row in rows]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def add_account(
    payload: AccountCreateRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AccountResponse:
    del token
    try:
        with get_db(db_path) as conn:
            _ = conn.execute(
                """
                INSERT INTO xianyu_accounts (
                    account_id, cookie_str, username, password, notes, enabled, show_browser
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.account_id,
                    payload.cookie_str,
                    payload.username,
                    payload.password,
                    payload.notes,
                    int(payload.enabled),
                    int(payload.show_browser),
                ),
            )
            row = cast(
                sqlite3.Row | None,
                conn.execute(
                    """
                    SELECT account_id, cookie_str, username, notes, enabled, show_browser, created_at, updated_at
                    FROM xianyu_accounts
                    WHERE account_id = ?
                    """,
                    (payload.account_id,),
                ).fetchone(),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Account '{payload.account_id}' already exists",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account insert failed",
        )
    return _map_account(row)


@router.delete("/{account_id}", response_model=DeleteResponse)
async def remove_account(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> DeleteResponse:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM xianyu_accounts WHERE account_id = ?",
            (account_id,),
        )

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    return DeleteResponse()


__all__ = ["router"]
