"""Authentication package root with single-admin session model.

Exports:
- verify_admin_login: Verify admin credentials against settings
- create_session_token: Generate opaque session tokens
- SessionStore: In-memory session store with expiration
- get_session_store: Get the global session store singleton
"""

from app.auth.service import create_session_token, verify_admin_login
from app.auth.sessions import SessionStore, get_session_store

__all__ = [
    "verify_admin_login",
    "create_session_token",
    "SessionStore",
    "get_session_store",
]
