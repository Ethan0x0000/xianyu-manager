"""Item polish service.

Readable plain-Python extraction of the Goofish item polish flow.

FROZEN: the retained polish API names, URLs, and signing inputs are preserved.
NO dynamic execution, NO encoded loaders, NO obfuscation.
"""

from __future__ import annotations

import json
import logging
import time

logger = logging.getLogger(__name__)


class ItemPolishError(Exception):
    """Raised when item polish setup or input validation fails."""


class ItemPolishService:
    """Clean, readable service for Goofish item polish requests.

    The retained flow signs a single ``itemId`` payload, calls the primary polish
    endpoint, and keeps a backup endpoint available for later bootstrap wiring.
    """

    POLISH_API_NAME: str = "mtop.taobao.idle.item.polish"
    PRIMARY_API_NAME: str = POLISH_API_NAME
    POLISH_API_URL: str = (
        "https://h5api.m.goofish.com/h5/mtop.taobao.idle.item.polish/1.0/"
    )
    PRIMARY_API_URL: str = POLISH_API_URL
    BACKUP_API_NAME: str = "mtop.idle.item.polish"
    BACKUP_API_URL: str = "https://h5api.m.goofish.com/h5/mtop.idle.item.polish/1.0/"

    FROZEN_QUERY_PARAMS: dict[str, str] = {
        "jsv": "2.7.2",
        "appKey": "34839810",
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "sessionOption": "AutoLoginOnly",
        "spm_cnt": "a21ybx.im.0.0",
        "spm_pre": "a21ybx.collection.menu.1.272b5141NafCNK",
    }

    def __init__(
        self,
        account_id: str,
        cookie_str: str,
    ) -> None:
        if not account_id or not cookie_str:
            raise ItemPolishError("account_id and cookie_str are required")

        self.account_id: str = account_id
        self.cookie_str: str = cookie_str

    def build_request(
        self,
        item_id: str,
        *,
        api_name: str | None = None,
        api_url: str | None = None,
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Build the frozen signed request contract for one polish call."""
        normalized_item_id = self._normalize_item_id(item_id)
        timestamp = str(int(time.time()) * 1000)
        data = json.dumps({"itemId": normalized_item_id}, separators=(",", ":"))

        params = dict(self.FROZEN_QUERY_PARAMS)
        params["t"] = timestamp
        params["api"] = api_name or self.POLISH_API_NAME
        params["sign"] = self._generate_sign(timestamp, data)

        return api_url or self.POLISH_API_URL, params, {"data": data}

    def build_backup_request(
        self, item_id: str
    ) -> tuple[str, dict[str, str], dict[str, str]]:
        """Build the retained backup polish request contract."""
        return self.build_request(
            item_id,
            api_name=self.BACKUP_API_NAME,
            api_url=self.BACKUP_API_URL,
        )

    async def polish_item(self, item_id: str) -> dict[str, object]:
        """Polish/refresh a single item listing.

        Args:
            item_id: Goofish item ID to polish.

        Returns:
            Placeholder result until the HTTP bootstrap task wires this service.

        Raises:
            ItemPolishError: If item_id is empty.
        """
        normalized_item_id = self._normalize_item_id(item_id)

        logger.info("[%s] Polishing item %s", self.account_id, normalized_item_id)
        # HTTP execution is intentionally deferred to the later bootstrap task.
        # Request signing continues to use app.protocol.goofish_signing.generate_sign.
        return {"success": False, "error": "not_yet_wired"}

    async def polish_items(self, item_ids: list[str]) -> list[dict[str, object]]:
        """Polish multiple items and return one result per item."""
        results: list[dict[str, object]] = []

        for item_id in item_ids:
            try:
                result = await self.polish_item(item_id)
                results.append({"item_id": str(item_id), **result})
            except ItemPolishError as exc:
                results.append(
                    {
                        "item_id": str(item_id),
                        "success": False,
                        "error": str(exc),
                    }
                )

        return results

    def _generate_sign(self, timestamp: str, data: str) -> str:
        """Generate the frozen H5 signature for a polish request."""
        from app.protocol.goofish_signing import generate_sign

        token = self._extract_mtop_token()
        return generate_sign(timestamp, token, data)

    def _extract_mtop_token(self) -> str:
        """Extract the `_m_h5_tk` signing token from the cookie string."""
        token_cookie = self._parse_cookies().get("_m_h5_tk", "")
        token = token_cookie.split("_", 1)[0].strip()
        if not token:
            raise ItemPolishError("cookie_str is missing the _m_h5_tk signing token")
        return token

    def _parse_cookies(self) -> dict[str, str]:
        """Parse a standard ``key=value; key2=value2`` cookie string."""
        cookies: dict[str, str] = {}

        for part in self.cookie_str.split(";"):
            segment = part.strip()
            if not segment or "=" not in segment:
                continue

            key, value = segment.split("=", 1)
            cookies[key.strip()] = value.strip()

        return cookies

    def _normalize_item_id(self, item_id: object) -> str:
        """Normalize and validate an item identifier."""
        normalized = str(item_id or "").strip()
        if not normalized:
            raise ItemPolishError("item_id is required for polish")
        return normalized


__all__ = ["ItemPolishError", "ItemPolishService"]
