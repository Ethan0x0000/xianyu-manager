from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DockerSecretProvisioningTests(unittest.TestCase):
    def test_compose_files_require_non_empty_secret_variables(self) -> None:
        for compose_name in ("docker-compose.yml", "docker-compose-cn.yml"):
            compose_text = (PROJECT_ROOT / compose_name).read_text(encoding="utf-8")

            self.assertIn("${SECRET_KEY:?", compose_text)
            self.assertIn("${SECRET_ENCRYPTION_KEY:?", compose_text)
            self.assertNotIn("${SECRET_KEY:-}", compose_text)
            self.assertNotIn("${SECRET_ENCRYPTION_KEY:-}", compose_text)

    def test_env_example_documents_required_secret_variables(self) -> None:
        env_example_path = PROJECT_ROOT / ".env.example"

        self.assertTrue(env_example_path.exists())

        env_example_text = env_example_path.read_text(encoding="utf-8")

        self.assertRegex(env_example_text, r"(?m)^SECRET_KEY=")
        self.assertRegex(env_example_text, r"(?m)^SECRET_ENCRYPTION_KEY=")


if __name__ == "__main__":
    _ = unittest.main()
