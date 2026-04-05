from __future__ import annotations

import sqlite3
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import RuntimeAccountResponse
from app.db.connection import get_db
from app.runtime.account_registry import DuplicateAccountError, get_registry

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


def _load_account_row(db_path: str, account_id: str) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                """
                SELECT account_id, cookie_str, username, notes, enabled
                FROM xianyu_accounts
                WHERE account_id = ?
                LIMIT 1
                """,
                (account_id,),
            ).fetchone(),
        )


@router.get("/accounts", response_model=list[RuntimeAccountResponse])
async def list_runtime_accounts(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> list[RuntimeAccountResponse]:
    del token
    registry = get_registry()
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT account_id, username, notes, enabled FROM xianyu_accounts ORDER BY account_id"
        ).fetchall()

    results: list[RuntimeAccountResponse] = []
    for row in cast(list[sqlite3.Row], rows):
        account_id = str(row["account_id"])
        entry = registry.get_account(account_id)
        results.append(
            RuntimeAccountResponse(
                account_id=account_id,
                enabled=bool(entry.enabled) if entry else bool(row["enabled"]),
                runtime_registered=entry is not None,
                runtime_active=bool(entry and entry.runtime_instance),
                username=str(row["username"] or ""),
                notes=str(row["notes"] or ""),
            )
        )
    return results


@router.post("/accounts/{account_id}/start", response_model=RuntimeAccountResponse)
async def start_account(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> RuntimeAccountResponse:
    del token
    row = _load_account_row(db_path, account_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    registry = get_registry()
    entry = registry.get_account(account_id)
    if entry is None:
        try:
            entry = registry.add_account(
                account_id=account_id,
                cookie_str=str(row["cookie_str"] or ""),
                username=str(row["username"] or ""),
                notes=str(row["notes"] or ""),
            )
        except DuplicateAccountError:
            entry = registry.get_account(account_id)

    assert entry is not None
    registry.enable_account(account_id)
    with get_db(db_path) as conn:
        _ = conn.execute(
            "UPDATE xianyu_accounts SET enabled = 1 WHERE account_id = ?",
            (account_id,),
        )
    return RuntimeAccountResponse(
        account_id=account_id,
        enabled=True,
        runtime_registered=True,
        runtime_active=bool(entry.runtime_instance),
        username=str(row["username"] or ""),
        notes=str(row["notes"] or ""),
    )


@router.post("/accounts/{account_id}/stop", response_model=RuntimeAccountResponse)
async def stop_account(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> RuntimeAccountResponse:
    del token
    row = _load_account_row(db_path, account_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    registry = get_registry()
    entry = registry.get_account(account_id)
    if entry is not None:
        registry.disable_account(account_id)

    with get_db(db_path) as conn:
        _ = conn.execute(
            "UPDATE xianyu_accounts SET enabled = 0 WHERE account_id = ?",
            (account_id,),
        )
    return RuntimeAccountResponse(
        account_id=account_id,
        enabled=False,
        runtime_registered=entry is not None,
        runtime_active=bool(entry and entry.runtime_instance),
        username=str(row["username"] or ""),
        notes=str(row["notes"] or ""),
    )


__all__ = ["router"]
