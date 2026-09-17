# API Reference

The authoritative, always-current reference is the live OpenAPI/Swagger UI served by FastAPI at `/docs` (and the raw schema at `/openapi.json`) when the backend is running. This file is a short map of what exists; the next addition will be whatever Phase 8's frontend needs that the backend does not yet expose.

## Conventions

- **Pagination.** Every list endpoint (`GET /users`, `GET /patients`, `GET /encounters`, `GET /organizations`) takes `page` (default 1) and `page_size` (default 20, max 100) query parameters and returns `{"items": [...], "total": N, "page": N, "page_size": N}` rather than a bare array.
- **Filtering and sorting.** Where it applies, list endpoints take typed query parameters (e.g. `GET /users?role=coder&is_active=true`, `GET /encounters?status=finalized&patient_id=...`) and a whitelisted `sort` parameter (e.g. `sort=-created_at`). Patient names cannot be filtered or sorted on: they are encrypted at rest (`app/core/encryption.py`) and therefore not queryable at the SQL level.
- **Error shape.** `HTTPException`s (4xx) keep FastAPI's normal `{"detail": "..."}` body. Every response, success or failure, carries an `X-Request-ID` header (echoing one the client sent, or a generated one). An unhandled server error (5xx) returns `{"detail": "Internal server error", "request_id": "..."}`, with `request_id` matching the header, so a support ticket can reference one id that also appears in the server's structured logs. See `app/core/correlation.py` and `app/core/error_handlers.py`.
- **Logging.** One structured log line per request (method, path, status, duration, request id) — never request/response bodies, which can contain PHI (transcripts, note content, patient identifiers). See `docs/security.md`.

## Auth (`/auth`, Phase 2)

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | OAuth2 password flow; `username` is the email |
| POST | `/auth/refresh` | Rotates the refresh token; requires the `X-CSRF-Token` header |
| POST | `/auth/logout` | Revokes the current refresh token |
| GET | `/auth/me` | Current authenticated user |
| POST | `/auth/password-reset/request` | Always returns 204 |
| POST | `/auth/password-reset/confirm` | Single-use token |

## Users (`/users`, Phase 2, pagination/filtering added Phase 6)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/users` | admin, super_admin, coder | Org-scoped; paginated; filter by `role`, `is_active`; sort by `created_at`/`email` |
| POST | `/users` | admin, super_admin | Admin-invited registration |
| PATCH | `/users/{id}/role` | admin, super_admin | Audit-logged |
| PATCH | `/users/{id}/deactivate` | admin, super_admin | Audit-logged |

## Organizations (`/organizations`, Phase 6)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/organizations/me` | any authenticated | The caller's own organization |
| PATCH | `/organizations/me` | admin, super_admin | Rename; audit-logged |
| GET | `/organizations` | super_admin | All organizations, paginated |
| PATCH | `/organizations/{id}/deactivate` | super_admin | Audit-logged |

## Patients (`/patients`, Phase 4, list added Phase 6)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/patients` | clinician, admin, super_admin | Identifier fields encrypted at rest |
| GET | `/patients` | any authenticated | Org-scoped, paginated; no name search (see Conventions above) |
| GET | `/patients/{id}` | any authenticated | Org-scoped |

## Encounters (`/encounters`, Phase 4-6)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/encounters` | clinician, admin, super_admin | Pasted/typed transcript; status -> `transcribed` |
| POST | `/encounters/audio` | clinician, admin, super_admin | Multipart audio upload, transcribed via faster-whisper; status -> `transcribed` |
| POST | `/encounters/live` | clinician, admin, super_admin | Creates an encounter for live recording; status -> `recording` (Phase 5) |
| GET | `/encounters` | any authenticated | Org-scoped (clinicians see only their own), paginated; filter by `status`, `patient_id`; sort by `created_at` |
| GET | `/encounters/{id}` | any authenticated | Full detail: transcript, SOAP note, care plan, code suggestions, billing record |
| POST | `/encounters/{id}/soap-note` | any authenticated | Calls the LLM gateway; status -> `note_generated` |
| PATCH | `/encounters/{id}/soap-note` | any authenticated | Blocked once the note is finalized |
| POST | `/encounters/{id}/soap-note/review` | any authenticated | status -> `under_review` |
| POST | `/encounters/{id}/soap-note/finalize` | any authenticated | Requires `under_review`; status -> `finalized` |
| POST | `/encounters/{id}/care-plan` | any authenticated | Requires a SOAP note to exist |
| PATCH | `/encounters/{id}/care-plan` | any authenticated | |
| POST | `/encounters/{id}/codes` | any authenticated | Requires `finalized`; pgvector retrieval + LLM ranking; status -> `coded` |
| PATCH | `/encounters/{id}/codes/{suggestion_id}` | coder, admin, super_admin | Accept/reject a suggested code |
| POST | `/encounters/{id}/billing-record` | coder, admin, super_admin | Requires `coded`; status -> `billed` (Phase 6) |
| PATCH | `/encounters/{id}/billing-record/{record_id}` | coder, admin, super_admin | Update status/billed amount/payer (Phase 6) |
| POST | `/encounters/bulk-reprocess` | admin, super_admin | Enqueues a background Celery job to regenerate SOAP notes for a batch of encounters (Phase 6); returns 202 + a task id |

Invalid state transitions return `409 Conflict` with a message naming the allowed states (see `app/services/clinical/workflow.py`). Cross-organization access, and (for clinicians) access to another clinician's encounter, returns `404 Not Found` rather than `403`, so existence is not leaked.

Endpoint-level role checks are enforced with `require_roles(...)`; every endpoint also requires a valid access token via `get_current_user`. See `docs/security.md`.

## Background tasks (`/tasks`, Phase 6)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/tasks/{task_id}` | admin, super_admin | Status/result of a Celery task, e.g. one returned by `POST /encounters/bulk-reprocess` |

## Live transcription (`/ws/encounters`, Phase 5)

| Type | Path | Notes |
|---|---|---|
| WebSocket | `/ws/encounters/{encounter_id}/live-transcribe?token=<access_token>` | Streams partial/final transcript segments; see `docs/live-transcription.md` for the full protocol |

The token is a query parameter, not a header, since browsers cannot set custom headers on a WebSocket handshake. The encounter must already exist with `status = recording` (create it with `POST /encounters/live` first). On `stop`, the encounter transitions to `transcribed`, so `POST /encounters/{id}/soap-note` works immediately afterward with no separate step.

## Reimbursement rates (`/reimbursement-rates`, Phase 7)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/reimbursement-rates` | admin, super_admin, coder | Org-scoped, paginated |
| PUT | `/reimbursement-rates` | admin, super_admin | Upsert by `(code_type, code)`: setting an existing code's rate replaces it |
| DELETE | `/reimbursement-rates/{id}` | admin, super_admin | |

## Analytics (`/analytics`, Phase 7)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/analytics/rollup` | admin, super_admin | Computes all 6 rollup types for the caller's org for one day (defaults to yesterday); synchronous, not a background task |
| GET | `/analytics/{rollup_type}` | admin, super_admin | `rollup_type` one of `encounter_volume`, `coding_mix`, `estimated_reimbursement`, `turnaround_time`, `llm_usage`, `clinician_productivity`; requires `start_date`/`end_date` |
| GET | `/analytics/{rollup_type}/export` | admin, super_admin | Same query params plus `format=csv\|xlsx` (default `csv`); returns a file download |

Analytics data is pre-aggregated (nightly via Celery beat, or on demand via `POST /analytics/rollup`), never computed from raw encounter/note/code tables at request time. See `docs/analytics.md` for the exact shape of each metric's rows and what is deliberately not produced ("average review edits per note" has no supporting instrumentation in this codebase, so it is omitted rather than faked).
