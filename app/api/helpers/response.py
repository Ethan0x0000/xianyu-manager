from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import cast


def legacy_ok(data: object = None, message: str = "ok") -> dict[str, object]:
    payload: dict[str, object] = {
        "success": True,
        "message": message,
        "data": data,
    }
    if isinstance(data, Mapping):
        mapping = cast(Mapping[object, object], data)
        for key, value in mapping.items():
            payload[str(key)] = value
    return payload


def legacy_paginated(
    items: Iterable[object],
    total: int,
    page: int,
    size: int,
) -> dict[str, object]:
    materialized_items = list(items)
    pages = math.ceil(total / size) if size > 0 else 0
    return legacy_ok(
        {
            "items": materialized_items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        },
        message="ok",
    )


__all__ = ["legacy_ok", "legacy_paginated"]
