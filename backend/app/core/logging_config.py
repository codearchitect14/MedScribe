"""Structured logging setup (plan.md Phase 6).

JSON output in non-development environments (log aggregators expect one
JSON object per line); a readable console renderer in development. Every
log call anywhere in the app automatically picks up request_id (and any
other bound context) via the contextvars merge processor, since
app.core.correlation.RequestContextMiddleware binds it per request.
"""

import logging

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
