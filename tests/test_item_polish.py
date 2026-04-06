# pyright: reportPrivateUsage=false

import json
import unittest
from typing import cast
from unittest.mock import AsyncMock, patch

from app.services.item_polish import ItemPolishError, ItemPolishService


class TestItemPolishService(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def make_service() -> ItemPolishService:
        return ItemPolishService(
            account_id="account-1",
            cookie_str="_m_h5_tk=testtoken_12345; cna=session-value; xlly_s=1",
        )

    def test_init_rejects_empty_account_id_or_cookie_str(self) -> None:
        invalid_cases = [
            ("", "cookie=1"),
            (None, "cookie=1"),
            ("account-1", ""),
            ("account-1", None),
        ]

        for account_id, cookie_str in invalid_cases:
            with self.subTest(account_id=account_id, cookie_str=cookie_str):
                with self.assertRaises(ItemPolishError):
                    _ = ItemPolishService(
                        account_id=cast(str, account_id),
                        cookie_str=cast(str, cookie_str),
                    )

    def test_normalize_item_id_rejects_empty_values_and_normalizes_whitespace(
        self,
    ) -> None:
        service = self.make_service()
        self.assertEqual(service._normalize_item_id("  123456  "), "123456")

        for invalid_value in (None, "", "   "):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(ItemPolishError, "item_id is required"):
                    _ = service._normalize_item_id(invalid_value)

    def test_parse_cookies_parses_standard_cookie_strings(self) -> None:
        cookies = self.make_service()._parse_cookies()

        self.assertEqual(
            cookies,
            {
                "_m_h5_tk": "testtoken_12345",
                "cna": "session-value",
                "xlly_s": "1",
            },
        )

    def test_extract_mtop_token_extracts_value_before_first_underscore(self) -> None:
        self.assertEqual(self.make_service()._extract_mtop_token(), "testtoken")

    def test_extract_mtop_token_raises_when_signing_cookie_missing(self) -> None:
        service = ItemPolishService(
            account_id="account-1", cookie_str="cna=session-value"
        )

        with self.assertRaisesRegex(ItemPolishError, "_m_h5_tk"):
            _ = service._extract_mtop_token()

    def test_build_request_returns_url_params_and_form_data(self) -> None:
        service = self.make_service()
        with patch.object(
            service, "_generate_sign", return_value="signed-value"
        ) as mocked_sign:
            url, params, form_data = service.build_request(" 123456 ")

        self.assertEqual(url, ItemPolishService.POLISH_API_URL)
        self.assertEqual(params["api"], ItemPolishService.POLISH_API_NAME)
        self.assertEqual(params["sign"], "signed-value")
        self.assertTrue(params["t"].isdigit())
        self.assertEqual(form_data, {"data": '{"itemId":"123456"}'})
        self.assertEqual(json.loads(form_data["data"]), {"itemId": "123456"})
        mocked_sign.assert_called_once_with(params["t"], form_data["data"])

        for key, value in ItemPolishService.FROZEN_QUERY_PARAMS.items():
            with self.subTest(key=key):
                self.assertEqual(params[key], value)

    def test_build_backup_request_uses_backup_api_name_and_url(self) -> None:
        service = self.make_service()
        with patch.object(service, "_generate_sign", return_value="backup-sign"):
            url, params, form_data = service.build_backup_request("item-9")

        self.assertEqual(url, ItemPolishService.BACKUP_API_URL)
        self.assertEqual(params["api"], ItemPolishService.BACKUP_API_NAME)
        self.assertEqual(params["sign"], "backup-sign")
        self.assertEqual(json.loads(form_data["data"]), {"itemId": "item-9"})

    async def test_polish_items_collects_success_and_error_results(self) -> None:
        service = self.make_service()

        async def fake_polish_item(item_id: str) -> dict[str, object]:
            if item_id == "bad-item":
                raise ItemPolishError("item_id is required for polish")
            return {"success": True, "result": f"polished:{item_id}"}

        service.polish_item = AsyncMock(side_effect=fake_polish_item)

        results = await service.polish_items(["item-1", "bad-item", "item-3"])

        self.assertEqual(
            results,
            [
                {"item_id": "item-1", "success": True, "result": "polished:item-1"},
                {
                    "item_id": "bad-item",
                    "success": False,
                    "error": "item_id is required for polish",
                },
                {"item_id": "item-3", "success": True, "result": "polished:item-3"},
            ],
        )


if __name__ == "__main__":
    _ = unittest.main()
