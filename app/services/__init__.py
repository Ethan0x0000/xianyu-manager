"""Service package root with placeholder bindings for future extractions."""

from app.shared.types import StubBinding

reply_policy = StubBinding(
    key="reply_policy",
    package="app.services",
    description="Placeholder reply policy service binding.",
)
ai_reply = StubBinding(
    key="ai_reply",
    package="app.services",
    description="Placeholder AI reply service binding.",
)
shipping = StubBinding(
    key="shipping",
    package="app.services",
    description="Placeholder shipping service binding.",
)
item_polish = StubBinding(
    key="item_polish",
    package="app.services",
    description="Placeholder item polish service binding.",
)
auto_confirm = StubBinding(
    key="auto_confirm",
    package="app.services",
    description="Placeholder auto-confirm service binding.",
)
login_service = StubBinding(
    key="login_service",
    package="app.services",
    description="Placeholder login service binding.",
)

__all__ = [
    "ai_reply",
    "auto_confirm",
    "item_polish",
    "login_service",
    "reply_policy",
    "shipping",
]
