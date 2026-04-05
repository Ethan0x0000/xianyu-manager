from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_path, verify_token
from app.api.schemas import HealthResponse, SettingsResponse
from app.bootstrap.settings import load_settings
from app.db.repositories.settings_repository import SettingsRepository

router = APIRouter(prefix="", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version="2.0")


@router.get("/api/settings", response_model=SettingsResponse)
async def get_system_settings(
    token: Annotated[str, Depends(verify_token)],
    db_path: Annotated[str, Depends(get_db_path)],
) -> SettingsResponse:
    del token
    try:
        settings = SettingsRepository(db_path).get_all()
        payload = {str(item["key"]): item["value"] for item in settings}
    except Exception:
        payload = asdict(load_settings())

    _ = payload.pop("admin_password_hash", None)
    return SettingsResponse(settings=payload)


__all__ = ["router"]
