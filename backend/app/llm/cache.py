"""Request-level cache: if the same input has already been processed for a
given task type, return the cached result instead of calling an LLM again.
"""

import hashlib
import json

from redis.asyncio import Redis

from app.core.config import get_settings


def make_cache_key(task_type: str, content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"llm_cache:{task_type}:{digest}"


async def get_cached(redis: Redis, cache_key: str) -> dict | None:
    raw = await redis.get(cache_key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached(redis: Redis, cache_key: str, value: dict) -> None:
    settings = get_settings()
    await redis.set(cache_key, json.dumps(value), ex=settings.llm_cache_ttl_seconds)
