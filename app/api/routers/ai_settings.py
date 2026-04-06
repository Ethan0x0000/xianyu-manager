from __future__ import annotations

from collections.abc import Mapping
import sqlite3
from typing import Annotated, TypedDict, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import AITestResponse, AISettingsResponse, AISettingsUpsertRequest
from app.db.connection import get_db
from app.services.ai_reply import AIReplyService
from app.shared.types import ServiceKey

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AISettingsValues(TypedDict):
    provider_type: str
    api_key: str
    base_url: str
    model_name: str
    system_prompt: str
    max_tokens: int
    enabled: bool


def _get_ai_reply_service(request: Request) -> AIReplyService:
    app = cast(FastAPI, request.app)
    container = cast(
        Mapping[str, object] | None,
        getattr(app.state, "container", None),
    )
    if container is None or ServiceKey.AI_REPLY.value not in container:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI reply service unavailable",
        )
    return cast(AIReplyService, container[ServiceKey.AI_REPLY.value])


def _load_ai_settings_row(db_path: str) -> sqlite3.Row | None:
    with get_db(db_path) as conn:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                """
                SELECT id, provider_type, api_key, base_url, model_name, system_prompt, max_tokens, enabled
                FROM ai_settings
                ORDER BY id
                LIMIT 1
                """
            ).fetchone(),
        )


def _mask_api_key(api_key: str) -> str:
    return "****" if api_key.strip() else ""


def _row_id(row: sqlite3.Row) -> int:
    return cast(int, row["id"])


def _row_string(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_int(row: sqlite3.Row, key: str) -> int:
    return cast(int, row[key])


def _row_bool(row: sqlite3.Row, key: str) -> bool:
    return bool(cast(int | bool, row[key]))


def _map_ai_settings_row(row: sqlite3.Row) -> AISettingsResponse:
    return AISettingsResponse(
        id=_row_id(row),
        provider_type=_row_string(row, "provider_type"),
        api_key=_mask_api_key(_row_string(row, "api_key")),
        base_url=_row_string(row, "base_url"),
        model_name=_row_string(row, "model_name"),
        system_prompt=_row_string(row, "system_prompt"),
        max_tokens=_row_int(row, "max_tokens"),
        enabled=_row_bool(row, "enabled"),
    )


def _merge_ai_settings_payload(
    payload: AISettingsUpsertRequest,
    existing_row: sqlite3.Row | None,
) -> AISettingsValues:
    updates = payload.model_dump(exclude_unset=True)
    return {
        "provider_type": cast(str, updates["provider_type"])
        if "provider_type" in updates
        else (_row_string(existing_row, "provider_type") if existing_row else ""),
        "api_key": cast(str, updates["api_key"])
        if "api_key" in updates
        else (_row_string(existing_row, "api_key") if existing_row else ""),
        "base_url": cast(str, updates["base_url"])
        if "base_url" in updates
        else (_row_string(existing_row, "base_url") if existing_row else ""),
        "model_name": cast(str, updates["model_name"])
        if "model_name" in updates
        else (_row_string(existing_row, "model_name") if existing_row else ""),
        "system_prompt": cast(str, updates["system_prompt"])
        if "system_prompt" in updates
        else (_row_string(existing_row, "system_prompt") if existing_row else ""),
        "max_tokens": cast(int, updates["max_tokens"])
        if "max_tokens" in updates
        else (_row_int(existing_row, "max_tokens") if existing_row else 512),
        "enabled": cast(bool, updates["enabled"])
        if "enabled" in updates
        else (_row_bool(existing_row, "enabled") if existing_row else False),
    }


def _require_ai_settings_row(db_path: str) -> sqlite3.Row:
    row = _load_ai_settings_row(db_path)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI settings not found",
        )
    return row


@router.get("/settings", response_model=AISettingsResponse)
async def get_ai_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AISettingsResponse:
    del token
    return _map_ai_settings_row(_require_ai_settings_row(db_path))


@router.put("/settings", response_model=AISettingsResponse)
async def upsert_ai_settings(
    payload: AISettingsUpsertRequest,
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> AISettingsResponse:
    del token
    existing_row = _load_ai_settings_row(db_path)
    merged = _merge_ai_settings_payload(payload, existing_row)

    with get_db(db_path) as conn:
        if existing_row is None:
            cursor = conn.execute(
                """
                INSERT INTO ai_settings (
                    provider_type, api_key, base_url, model_name, system_prompt, max_tokens, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    merged["provider_type"],
                    merged["api_key"],
                    merged["base_url"],
                    merged["model_name"],
                    merged["system_prompt"],
                    merged["max_tokens"],
                    int(merged["enabled"]),
                ),
            )
            row_id = int(cast(int, cursor.lastrowid))
        else:
            row_id = _row_id(existing_row)
            _ = conn.execute(
                """
                UPDATE ai_settings
                SET provider_type = ?, api_key = ?, base_url = ?, model_name = ?,
                    system_prompt = ?, max_tokens = ?, enabled = ?
                WHERE id = ?
                """,
                (
                    merged["provider_type"],
                    merged["api_key"],
                    merged["base_url"],
                    merged["model_name"],
                    merged["system_prompt"],
                    merged["max_tokens"],
                    int(merged["enabled"]),
                    row_id,
                ),
            )

        row = cast(
            sqlite3.Row | None,
            conn.execute(
                """
                SELECT id, provider_type, api_key, base_url, model_name, system_prompt, max_tokens, enabled
                FROM ai_settings
                WHERE id = ?
                """,
                (row_id,),
            ).fetchone(),
        )

    assert row is not None
    return _map_ai_settings_row(row)


@router.post("/test", response_model=AITestResponse)
async def test_ai_settings(
    request: Request,
    payload: AISettingsUpsertRequest | None = None,
    token: Annotated[str, Depends(verify_token)] = "",
    db_path: Annotated[str, Depends(get_db_path)] = "",
) -> AITestResponse:
    del token
    existing_row = _load_ai_settings_row(db_path)
    if payload is None:
        if existing_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI settings not found",
            )
        merged: AISettingsValues = {
            "provider_type": _row_string(existing_row, "provider_type"),
            "api_key": _row_string(existing_row, "api_key"),
            "base_url": _row_string(existing_row, "base_url"),
            "model_name": _row_string(existing_row, "model_name"),
            "system_prompt": _row_string(existing_row, "system_prompt"),
            "max_tokens": _row_int(existing_row, "max_tokens"),
            "enabled": _row_bool(existing_row, "enabled"),
        }
    else:
        merged = _merge_ai_settings_payload(payload, existing_row)

    ai_reply_service = _get_ai_reply_service(request)
    success, message = await ai_reply_service.test_connection(
        provider_type=merged["provider_type"],
        api_key=merged["api_key"],
        base_url=merged["base_url"],
        model_name=merged["model_name"],
        system_prompt=merged["system_prompt"],
        max_tokens=merged["max_tokens"],
        enabled=merged["enabled"],
    )
    return AITestResponse(success=success, message=message)


__all__ = ["router"]
