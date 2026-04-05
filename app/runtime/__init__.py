"""Runtime package root.

This package deliberately exposes placeholder bindings instead of importing the
legacy CookieManager / XianyuLive runtime, which breaks the current circular
dependency chain for new code.
"""

from app.shared.types import StubBinding

account_registry = StubBinding(
    key="account_registry",
    package="app.runtime",
    description="Placeholder account registry binding for extracted runtime code.",
)
ws_client = StubBinding(
    key="ws_client",
    package="app.runtime",
    description="Placeholder WebSocket client binding for extracted runtime code.",
)

__all__ = ["account_registry", "ws_client"]
