"""Unit tests for the LLM gateway, using mocked provider adapters.

Per plan.md Phase 3: no real Groq/Gemini API keys are exercised here. Redis
is used for quota/cache state (a real dev instance, see README.md); the
provider adapters themselves are monkeypatched so no network call is made.
"""

import json
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.redis import get_redis
from app.llm import gateway
from app.llm.adapters.base import ProviderResponse
from app.llm.exceptions import AllProvidersExhaustedError, ProviderError
from app.llm.gateway import GenerationContext, generate
from app.llm.schemas import SoapNoteResult, TaskType
from app.models.llm_usage_log import LlmUsageLog

settings = get_settings()

VALID_SOAP_JSON = json.dumps(
    {
        "subjective": "Patient reports cough.",
        "objective": "Mild wheeze on exam.",
        "assessment": "Acute bronchitis.",
        "plan": "Inhaler, follow up in a week.",
    }
)


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


class FakeAdapter:
    """Stands in for a ProviderAdapter; queue of (result_or_exception) per call."""

    def __init__(self, name: str, responses: list):
        self.name = name
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt, "max_tokens": max_tokens}
        )
        outcome = self._responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _ok_response(content: str = VALID_SOAP_JSON, model: str = "test-model") -> ProviderResponse:
    return ProviderResponse(content=content, tokens_input=100, tokens_output=50, model=model)


@pytest.fixture
def redis_client():
    _require_db()
    return get_redis()


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_success_logs_usage_and_caches(redis_client, monkeypatch):
    fake_groq = FakeAdapter("groq", [_ok_response()])
    monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)

    async with async_session_factory() as session:
        context = GenerationContext(session=session, redis=redis_client)
        prompt = f"unique transcript {uuid.uuid4()}"

        result = await generate(TaskType.soap_note, prompt, context)

        assert isinstance(result.data, SoapNoteResult)
        assert result.data.assessment == "Acute bronchitis."
        assert result.provider == "groq"
        assert result.from_cache is False
        assert len(fake_groq.calls) == 1

        rows = (
            await session.execute(
                select(LlmUsageLog).where(LlmUsageLog.provider == "groq").order_by(LlmUsageLog.created_at.desc())
            )
        ).scalars().all()
        assert rows, "expected a usage log row to be written"
        assert rows[0].tokens_input == 100
        assert rows[0].tokens_output == 50

        # Second call with the same prompt should hit the cache and not call the adapter again.
        result2 = await generate(TaskType.soap_note, prompt, context)
        assert result2.from_cache is True
        assert len(fake_groq.calls) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_failover_to_secondary_on_provider_error(redis_client, monkeypatch):
    fake_groq = FakeAdapter("groq", [ProviderError("boom")])
    fake_gemini = FakeAdapter("gemini", [_ok_response(model="gemini-test")])
    monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)
    monkeypatch.setitem(gateway.ADAPTERS, "gemini", fake_gemini)

    async with async_session_factory() as session:
        context = GenerationContext(session=session, redis=redis_client)
        prompt = f"unique transcript {uuid.uuid4()}"

        result = await generate(TaskType.soap_note, prompt, context)

        assert result.provider == "gemini"
        assert len(fake_groq.calls) == 1
        assert len(fake_gemini.calls) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_all_providers_exhausted_raises(redis_client, monkeypatch):
    fake_groq = FakeAdapter("groq", [ProviderError("boom")])
    fake_gemini = FakeAdapter("gemini", [ProviderError("also boom")])
    monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)
    monkeypatch.setitem(gateway.ADAPTERS, "gemini", fake_gemini)

    async with async_session_factory() as session:
        context = GenerationContext(session=session, redis=redis_client)
        prompt = f"unique transcript {uuid.uuid4()}"

        with pytest.raises(AllProvidersExhaustedError):
            await generate(TaskType.soap_note, prompt, context)


@pytest.mark.asyncio(loop_scope="session")
async def test_malformed_json_retried_once_then_succeeds(redis_client, monkeypatch):
    fake_groq = FakeAdapter(
        "groq",
        [_ok_response(content="not json at all"), _ok_response(content=VALID_SOAP_JSON)],
    )
    monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)

    async with async_session_factory() as session:
        context = GenerationContext(session=session, redis=redis_client)
        prompt = f"unique transcript {uuid.uuid4()}"

        result = await generate(TaskType.soap_note, prompt, context)

        assert result.data.assessment == "Acute bronchitis."
        assert len(fake_groq.calls) == 2
        # The retry call must include the stricter JSON-only instruction.
        assert "valid JSON" in fake_groq.calls[1]["user_prompt"]


@pytest.mark.asyncio(loop_scope="session")
async def test_malformed_json_twice_fails_over_to_secondary(redis_client, monkeypatch):
    fake_groq = FakeAdapter(
        "groq",
        [_ok_response(content="not json"), _ok_response(content="still not json")],
    )
    fake_gemini = FakeAdapter("gemini", [_ok_response(model="gemini-test")])
    monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)
    monkeypatch.setitem(gateway.ADAPTERS, "gemini", fake_gemini)

    async with async_session_factory() as session:
        context = GenerationContext(session=session, redis=redis_client)
        prompt = f"unique transcript {uuid.uuid4()}"

        result = await generate(TaskType.soap_note, prompt, context)

        assert result.provider == "gemini"
        assert len(fake_groq.calls) == 2
        assert len(fake_gemini.calls) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_quota_exhaustion_switches_provider_order(redis_client, monkeypatch):
    from app.llm import quota

    rpm_key = quota._rpm_key("groq")
    try:
        # Exhaust groq's per-minute quota locally.
        groq_limit = settings.groq_requests_per_minute
        for _ in range(groq_limit):
            await quota.record_request(redis_client, "groq")

        assert await quota.has_quota(redis_client, "groq") is False
        assert await quota.has_quota(redis_client, "gemini") is True

        fake_groq = FakeAdapter("groq", [])
        fake_gemini = FakeAdapter("gemini", [_ok_response(model="gemini-test")])
        monkeypatch.setitem(gateway.ADAPTERS, "groq", fake_groq)
        monkeypatch.setitem(gateway.ADAPTERS, "gemini", fake_gemini)

        async with async_session_factory() as session:
            context = GenerationContext(session=session, redis=redis_client)
            prompt = f"unique transcript {uuid.uuid4()}"

            result = await generate(TaskType.soap_note, prompt, context)

            assert result.provider == "gemini"
            assert len(fake_groq.calls) == 0, "groq should have been skipped due to exhausted local quota"
    finally:
        # Local quota state is tracked in a real-wall-clock minute bucket in a
        # shared dev Redis instance; without cleanup this would leak into
        # whichever other test happens to run in the same minute.
        await redis_client.delete(rpm_key)
