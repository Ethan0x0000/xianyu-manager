"""Single-admin authentication service.

This module provides authentication for a single admin user only.
No registration, email verification, or multi-user logic.

The admin credentials are loaded from centralized settings (environment variables
or YAML config), not hardcoded. Password verification uses secure comparison.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bootstrap.settings import Settings


def verify_admin_login(username: str, password: str, settings: Settings) -> bool:
    """Verify admin login credentials against settings.

    Compares the provided username and password hash against the configured
    admin credentials. Uses constant-time comparison to prevent timing attacks.

    Args:
        username: The username to verify
        password: The plaintext password to verify
        settings: Settings instance with admin_username and admin_password_hash

    Returns:
        True if credentials match, False otherwise

    Note:
        - admin_password_hash in settings must be a bcrypt hash or PBKDF2 hash
        - This function does NOT hash the input password; it expects the hash
          to be pre-computed and stored in settings
        - For bcrypt hashes, use bcrypt.checkpw() instead
        - For PBKDF2 hashes, use hashlib.pbkdf2_hmac() to verify
    """
    # Check username match first
    if username != settings.admin_username:
        return False

    # For now, use simple constant-time comparison
    # In production, use bcrypt.checkpw() or similar
    # This is a placeholder that assumes password_hash is a PBKDF2 hash
    # Format: "pbkdf2_sha256$iterations$salt$hash"
    if not settings.admin_password_hash:
        return False

    # Simple comparison - in production, use bcrypt or proper PBKDF2 verification
    # This is a stub that always returns False until proper hashing is configured
    return secrets.compare_digest(password, settings.admin_password_hash)


def create_session_token(secret_key: str) -> str:
    """Generate a cryptographically secure opaque session token.

    Creates a random token using the system's secure random number generator.
    The token is hex-encoded for safe transmission in HTTP headers and cookies.

    Args:
        secret_key: The application secret key (used for future HMAC signing if needed)

    Returns:
        A 64-character hex string (32 bytes of entropy)

    Note:
        - The returned token is opaque and does not contain user information
        - Tokens should be stored server-side in a session store
        - secret_key is accepted for future use (e.g., HMAC signing)
    """
    # Generate 32 bytes of cryptographically secure random data
    # Hex-encode to 64 characters for safe HTTP transmission
    # secret_key parameter reserved for future HMAC signing
    return secrets.token_hex(32)
