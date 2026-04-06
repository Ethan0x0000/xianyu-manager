"""Single-admin authentication service.

This module provides authentication for a single admin user only.
No registration, email verification, or multi-user logic.

The admin credentials are loaded from centralized settings (environment variables
or YAML config), not hardcoded. Password verification uses secure comparison.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING

import bcrypt

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
        - admin_password_hash in settings may be a bcrypt hash, a PBKDF2 hash,
          or a plaintext compatibility value
        - This function verifies the input password against the stored value
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

    return _verify_password(password, settings.admin_password_hash)


def _verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        return _verify_bcrypt_password(password, password_hash)

    if password_hash.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2_password(password, password_hash)

    return secrets.compare_digest(password, password_hash)


def _verify_bcrypt_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _verify_pbkdf2_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected_hash = password_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(iterations_text)
    except ValueError:
        return False

    calculated_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return secrets.compare_digest(calculated_hash, expected_hash)


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
