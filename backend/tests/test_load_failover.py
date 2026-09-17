"""Load/concurrency test for the LLM gateway (plan.md Phase 6): confirms the
Phase 3 failover logic holds up under many concurrent requests once the
primary provider starts throttling mid-batch, not just in the single-call
unit tests in tests/test_llm_gateway.py.
"""

import asyncio
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.redis import get_redis
from app.llm import gateway
from app.llm.adapters.base import ProviderResponse
from app.llm.exceptions import RateLimitExceededError
from app.llm.gateway import GenerationContext, generate
from app.llm.schemas import TaskType

settings = get_settings()

SOAP_JSON = json.dumps({"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"})


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


class ThrottledAfterLimitAdapter:
    """Simulates a free-tier provider that starts returning 429s partway
    through a burst of concurrent requests."""

    name = "groq"

    def __init__(self, limit: int):
        self.limit = limit
        self.calls = 0

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        self.calls += 1  # no `await` before this check: atomic under asyncio's cooperative scheduling
        if self.calls <= self.limit:
            return ProviderResponse(content=SOAP_JSON, tokens_input=10, tokens_output=10, model="groq-mock")
        raise RateLimitExceededError("simulated throttling")


class AlwaysAvailableAdapter:
    name = "gemini"

    def __init__(self):
        self.calls = 0

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        self.calls += 1
        return ProviderResponse(content=SOAP_JSON, tokens_input=10, tokens_output=10, model="gemini-mock")


@pytest.mark.asyncio(loop_scope="session")
async def test_failover_holds_up_under_concurrent_load():
    _require_db()

    throttle_limit = 8
    concurrent_requests = 20

    groq_adapter = ThrottledAfterLimitAdapter(limit=throttle_limit)
    gemini_adapter = AlwaysAvailableAdapter()

    original_groq = gateway.ADAPTERS["groq"]
    original_gemini = gateway.ADAPTERS["gemini"]
    gateway.ADAPTERS["groq"] = groq_adapter
    gateway.ADAPTERS["gemini"] = gemini_adapter

    redis = get_redis()

    async def _one_call(i: int):
        async with async_session_factory() as session:
            context = GenerationContext(session=session, redis=redis, encounter_id=None)
            prompt = f"concurrent load test transcript {uuid.uuid4()} #{i}"
            return await generate(TaskType.soap_note, prompt, context)

    from app.llm import quota

    try:
        results = await asyncio.gather(*[_one_call(i) for i in range(concurrent_requests)])
    finally:
        gateway.ADAPTERS["groq"] = original_groq
        gateway.ADAPTERS["gemini"] = original_gemini
        # Local quota state lives in a real-wall-clock minute bucket in a
        # shared dev Redis instance; without cleanup this leaks into
        # whichever other test happens to run in the same minute (same
        # issue as tests/test_llm_gateway.py's quota test).
        await redis.delete(quota._rpm_key("groq"))
        await redis.delete(quota._rpm_key("gemini"))

    assert len(results) == concurrent_requests
    for result in results:
        assert result.data.assessment == "a"

    providers_used = [r.provider for r in results]
    groq_used = providers_used.count("groq")
    gemini_used = providers_used.count("gemini")

    # Every request succeeded despite the primary throttling partway through:
    # the excess load was absorbed by automatic failover to the secondary.
    assert groq_used == throttle_limit
    assert gemini_used == concurrent_requests - throttle_limit
    assert groq_adapter.calls == concurrent_requests  # every request tried groq first (primary_first strategy)
