"""Authentication package root with single-admin session model.

Exports:
- verify_admin_login: Verify admin credentials against settings
- create_session_token: Generate opaque session tokens
- SessionStore: In-memory session store with expiration
- get_session_store: Get the global session store singleton
- LoginRateLimiter: Brute-force protection rate limiter
- get_rate_limiter: Get the global rate limiter singleton
"""

from app.auth.rate_limiter import LoginRateLimiter, get_rate_limiter
from app.auth.service import create_session_token, verify_admin_login
from app.auth.sessions import SessionStore, get_session_store

__all__ = [
    "LoginRateLimiter",
    "SessionStore",
    "create_session_token",
    "get_rate_limiter",
    "get_session_store",
    "verify_admin_login",
]
