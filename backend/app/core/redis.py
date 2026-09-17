from redis.asyncio import Redis

from app.core.config import get_settings


def get_redis() -> Redis:
    """Returns a new Redis client per call.

    Not cached: an asyncio Redis client is bound to the event loop it was
    created on, and caching it across requests/tests that may run on
    different event loops (as pytest-asyncio's function-scoped loops do)
    breaks the underlying connection. The client is cheap to construct;
    the connection itself is pooled lazily by redis-py.
    """
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)
