import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.bootstrap.settings import Settings, load_settings, validate_settings
from app.auth.service import verify_admin_login
from tests.helpers import make_settings


VALID_BCRYPT_HASH = "$2b$12$4r/djL8R15ywfXfEc0caDOYSTvfaF9.3D1ZeJYo0vQRT8JkRkfyQa"


class LoadSettingsTests(unittest.TestCase):
    def test_load_settings_returns_defaults_when_no_config_file_exists(self) -> None:
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            missing_config = str(Path(temp_dir) / "missing.yml")

            settings = load_settings(missing_config)

        self.assertEqual(Settings(), settings)

    def test_load_settings_reads_port_from_yaml_config(self) -> None:
        with TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            config_path = Path(temp_dir) / "config.yml"
            _ = config_path.write_text(
                "AUTO_REPLY:\n  api:\n    port: 9001\n",
                encoding="utf-8",
            )

            settings = load_settings(str(config_path))

        self.assertEqual(9001, settings.api_port)

    def test_load_settings_gives_env_var_precedence_over_yaml(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {"API_PORT": "9002"},
                clear=True,
            ),
        ):
            config_path = Path(temp_dir) / "config.yml"
            _ = config_path.write_text(
                "AUTO_REPLY:\n  api:\n    port: 9001\n",
                encoding="utf-8",
            )

            settings = load_settings(str(config_path))

        self.assertEqual(9002, settings.api_port)

    def test_load_settings_reads_admin_credentials_from_env(self) -> None:
        with (
            TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {
                    "ADMIN_USERNAME": "env-admin",
                    "ADMIN_PASSWORD_HASH": VALID_BCRYPT_HASH,
                },
                clear=True,
            ),
        ):
            missing_config = str(Path(temp_dir) / "missing.yml")

            settings = load_settings(missing_config)

        self.assertEqual("env-admin", settings.admin_username)
        self.assertEqual(VALID_BCRYPT_HASH, settings.admin_password_hash)
        self.assertTrue(verify_admin_login("env-admin", "admin123", settings))


class ValidateSettingsTests(unittest.TestCase):
    def test_validate_settings_raises_value_error_when_secret_key_is_empty(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "SECRET_KEY"):
            validate_settings(make_settings(secret_key=""))

    def test_validate_settings_raises_value_error_when_secret_encryption_key_is_empty(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "SECRET_ENCRYPTION_KEY"):
            validate_settings(make_settings(secret_encryption_key=""))

    def test_validate_settings_passes_when_both_keys_are_set(self) -> None:
        validate_settings(
            make_settings(
                secret_key="configured-secret",
                secret_encryption_key="configured-encryption-key",
            )
        )


class SettingsDefaultsTests(unittest.TestCase):
    def test_settings_dataclass_has_correct_default_values(self) -> None:
        settings = Settings()

        self.assertEqual("0.0.0.0", settings.api_host)
        self.assertEqual(8848, settings.api_port)
        self.assertEqual("data/xianyu_data.db", settings.db_path)
        self.assertEqual("admin", settings.admin_username)
        self.assertTrue(settings.admin_password_hash)
        self.assertEqual("", settings.secret_key)
        self.assertEqual("", settings.secret_encryption_key)
        self.assertFalse(settings.ai_enabled)
        self.assertFalse(settings.enable_headful)
        self.assertFalse(settings.use_xvfb)
        self.assertFalse(settings.enable_vnc)
        self.assertFalse(settings.sql_log_enabled)
        self.assertEqual("INFO", settings.sql_log_level)
        self.assertEqual("wss://wss-goofish.dingtalk.com/", settings.websocket_url)
        self.assertTrue(settings.auto_reply_enabled)
        self.assertTrue(settings.auto_shipping_enabled)
        self.assertTrue(settings.auto_confirm_enabled)

    def test_default_admin_credentials_accept_admin123(self) -> None:
        settings = Settings()

        self.assertTrue(verify_admin_login("admin", "admin123", settings))
