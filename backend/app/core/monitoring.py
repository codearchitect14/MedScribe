"""Optional error tracking (plan.md Phase 9: "free tier of Sentry"). A no-op
unless SENTRY_DSN is set; nothing about request handling changes for a
deployment that doesn't configure it. PHI-safety follows the same posture
as structured logging (docs/hardening.md): request bodies are never sent to
Sentry (send_default_pii stays False), only exception metadata.
"""

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


def configure_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        traces_sample_rate=0.0,
    )
    logger.info("monitoring.sentry_enabled", environment=settings.environment)
