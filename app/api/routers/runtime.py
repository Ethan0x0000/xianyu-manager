from __future__ import annotations

from html import escape
import logging
import os
import sqlite3
import tempfile
from collections import deque
from pathlib import Path
from typing import Annotated, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import RuntimeAccountResponse
from app.db.connection import get_db
from app.runtime.account_registry import DuplicateAccountError, get_registry

router = APIRouter(tags=["runtime"])

LOG_BUFFER: deque[str] = deque(maxlen=2000)
LOG_FORMATTER = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
SQLITE_HEADER = b"SQLite format 3\x00"
CAPTCHA_SESSIONS: dict[str, dict[str, object]] = {}


class _RuntimeLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:
            self.handleError(record)


def _ensure_runtime_log_handler() -> None:
    root_logger = logging.getLogger()
    if any(isinstance(handler, _RuntimeLogHandler) for handler in root_logger.handlers):
        return

    handler = _RuntimeLogHandler()
    handler.setFormatter(LOG_FORMATTER)
    root_logger.addHandler(handler)


_ensure_runtime_log_handler()


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


def _list_table_names(db_path: str) -> list[str]:
    with get_db(db_path) as conn:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall(),
        )
    return [str(cast(object, row["name"])) for row in rows]


def _require_table_name(db_path: str, table_name: str) -> str:
    available_tables = set(_list_table_names(db_path))
    if table_name not in available_tables:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    return table_name


def _table_columns(db_path: str, table_name: str) -> list[str]:
    with get_db(db_path) as conn:
        rows = cast(
            list[sqlite3.Row],
            conn.execute(f'PRAGMA table_info("{table_name}")').fetchall(),
        )
    return [str(cast(object, row["name"])) for row in rows]


def _table_page_payload(
    db_path: str,
    table_name: str,
    page: int,
    page_size: int,
) -> dict[str, object]:
    safe_table_name = _require_table_name(db_path, table_name)
    offset = (page - 1) * page_size
    with get_db(db_path) as conn:
        total = cast(
            int,
            conn.execute(f'SELECT COUNT(*) FROM "{safe_table_name}"').fetchone()[0],
        )
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                f'SELECT * FROM "{safe_table_name}" ORDER BY rowid DESC LIMIT ? OFFSET ?',
                (page_size, offset),
            ).fetchall(),
        )

    row_dicts = [dict(row) for row in rows]
    return {
        "table": safe_table_name,
        "rows": row_dicts,
        "columns": _table_columns(db_path, safe_table_name),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _risk_logs_payload(
    db_path: str,
    account_id: str | None,
    page: int,
    page_size: int,
) -> dict[str, object]:
    offset = (page - 1) * page_size
    filters: list[str] = []
    params: list[object] = []
    if account_id:
        filters.append("account_id = ?")
        params.append(account_id)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    with get_db(db_path) as conn:
        total = cast(
            int,
            conn.execute(
                f"SELECT COUNT(*) FROM risk_logs {where_clause}",
                tuple(params),
            ).fetchone()[0],
        )
        rows = cast(
            list[sqlite3.Row],
            conn.execute(
                f"""
                SELECT id, account_id, event_type, details, created_at
                FROM risk_logs
                {where_clause}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall(),
        )

    return {
        "logs": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _clear_risk_logs(db_path: str) -> int:
    with get_db(db_path) as conn:
        total = cast(int, conn.execute("SELECT COUNT(*) FROM risk_logs").fetchone()[0])
        _ = conn.execute("DELETE FROM risk_logs")
    return total


def _read_recent_logs(level: str | None, limit: int) -> list[str]:
    normalized_level = (level or "").strip().upper()
    lines = list(LOG_BUFFER)
    if normalized_level:
        lines = [line for line in lines if line.startswith(normalized_level)]
    return lines[-limit:]


def _captcha_payload(session_id: str | None) -> dict[str, object]:
    if not session_id:
        return {"active": False}
    session = CAPTCHA_SESSIONS.get(session_id)
    if session is None:
        return {"active": False, "session_id": session_id}
    return {
        "active": bool(session["active"]),
        "session_id": session_id,
    }


def _create_captcha_session() -> dict[str, object]:
    session_id = uuid4().hex
    CAPTCHA_SESSIONS[session_id] = {
        "active": True,
        "completed": False,
        "has_websocket": True,
    }
    return {"session_id": session_id}


def _backup_file_response(db_path: str) -> FileResponse:
    backup_path = Path(db_path)
    if not backup_path.exists():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Backup export is unavailable",
        )
    return FileResponse(
        path=str(backup_path),
        filename=backup_path.name,
        media_type="application/octet-stream",
    )


async def _restore_backup_file(
    db_path: str, upload: UploadFile | None
) -> dict[str, object]:
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A SQLite backup file is required",
        )

    content = await upload.read()
    if not content.startswith(SQLITE_HEADER):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded backup must be a SQLite database",
        )

    resolved_db_path = Path(db_path)
    resolved_db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        suffix=resolved_db_path.suffix or ".db",
        dir=str(resolved_db_path.parent),
    )
    os.close(fd)
    try:
        _ = Path(temp_path).write_bytes(content)
        os.replace(temp_path, resolved_db_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return {"status": "restored"}


@router.get("/api/runtime/accounts", response_model=list[RuntimeAccountResponse])
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
        account_id = str(cast(object, row["account_id"]))
        entry = registry.get_account(account_id)
        results.append(
            RuntimeAccountResponse(
                account_id=account_id,
                enabled=bool(entry.enabled)
                if entry
                else bool(cast(object, row["enabled"])),
                runtime_registered=entry is not None,
                runtime_active=bool(entry and entry.runtime_instance),
                username=str(row["username"] or ""),
                notes=str(row["notes"] or ""),
            )
        )
    return results


@router.post(
    "/api/runtime/accounts/{account_id}/start", response_model=RuntimeAccountResponse
)
async def start_account(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> RuntimeAccountResponse:
    del token
    row = _load_account_row(db_path, account_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
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


@router.post(
    "/api/runtime/accounts/{account_id}/stop", response_model=RuntimeAccountResponse
)
async def stop_account(
    account_id: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> RuntimeAccountResponse:
    del token
    row = _load_account_row(db_path, account_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
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


@router.get("/api/logs")
async def list_logs(
    token: Annotated[str, Depends(verify_token)],
    level: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> dict[str, object]:
    del token
    return {"logs": _read_recent_logs(level, limit)}


@router.get("/api/logs/export")
async def export_logs(
    token: Annotated[str, Depends(verify_token)],
    level: str | None = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 1000,
) -> PlainTextResponse:
    del token
    response = PlainTextResponse("\n".join(_read_recent_logs(level, limit)))
    response.headers["content-disposition"] = (
        'attachment; filename="xianyu-manager.log"'
    )
    return response


@router.get("/api/risk-logs")
async def list_risk_logs(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    account_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 20,
) -> dict[str, object]:
    del token
    return _risk_logs_payload(db_path, account_id, page, page_size)


@router.delete("/api/risk-logs")
async def clear_risk_logs(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, int]:
    del token
    return {"deleted": _clear_risk_logs(db_path)}


@router.get("/api/backup/export")
async def export_backup(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> FileResponse:
    del token
    return _backup_file_response(db_path)


@router.post("/api/backup/import")
async def import_backup(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    file: Annotated[UploadFile | None, File()] = None,
    backup_file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, object]:
    del token
    upload = file or backup_file
    return await _restore_backup_file(db_path, upload)


@router.get("/api/data/tables")
async def list_tables(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, list[str]]:
    del token
    return {"tables": _list_table_names(db_path)}


@router.get("/api/data/table/{table_name}")
async def browse_table(
    table_name: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 20,
) -> dict[str, object]:
    del token
    return _table_page_payload(db_path, table_name, page, page_size)


@router.delete("/api/data/table/{table_name}")
async def clear_table(
    table_name: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    safe_table_name = _require_table_name(db_path, table_name)
    with get_db(db_path) as conn:
        cursor = conn.execute(f'DELETE FROM "{safe_table_name}"')
        deleted = cursor.rowcount
    return {"table": safe_table_name, "deleted": deleted}


@router.get("/api/captcha/status")
async def captcha_status(
    token: Annotated[str, Depends(verify_token)],
    session_id: str | None = None,
) -> dict[str, object]:
    del token
    return _captcha_payload(session_id)


@router.post("/api/captcha/start")
async def start_captcha(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    return _create_captcha_session()


@router.post("/system/reload-cache", include_in_schema=False)
async def reload_cache(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Cache reload is not implemented in the dev branch yet",
    )


@router.post("/api/update/restart", include_in_schema=False)
async def restart_system(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="System restart is not implemented in the dev branch yet",
    )


@router.post("/api/runtime/cache/clear")
async def runtime_cache_clear(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Runtime cache clear is not implemented in the dev branch yet",
    )


@router.post("/api/runtime/restart")
async def runtime_restart(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Runtime restart is not implemented in the dev branch yet",
    )


@router.post("/items/search_multiple", include_in_schema=False)
async def search_items_stub(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Legacy multi-page item search is not implemented in the dev branch yet",
    )


@router.post("/api/item-search/start")
async def start_item_search(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Item search task startup is not implemented in the dev branch yet",
    )


@router.get("/admin/risk-control-logs", include_in_schema=False)
async def legacy_list_risk_logs(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    cookie_id: str | None = None,
    event_type: str | None = None,
    trigger_scene: str | None = None,
    processing_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    session_id: str | None = None,
    result_code: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    del (
        token,
        event_type,
        trigger_scene,
        processing_status,
        date_from,
        date_to,
        session_id,
        result_code,
    )
    page = (offset // limit) + 1
    payload = _risk_logs_payload(db_path, cookie_id, page, limit)
    return {
        "success": True,
        "data": payload["logs"],
        "total": payload["total"],
        "limit": limit,
        "offset": offset,
    }


@router.delete("/admin/risk-control-logs/{log_id}", include_in_schema=False)
async def legacy_delete_risk_log(
    log_id: int,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    with get_db(db_path) as conn:
        cursor = conn.execute("DELETE FROM risk_logs WHERE id = ?", (log_id,))
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk log not found",
        )
    return {"success": True, "deleted": 1}


@router.delete("/admin/data/risk_control_logs", include_in_schema=False)
async def legacy_clear_risk_logs(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    return {"success": True, "deleted": _clear_risk_logs(db_path)}


@router.get("/admin/backup/download", include_in_schema=False)
async def legacy_export_backup_download(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> FileResponse:
    del token
    return _backup_file_response(db_path)


@router.post("/admin/backup/upload", include_in_schema=False)
async def legacy_import_backup_upload(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
    backup_file: Annotated[UploadFile | None, File()] = None,
) -> dict[str, object]:
    del token
    return await _restore_backup_file(db_path, backup_file)


@router.get("/admin/data/{table_name}", include_in_schema=False)
async def legacy_browse_table(
    table_name: str,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> dict[str, object]:
    del token
    payload = _table_page_payload(db_path, table_name, page=1, page_size=500)
    return {
        "success": True,
        "data": payload["rows"],
        "columns": payload["columns"],
        "total": payload["total"],
    }


@router.get("/api/captcha/sessions", include_in_schema=False)
async def legacy_captcha_sessions() -> dict[str, object]:
    sessions = [
        {
            "session_id": session_id,
            "completed": bool(data.get("completed", False)),
            "has_websocket": bool(data.get("has_websocket", True)),
        }
        for session_id, data in CAPTCHA_SESSIONS.items()
    ]
    return {"success": True, "count": len(sessions), "sessions": sessions}


@router.get("/api/captcha/status/{session_id}", include_in_schema=False)
async def legacy_captcha_status(session_id: str) -> dict[str, object]:
    session = CAPTCHA_SESSIONS.get(session_id)
    if session is None:
        return {
            "success": True,
            "session_id": session_id,
            "completed": False,
            "session_exists": False,
            "active": False,
        }
    return {
        "success": True,
        "session_id": session_id,
        "completed": bool(session.get("completed", False)),
        "session_exists": True,
        "active": bool(session.get("active", False)),
    }


@router.get("/api/captcha/control/{session_id:path}", include_in_schema=False)
async def legacy_captcha_control(
    session_id: str,
    embed: bool = False,
) -> HTMLResponse:
    del embed
    safe_session_id = escape(session_id)
    html = f"""
    <html>
      <head><title>Captcha Control</title></head>
      <body>
        <main>
          <h1>Captcha session ready</h1>
          <p>session_id: {safe_session_id}</p>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)


__all__ = ["router"]
