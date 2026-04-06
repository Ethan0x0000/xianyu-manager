from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import cast
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import Response
from PIL import Image

from app.auth.sessions import SessionStore
from app.bootstrap.app_factory import create_app
from tests.helpers import make_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_TOKEN = "legacy-token"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AUTH_TOKEN}"}


def _png_bytes() -> bytes:
    image = Image.new("RGB", (16, 16), color=(0, 128, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _json_dict(response: Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


@contextmanager
def _auth_client() -> Iterator[TestClient]:
    store = SessionStore()
    _ = store.create_session(AUTH_TOKEN, ttl_seconds=60)
    with patch("app.api.dependencies.get_session_store", return_value=store):
        with TestClient(create_app(settings=make_settings())) as client:
            yield client


def test_image_upload_accepts_authenticated_image_multipart() -> None:
    with _auth_client() as client:
        response = client.post(
            "/api/upload/image",
            headers=_auth_headers(),
            files={"file": ("sample.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 200
    payload = _json_dict(response)
    assert payload["success"] is True
    image_url = cast(str, payload["image_url"])
    assert image_url.startswith("/uploads/")

    saved_file = PROJECT_ROOT / "data" / image_url.lstrip("/")
    assert saved_file.exists()
    saved_file.unlink(missing_ok=True)


def test_image_upload_rejects_non_image_file() -> None:
    with _auth_client() as client:
        response = client.post(
            "/api/upload/image",
            headers=_auth_headers(),
            files={"file": ("sample.txt", b"not-an-image", "text/plain")},
        )

    assert response.status_code == 422
    payload = _json_dict(response)
    detail = cast(str, payload["detail"])
    assert "image" in detail.lower()


def test_orders_stream_uses_sse_content_type_and_emits_ready_event() -> None:
    with _auth_client() as client:
        response = client.get(
            "/api/orders/stream",
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: stream.ready" in response.text
    assert "data:" in response.text
