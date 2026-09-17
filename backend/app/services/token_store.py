"""Server-side refresh token and password reset token bookkeeping, in Redis.

Refresh tokens are stateless JWTs, but their jti is tracked here so a token
can be revoked (on logout or rotation) before its natural expiry.
"""

import uuid

from redis.asyncio import Redis

from app.core.config import get_settings


def _refresh_key(user_id: uuid.UUID, jti: str) -> str:
    return f"refresh_token:{user_id}:{jti}"


def _reset_key(token: str) -> str:
    return f"password_reset:{token}"


async def store_refresh_token(redis: Redis, user_id: uuid.UUID, jti: str) -> None:
    settings = get_settings()
    ttl_seconds = settings.refresh_token_expire_days * 24 * 60 * 60
    await redis.set(_refresh_key(user_id, jti), "1", ex=ttl_seconds)


async def is_refresh_token_valid(redis: Redis, user_id: uuid.UUID, jti: str) -> bool:
    return await redis.get(_refresh_key(user_id, jti)) is not None


async def revoke_refresh_token(redis: Redis, user_id: uuid.UUID, jti: str) -> None:
    await redis.delete(_refresh_key(user_id, jti))


async def store_password_reset_token(redis: Redis, token: str, user_id: uuid.UUID) -> None:
    settings = get_settings()
    ttl_seconds = settings.password_reset_token_expire_minutes * 60
    await redis.set(_reset_key(token), str(user_id), ex=ttl_seconds)


async def consume_password_reset_token(redis: Redis, token: str) -> uuid.UUID | None:
    key = _reset_key(token)
    user_id = await redis.get(key)
    if user_id is None:
        return None
    await redis.delete(key)
    return uuid.UUID(user_id)
