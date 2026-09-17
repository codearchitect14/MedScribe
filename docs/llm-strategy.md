# LLM Strategy

The clinical pipeline (Phase 4 onward) never calls Groq or Gemini directly. Every generation step goes through one function:

```python
from app.llm.gateway import GenerationContext, generate
from app.llm.schemas import TaskType

result = await generate(TaskType.soap_note, prompt, GenerationContext(session=db_session, redis=redis_client, encounter_id=encounter_id))
```

`result.data` is a validated Pydantic model (never raw text), `result.provider`/`result.model` record which provider actually served the call, and `result.from_cache` reports whether it was served from the request-level cache.

## Provider selection: failover and load balancing

`app/llm/gateway.py::_select_provider_order` picks an order between the two configured providers (`LLM_PRIMARY_PROVIDER` / `LLM_SECONDARY_PROVIDER`, default `groq` / `gemini`):

- **`primary_first`** (default): tries the primary provider first, failing over to the secondary only if the primary errors, rate-limits, or has no local quota headroom.
- **`round_robin`** (`LLM_LOAD_BALANCE_STRATEGY=round_robin`): when both providers currently have local quota headroom, alternates between them on successive calls (a Redis counter), spreading load evenly across both free tiers. Falls back to whichever provider does have quota if only one does.

Either way, if the selected provider's call raises `ProviderError` (including `RateLimitExceededError`), the gateway automatically tries the next provider in the order before giving up. If every provider fails, `AllProvidersExhaustedError` is raised.

## Quota tracking

`app/llm/quota.py` tracks requests-per-minute and requests-per-day counters per provider in Redis (`GROQ_REQUESTS_PER_MINUTE`, `GROQ_REQUESTS_PER_DAY`, `GEMINI_REQUESTS_PER_MINUTE`, `GEMINI_REQUESTS_PER_DAY`, defaulted to conservative free-tier estimates). This is a local, proactive estimate, not the provider's authoritative limit: a provider whose local counter looks exhausted is skipped in favor of the other one, so the gateway switches before hitting a real 429 rather than only reacting to one. If both look exhausted locally, the gateway still attempts a call (primary first) rather than refusing outright, since the local tracking can be wrong (limits change, other traffic shares the same key).

## Token minimization

- **One combined prompt per SOAP note.** All four sections (Subjective, Objective, Assessment, Plan) are requested and returned in a single JSON response (`app/llm/prompts.py::build_soap_note_prompt`), not four separate calls.
- **A short, fixed system prompt** (`SYSTEM_PROMPT`) is reused verbatim across every call. Both providers support prompt caching on repeated prefixes, so this costs less on the provider side over repeated calls.
- **The care plan step never resends the transcript.** `build_care_plan_prompt` takes only the already-generated Assessment and Plan text as input.
- **Coding never asks the model to invent codes.** The calling service retrieves the top-k candidate codes via pgvector similarity search against the Assessment embedding first (see `docs/database-schema.md`); only those candidate descriptions (typically 5-10) plus the Assessment text are sent to the LLM, which selects and justifies from that list (`build_coding_prompt`). This keeps both the call small and the codes accurate, since they come from the reference table, never from model memory.
- **Output is capped per task type** (`TASK_MAX_OUTPUT_TOKENS` in `app/llm/schemas.py`): 500 tokens for the SOAP note, 300 for the care plan, 200 for coding justification.
- **Strict JSON schema enforcement.** Both adapters request JSON-mode output (`response_format: json_object` for Groq, `responseMimeType: application/json` for Gemini) and the response is validated against a Pydantic schema per task type. A malformed response triggers exactly one retry, on the same provider, with an appended "valid JSON only" instruction; if that also fails, the gateway fails over to the next provider rather than retrying indefinitely.
- **Request-level cache.** `app/llm/cache.py` hashes the prompt (which embeds the transcript/assessment content) per task type and caches the validated result in Redis (`LLM_CACHE_TTL_SECONDS`, default 24h). Reprocessing the same input returns the cached result with zero additional tokens.

## Usage logging

Every non-cached call writes one row to `llm_usage_logs` (`app/models/llm_usage_log.py`, created in Phase 1): provider, model, tokens in/out, latency, and the encounter it belongs to. This is the source of truth for the Phase 7 analytics dashboard's LLM cost/usage panel.

## Token budget (estimated, per encounter)

With the caps above, one full encounter (SOAP note, then care plan, then coding) is bounded at:

| Step | Output cap | Typical input |
|---|---|---|
| SOAP note | 500 tokens | transcript (varies; MTS-Dialog/ACI-BENCH samples run roughly 200-800 tokens) |
| Care plan | 300 tokens | Assessment + Plan text only (typically 50-150 tokens), not the transcript |
| Coding justification | 200 tokens | Assessment text + 5-10 short candidate descriptions (typically 100-250 tokens) |

This is a design-time budget from the caps and prompt shapes above, not a measured one: the actual clinical pipeline that exercises this end to end is built in Phase 4. Once real Groq/Gemini API keys are configured, `llm_usage_logs` gives an exact measured token cost per encounter; re-check this table against that data once Phase 4 is in place.

## Testing

- `tests/test_llm_adapters.py`: verifies the Groq and Gemini adapters build the correct request payload and parse both success and 429 responses, using a monkeypatched `httpx.AsyncClient` (no network calls, no API keys required).
- `tests/test_llm_gateway.py`: verifies the gateway's provider selection, failover, quota-based switching, JSON-retry-then-failover behavior, usage logging, and caching, using mocked provider adapters.
- No live integration tests against real Groq/Gemini keys are included yet, since no free-tier keys are configured in this environment. Per plan.md Phase 3, such tests should run on a limited, scheduled CI basis only (not on every push) to avoid exhausting the free quota, once keys are available.
