"""Local, Redis-tracked request quota per provider.

This is an estimate, not the provider's authoritative limit: it lets the
gateway proactively switch provider before hitting a real 429, per plan.md
Phase 3. A provider can still return RateLimitExceededError even when this
module reports quota remaining (e.g. limits changed, other traffic on the
same key), and the gateway handles that as an ordinary provider failure.
"""

from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import get_settings


def _limits() -> dict[str, tuple[int, int]]:
    settings = get_settings()
    return {
        "groq": (settings.groq_requests_per_minute, settings.groq_requests_per_day),
        "gemini": (settings.gemini_requests_per_minute, settings.gemini_requests_per_day),
    }


def _minute_bucket() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M")


def _day_bucket() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _rpm_key(provider: str) -> str:
    return f"llm_quota:{provider}:rpm:{_minute_bucket()}"


def _rpd_key(provider: str) -> str:
    return f"llm_quota:{provider}:rpd:{_day_bucket()}"


async def has_quota(redis: Redis, provider: str) -> bool:
    rpm_limit, rpd_limit = _limits()[provider]
    rpm_used = await redis.get(_rpm_key(provider))
    rpd_used = await redis.get(_rpd_key(provider))
    if rpm_used is not None and int(rpm_used) >= rpm_limit:
        return False
    if rpd_used is not None and int(rpd_used) >= rpd_limit:
        return False
    return True


async def record_request(redis: Redis, provider: str) -> None:
    rpm_key = _rpm_key(provider)
    rpd_key = _rpd_key(provider)

    rpm_count = await redis.incr(rpm_key)
    if rpm_count == 1:
        await redis.expire(rpm_key, 60)

    rpd_count = await redis.incr(rpd_key)
    if rpd_count == 1:
        await redis.expire(rpd_key, 24 * 60 * 60)
