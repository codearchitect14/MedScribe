# Data-Flow Review (Phase 9)

A pass over the three specific checks plan.md Phase 9 names, plus what was found doing it.

## 1. No clinical text is logged in plaintext outside the database

Every `logger.*` call site in the backend was enumerated and checked:

| Location | What it logs | Clinical content? |
|---|---|---|
| `app/core/correlation.py` (`request.completed`, unhandled-exception path) | method, path, status code, duration, request id | No |
| `app/core/error_handlers.py` (`request.unhandled_exception`) | request id + exception traceback | No - standard Python tracebacks do not dump local variable values, and no exception message anywhere in the codebase interpolates transcript/note/patient content into its message string (checked: every `raise` in `app/services/clinical/` and `app/api/routes/encounters.py` either re-raises or constructs a message from static text/ids, never from field content) |
| `app/core/monitoring.py` (`monitoring.sentry_enabled`) | environment name | No |
| `app/api/routes/live_transcription.py` (`inference_error`, `finalize_on_stop_error`) | the exception message from a failed Whisper inference call (e.g. an allocation error) | No - these are technical error strings from faster-whisper/ctranslate2, not the audio or transcript content itself |
| `app/services/email.py` (`email.send`) | recipient address, subject, body | The body contains a password-reset token, not clinical content. This is the documented console-log fallback for password reset email (`docs/security.md`, Phase 2) since no live transactional email provider is wired up; swap it for a real provider before production use with real users, at which point this log line should be removed entirely rather than adapted |
| `app/tasks/analytics_rollup.py`, `app/tasks/bulk_reprocess.py` | organization/encounter ids, counts | No |

No log call anywhere passes `raw_transcript`, `subjective`/`objective`/`assessment`/`plan`, `care_plan.content`, or any patient field as an argument. This was true before this review (by original design, per `docs/hardening.md`'s "PHI-safe by construction, not by redaction") and remains true after Phase 7-9's additions.

**One real gap found and fixed by this review**: `app/llm/adapters/groq_adapter.py` and `gemini_adapter.py` raised `ProviderError` with the provider's *raw, unbounded* HTTP response body embedded in the exception message (e.g. `f"Groq returned {response.status_code}: {response.text}"`). An unhandled instance of that exception reaches `error_handlers.py`'s `logger.exception(...)`, which does log the exception's string representation - so if Groq or Gemini ever echoed part of the request (a common pattern for validation-error responses on some APIs) back in an error body, transcript-derived text could have reached the server log via that path. Fixed: both adapters now truncate the provider's response body to 200 characters before it can appear in any exception message (`app/llm/adapters/base.py::truncate_for_error`), verified by `tests/test_llm_adapters.py::test_groq_adapter_error_message_truncates_long_response_body`. This does not fully eliminate the theoretical exposure (200 characters could still contain a fragment), but bounds it to a size where full transcript content cannot land in a log line, and is a reasonable proportionate mitigation for an error path that has never actually been observed to echo request content back (neither Groq's nor Gemini's documented error responses do this).

**Frontend**: no `console.log`/`console.error` call in `frontend/src` logs request or response bodies; the optional Sentry integration (`frontend/src/lib/monitoring.ts`) sets `sendDefaultPii: false` for the same reason.

## 2. All traffic is served over TLS

TLS termination is out of scope for the application itself - a FastAPI/Uvicorn process does not terminate TLS in any of the free-tier deployment targets this plan names (Render, Railway, Fly.io); the platform's load balancer or a reverse proxy does, and this repository does not (and should not) hardcode a specific one. What the application *does* enforce:

- `SecurityHeadersMiddleware` (`app/core/middleware.py`) sets `Strict-Transport-Security` on every response outside `ENVIRONMENT=development`, so a browser that has ever loaded the app over HTTPS will not later be downgraded to HTTP.
- CORS (`app/main.py`) is restricted to a single configured `FRONTEND_ORIGIN`, not a wildcard, so a TLS-terminated response can't be read cross-origin by an arbitrary site.
- **Action for deployment**: whichever host is chosen must have TLS/HTTPS enforced at that layer (most free-tier PaaS targets named in `plan (1).md` do this by default for their own subdomain); see `docs/deployment.md`. This is recorded as a deployment-time checklist item, not something the application code can guarantee on its own.

## 3. JWTs are short-lived and refresh tokens are rotated on use

Both already held from Phase 2, re-verified here:

- Access tokens: `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30) - `app/core/config.py`.
- Refresh tokens: `REFRESH_TOKEN_EXPIRE_DAYS` (default 7), `httpOnly`, `Secure` outside development, `SameSite=Strict` - `app/core/cookies.py`.
- Rotation: `POST /auth/refresh` (`app/api/routes/auth.py`) revokes the presented refresh token's `jti` in Redis (`app/services/token_store.py::revoke_refresh_token`) before issuing a new access/refresh/CSRF token triple. A refresh token can only ever be used once; replaying an already-used one fails with 401. Verified by `tests/test_auth.py::test_refresh_requires_matching_csrf_and_rotates_token`.
