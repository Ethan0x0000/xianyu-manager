from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import verify_token

router = APIRouter(tags=["orders-stream"])


def _encode_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/api/orders/stream")
async def orders_stream(
    token: Annotated[str, Depends(verify_token)],
) -> StreamingResponse:
    del token

    async def event_stream() -> AsyncIterator[str]:
        yield _encode_sse("stream.ready", {"status": "connected", "channel": "orders"})
        await asyncio.sleep(0)
        yield _encode_sse("ping", {"heartbeat": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
