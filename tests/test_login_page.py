import unittest
from pathlib import Path


class LoginPageTests(unittest.TestCase):
    def test_login_page_uses_current_auth_endpoints_and_redirect(self) -> None:
        login_page_path = Path(__file__).resolve().parents[1] / "static" / "login.html"
        html = login_page_path.read_text(encoding="utf-8")

        self.assertIn("fetch('/api/auth/login'", html)
        self.assertIn("fetch('/api/auth/verify'", html)
        self.assertIn("const dashboardUrl = '/static/index.html';", html)
        self.assertIn("window.location.href = dashboardUrl;", html)
        self.assertNotIn("fetch('/login', {", html)
        self.assertNotIn("fetch('/verify', {", html)
