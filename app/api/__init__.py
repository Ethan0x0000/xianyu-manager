"""API package root placeholder.

The refactored API surface will grow under this package without importing the
legacy reply_server module from package initialization.
"""

from app.shared.types import StubBinding

api_root = StubBinding(
    key="api_root",
    package="app.api",
    description="Placeholder API package binding.",
)

__all__ = ["api_root"]
