"""Application entry point.

Starts Xianyu Manager using the new modular architecture.
"""

from __future__ import annotations

import uvicorn

from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import load_settings


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
