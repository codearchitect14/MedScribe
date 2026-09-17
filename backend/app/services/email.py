"""Transactional email sending.

No free-tier provider is wired up yet (Phase 2 scope is the auth flow itself).
In all environments this currently logs the message instead of sending it, so
password reset can be exercised end to end in development without a live
provider. Swap send_email's body for a Resend/Brevo API call when a provider
is configured, gated on ENVIRONMENT != "development".
"""

import structlog

logger = structlog.get_logger(__name__)


async def send_email(*, to: str, subject: str, body: str) -> None:
    logger.info("email.send", to=to, subject=subject, body=body)
