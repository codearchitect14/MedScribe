"""The single entry point every clinical generation step calls.

    result = await generate(TaskType.soap_note, prompt, context)

Selects a provider (primary-first with failover, or round-robin between
providers when both have quota), calls it, validates the JSON response
against the task's schema (retrying once on a malformed response), logs
usage, and caches the result. See docs/llm-strategy.md for the full design
rationale.
"""

import time
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.llm import cache, quota
from app.llm.adapters.base import ProviderAdapter
from app.llm.adapters.gemini_adapter import GeminiAdapter
from app.llm.adapters.groq_adapter import GroqAdapter
from app.llm.exceptions import AllProvidersExhaustedError, ProviderError
from app.llm.prompts import SYSTEM_PROMPT, build_retry_prompt
from app.llm.schemas import TASK_MAX_OUTPUT_TOKENS, TASK_SCHEMAS, TaskType
from app.models.llm_usage_log import LlmUsageLog

ADAPTERS: dict[str, ProviderAdapter] = {
    "groq": GroqAdapter(),
    "gemini": GeminiAdapter(),
}

ROUND_ROBIN_COUNTER_KEY = "llm_gateway:round_robin_counter"


@dataclass
class GenerationContext:
    session: AsyncSession
    redis: Redis
    encounter_id: uuid.UUID | None = None
    cache_key: str | None = None


@dataclass
class GenerationResult:
    data: BaseModel
    provider: str
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    from_cache: bool = False


async def _select_provider_order(redis: Redis) -> list[str]:
    settings = get_settings()
    primary = settings.llm_primary_provider
    secondary = settings.llm_secondary_provider

    primary_ok = await quota.has_quota(redis, primary)
    secondary_ok = await quota.has_quota(redis, secondary)

    if settings.llm_load_balance_strategy == "round_robin" and primary_ok and secondary_ok:
        count = await redis.incr(ROUND_ROBIN_COUNTER_KEY)
        return [primary, secondary] if count % 2 == 1 else [secondary, primary]

    if primary_ok:
        return [primary, secondary]
    if secondary_ok:
        return [secondary, primary]

    # Neither provider has local quota headroom; try anyway, primary first.
    # Local tracking is an estimate, not the provider's authority.
    return [primary, secondary]


async def _log_usage(
    context: GenerationContext,
    *,
    provider: str,
    model: str,
    tokens_input: int,
    tokens_output: int,
    latency_ms: int,
) -> None:
    context.session.add(
        LlmUsageLog(
            provider=provider,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            latency_ms=latency_ms,
            encounter_id=context.encounter_id,
        )
    )
    await context.session.commit()


async def generate(task_type: TaskType, prompt: str, context: GenerationContext) -> GenerationResult:
    schema = TASK_SCHEMAS[task_type]
    max_tokens = TASK_MAX_OUTPUT_TOKENS[task_type]

    cache_key = context.cache_key or cache.make_cache_key(task_type.value, prompt)
    cached = await cache.get_cached(context.redis, cache_key)
    if cached is not None:
        return GenerationResult(
            data=schema.model_validate(cached),
            provider="cache",
            model="cache",
            tokens_input=0,
            tokens_output=0,
            latency_ms=0,
            from_cache=True,
        )

    provider_order = await _select_provider_order(context.redis)
    last_error: Exception | None = None

    for provider_name in provider_order:
        adapter = ADAPTERS[provider_name]
        try:
            start = time.monotonic()
            response = await adapter.complete(
                system_prompt=SYSTEM_PROMPT, user_prompt=prompt, max_tokens=max_tokens, json_mode=True
            )
            latency_ms = int((time.monotonic() - start) * 1000)
        except ProviderError as exc:
            last_error = exc
            continue

        await quota.record_request(context.redis, provider_name)

        parsed = _try_parse(schema, response.content)
        if parsed is None:
            # One retry, same provider, with a stricter JSON-only reminder.
            try:
                retry_start = time.monotonic()
                retry_response = await adapter.complete(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=build_retry_prompt(prompt),
                    max_tokens=max_tokens,
                    json_mode=True,
                )
                latency_ms += int((time.monotonic() - retry_start) * 1000)
            except ProviderError as exc:
                last_error = exc
                continue

            await quota.record_request(context.redis, provider_name)
            parsed = _try_parse(schema, retry_response.content)
            if parsed is None:
                last_error = ValueError(
                    f"{provider_name} returned invalid JSON twice for task {task_type.value}"
                )
                continue
            response = retry_response

        await _log_usage(
            context,
            provider=provider_name,
            model=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            latency_ms=latency_ms,
        )
        await cache.set_cached(context.redis, cache_key, parsed.model_dump())

        return GenerationResult(
            data=parsed,
            provider=provider_name,
            model=response.model,
            tokens_input=response.tokens_input,
            tokens_output=response.tokens_output,
            latency_ms=latency_ms,
        )

    raise AllProvidersExhaustedError(
        f"All configured LLM providers failed for task {task_type.value}: {last_error}"
    ) from last_error


def _try_parse(schema: type[BaseModel], content: str) -> BaseModel | None:
    try:
        return schema.model_validate_json(content)
    except ValidationError:
        return None
