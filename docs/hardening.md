# Backend Hardening (Phase 6)

This document covers the cross-cutting additions from Phase 6: pagination/filtering, input validation, centralized error handling, structured logging, background task processing, and load/failover testing. See `docs/api-reference.md` for the per-endpoint summary these apply to.

## Pagination, filtering, sorting

`app/schemas/pagination.py` defines `PageParams` (via the `pagination_params` FastAPI dependency, reading `page`/`page_size` query parameters, capped at 100 per page) and the generic `Page[T]` response wrapper (`{items, total, page, page_size}`). `app/core/query.py::paginate()` runs a SQLAlchemy `Select` with a `COUNT` and an `OFFSET`/`LIMIT` pass. Every list endpoint (`GET /users`, `/patients`, `/encounters`, `/organizations`) uses this pair rather than a bespoke implementation.

Filters and sort fields are explicit, typed query parameters per endpoint (e.g. `status: EncounterStatus | None`, `sort: Literal["created_at", "-created_at"]`), not a generic/dynamic field-name lookup — arbitrary column filtering or sorting from user input would be an injection and information-disclosure risk. Patient names are excluded from filtering and sorting entirely: they are stored Fernet-encrypted (`app/core/encryption.py`), so there is no SQL-level way to search or order by them without a separate searchable index, which is out of scope here.

## Input validation

Every request body is a Pydantic model with explicit bounds, not just types: `CreateEncounterRequest.raw_transcript` is capped at 50,000 characters, SOAP note fields at 5,000, care plan content at 20,000, and similar bounds exist on patient and billing fields (`app/schemas/encounter.py`, `app/schemas/billing.py`, `app/schemas/patient.py`). An oversized or malformed payload is rejected by FastAPI's request validation (422) before any handler code runs.

## Centralized error handling and correlation IDs

`app/core/correlation.py::RequestContextMiddleware` assigns a correlation id to every request — the client's `X-Request-ID` header if it sent one, otherwise a generated UUID — binds it into structlog's contextvars for the duration of the request, and sets it on the response header. `app/core/error_handlers.py` registers a handler for unhandled exceptions specifically: `HTTPException`s and validation errors keep FastAPI's normal `{"detail": ...}` shape (existing clients rely on that), but anything unexpected returns a consistent `{"detail": "Internal server error", "request_id": "..."}` with a 500, rather than leaking a bare traceback. The `request_id` in that body always matches the `X-Request-ID` header on the same response, so a support ticket referencing one id can be found in both the client-visible error and the server logs for that request.

Note: Starlette's `ServerErrorMiddleware` re-raises the original exception after generating the response (by design, so it still reaches the ASGI server's own logs); this is why `tests/test_error_handling.py` uses `ASGITransport(..., raise_app_exceptions=False)` to inspect the response instead of letting the exception propagate into the test itself.

## Structured logging

`app/core/logging_config.py::configure_logging()` (called once at startup, in `app/main.py`) sets up structlog: JSON output outside `development` (for log aggregators), a readable console renderer in `development`. Every log call anywhere in the app automatically includes the current request's correlation id via `structlog.contextvars.merge_contextvars`.

**PHI-safe by construction, not by redaction.** `RequestContextMiddleware` logs exactly one line per request — method, path, status code, duration, request id — and nothing from the request or response body. Raw transcripts, SOAP note content, and patient identifiers are never passed to a logger anywhere in the codebase; there is no redaction step because there is nothing to redact.

## Background task processing (Celery)

`app/tasks/bulk_reprocess.py` moves batch SOAP note regeneration off the request path: `POST /encounters/bulk-reprocess` (admin/super_admin, org-ownership checked before enqueueing) returns `202` with a task id immediately, and `GET /tasks/{task_id}` polls its status. The actual work runs in a Celery worker process (`docker compose up -d worker`, or `celery -A app.worker worker`), broker/backend both Redis.

Celery's task execution model is synchronous per task, while the app's clinical services are async (async DB session, async LLM gateway); `bulk_reprocess_encounters_task` bridges this with `asyncio.run()` around a dedicated async function (`_bulk_reprocess`), using its own fresh `AsyncSession` and Redis client rather than reusing any request-scoped ones. A single encounter's failure (bad id, LLM error) is caught and reported in the result's `failed` list rather than aborting the whole batch.

**Testing note:** Celery's eager mode (`task_always_eager=True`, running the task inline via `asyncio.run()`) cannot be invoked from code that is itself already running inside an event loop — which is exactly the situation calling `.delay()` from within an async HTTP test is in. This is a testability wrinkle specific to eager mode, not a production issue (a real worker process never has a loop already running when it picks up a task). `tests/test_bulk_reprocess.py` tests the two layers separately: the HTTP endpoint's own logic (org-ownership validation, 202 response) with `.delay` patched to a stub, and the task's actual async logic by awaiting its inner coroutine directly.

## Load and failover testing

`tests/test_load_failover.py` fires 20 concurrent `generate()` calls through the real LLM gateway (mocked adapters, real Redis-backed quota tracking) against a primary provider that starts returning 429s partway through the burst. Every request still succeeds: the ones that hit the primary before its simulated limit use it, the rest fail over to the secondary automatically, and the test asserts the exact split — confirming the Phase 3 failover logic (`app/llm/gateway.py`) holds up under concurrent load, not just in the single-call unit tests in `tests/test_llm_gateway.py`.

## Test coverage

`pytest --cov` on the core business logic packages (`app/services/clinical`, `app/services/analytics`, `app/llm`, `app/tasks`, `app/api/deps.py`, `app/core/security.py`, `app/core/encryption.py`, `app/services/audit.py`, `app/services/rate_limit.py`, `app/services/token_store.py`) measures 93% line coverage with the full suite (`pytest tests/` — both the fast suite and the `slow`-marked Whisper/live-transcription tests), comfortably above the plan's 80% target on this code:

```
cd backend
.venv/Scripts/python -m pytest tests/ --cov=app.services.clinical --cov=app.services.analytics --cov=app.llm \
  --cov=app.tasks --cov=app.api.deps --cov=app.core.security --cov=app.core.encryption \
  --cov=app.services.audit --cov=app.services.rate_limit --cov=app.services.token_store --cov-report=term-missing
```
