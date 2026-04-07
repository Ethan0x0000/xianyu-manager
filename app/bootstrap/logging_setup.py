"""Logging initialization based on application settings.

Configures loguru with console and file handlers, reading level, rotation,
retention and compression from the ``Settings`` instance (which in turn
reads from ``global_config.yml`` → ``LOG_CONFIG``).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from app.bootstrap.settings import Settings

# Intercept stdlib logging so that libraries using ``logging.getLogger()``
# are routed through loguru with the correct level.
_loguru_configured = False


class _InterceptHandler(logging.Handler):
    """Route stdlib ``logging`` records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(settings: Settings) -> None:
    """Configure loguru based on *settings*.

    * Removes all existing loguru handlers.
    * Adds a **console** (stderr) handler at the configured level.
    * Adds a **file** handler under ``logs/`` with rotation, retention and
      compression read from ``settings.log_*`` fields.
    * Installs a stdlib ``logging`` intercept handler so that any code using
      ``logging.getLogger()`` also flows through loguru.

    This function is idempotent; calling it again replaces the previous
    configuration.
    """
    global _loguru_configured  # noqa: PLW0603

    log_level = settings.log_level.upper()

    # -- loguru handlers ---------------------------------------------------
    logger.remove()  # Remove default stderr handler

    # Console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format=settings.log_format,
        colorize=True,
    )

    # File handler — daily rotation under logs/
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(logs_dir / "xianyu_{time:YYYY-MM-DD}.log"),
        level=log_level,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8}"
            " | {name}:{function}:{line} - {message}"
        ),
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression=settings.log_compression,
        encoding="utf-8",
        enqueue=True,
    )

    # -- stdlib logging intercept ------------------------------------------
    if not _loguru_configured:
        intercept_handler = _InterceptHandler()

        # Add the intercept handler to the root logger while *preserving*
        # existing handlers (e.g. _RuntimeLogHandler used for the web UI
        # log feed).
        root_logger = logging.getLogger()
        if not any(isinstance(h, _InterceptHandler) for h in root_logger.handlers):
            root_logger.addHandler(intercept_handler)
        root_logger.setLevel(0)

        # Ensure common noisy loggers are tamed
        for noisy_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            noisy = logging.getLogger(noisy_logger_name)
            noisy.handlers = [intercept_handler]
        _loguru_configured = True

    logger.info(
        "Logging configured: level={}, rotation={}, retention={}, compression={}",
        log_level,
        settings.log_rotation,
        settings.log_retention,
        settings.log_compression,
    )


__all__ = ["setup_logging"]
