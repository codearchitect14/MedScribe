from redis.asyncio import Redis

from app.core.config import get_settings


class RateLimitExceeded(Exception):
    pass


def _login_attempts_key(email: str) -> str:
    return f"login_attempts:{email.lower()}"


async def check_login_rate_limit(redis: Redis, email: str) -> None:
    settings = get_settings()
    key = _login_attempts_key(email)
    attempts = await redis.get(key)
    if attempts is not None and int(attempts) >= settings.login_rate_limit_attempts:
        raise RateLimitExceeded(
            f"Too many failed login attempts. Try again in "
            f"{settings.login_rate_limit_window_seconds // 60} minutes."
        )


async def record_failed_login(redis: Redis, email: str) -> None:
    settings = get_settings()
    key = _login_attempts_key(email)
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, settings.login_rate_limit_window_seconds)


async def clear_login_attempts(redis: Redis, email: str) -> None:
    await redis.delete(_login_attempts_key(email))
