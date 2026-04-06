from __future__ import annotations

from pathlib import Path
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.api.dependencies import verify_token
from app.api.helpers import legacy_ok
from utils.image_utils import ImageManager

router = APIRouter(tags=["uploads"])


class _UploadState(Protocol):
    upload_dir: Path


class _ConfiguredApp(Protocol):
    state: _UploadState


def _upload_dir(request: Request) -> Path:
    app = cast(_ConfiguredApp, request.app)
    return Path(app.state.upload_dir)


def _image_url(saved_path: str) -> str:
    return "/" + saved_path.replace("\\", "/").lstrip("/")


def _validate_image_upload(file: UploadFile) -> None:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only image uploads are supported",
        )


@router.post("/api/upload/image")
@router.post("/api/upload", include_in_schema=False)
@router.post("/upload-image", include_in_schema=False)
async def upload_image(
    request: Request,
    token: Annotated[str, Depends(verify_token)],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, object]:
    del token
    _validate_image_upload(file)

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded image is empty",
        )

    image_manager = ImageManager(upload_dir=str(_upload_dir(request)))
    saved_path = image_manager.save_image(image_bytes, file.filename or "upload-image")
    if saved_path is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid image upload",
        )

    image_url = _image_url(saved_path)
    return legacy_ok(
        {"image_url": image_url, "path": image_url},
        message="Image uploaded successfully",
    )


@router.get("/backup/export", include_in_schema=False)
async def export_backup_stub(
    token: Annotated[str, Depends(verify_token)],
) -> dict[str, object]:
    del token
    return legacy_ok(
        {"exported": False, "kind": "backup"},
        message="Backup export stub registered",
    )


@router.post("/admin/backup/upload", include_in_schema=False)
async def upload_backup_stub(
    token: Annotated[str, Depends(verify_token)],
    backup_file: Annotated[UploadFile, File(...)],
) -> dict[str, object]:
    del token
    return legacy_ok(
        {
            "imported": False,
            "filename": backup_file.filename or "backup.db",
            "kind": "backup",
        },
        message="Backup upload stub registered",
    )


__all__ = ["router"]
