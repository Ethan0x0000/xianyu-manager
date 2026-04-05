"""Authentication package root with placeholder bindings."""

from app.shared.types import StubBinding

token_refresh = StubBinding(
    key="token_refresh",
    package="app.auth",
    description="Placeholder token refresh service binding.",
)

__all__ = ["token_refresh"]
