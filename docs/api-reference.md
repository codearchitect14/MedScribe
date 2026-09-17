# API Reference

The authoritative, always-current reference is the live OpenAPI/Swagger UI served by FastAPI at `/docs` (and the raw schema at `/openapi.json`) when the backend is running. This file is a short map of what exists so far; it will grow as later phases add endpoints (analytics in Phase 7, the remaining hardening in Phase 6).

## Auth (`/auth`, Phase 2)

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | OAuth2 password flow; `username` is the email |
| POST | `/auth/refresh` | Rotates the refresh token; requires the `X-CSRF-Token` header |
| POST | `/auth/logout` | Revokes the current refresh token |
| GET | `/auth/me` | Current authenticated user |
| POST | `/auth/password-reset/request` | Always returns 204 |
| POST | `/auth/password-reset/confirm` | Single-use token |

## Users (`/users`, Phase 2)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/users` | admin, super_admin, coder | Org-scoped |
| POST | `/users` | admin, super_admin | Admin-invited registration |
| PATCH | `/users/{id}/role` | admin, super_admin | Audit-logged |
| PATCH | `/users/{id}/deactivate` | admin, super_admin | Audit-logged |

## Patients (`/patients`, Phase 4)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/patients` | clinician, admin, super_admin | Identifier fields encrypted at rest |
| GET | `/patients/{id}` | any authenticated | Org-scoped |

## Encounters (`/encounters`, Phase 4)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/encounters` | clinician, admin, super_admin | Pasted/typed transcript; status -> `transcribed` |
| POST | `/encounters/audio` | clinician, admin, super_admin | Multipart audio upload, transcribed via faster-whisper; status -> `transcribed` |
| POST | `/encounters/live` | clinician, admin, super_admin | Creates an encounter for live recording; status -> `recording` (Phase 5) |
| GET | `/encounters` | any authenticated | Org-scoped; clinicians see only their own |
| GET | `/encounters/{id}` | any authenticated | Full detail: transcript, SOAP note, care plan, code suggestions |
| POST | `/encounters/{id}/soap-note` | any authenticated | Calls the LLM gateway; status -> `note_generated` |
| PATCH | `/encounters/{id}/soap-note` | any authenticated | Blocked once the note is finalized |
| POST | `/encounters/{id}/soap-note/review` | any authenticated | status -> `under_review` |
| POST | `/encounters/{id}/soap-note/finalize` | any authenticated | Requires `under_review`; status -> `finalized` |
| POST | `/encounters/{id}/care-plan` | any authenticated | Requires a SOAP note to exist |
| PATCH | `/encounters/{id}/care-plan` | any authenticated | |
| POST | `/encounters/{id}/codes` | any authenticated | Requires `finalized`; pgvector retrieval + LLM ranking; status -> `coded` |
| PATCH | `/encounters/{id}/codes/{suggestion_id}` | coder, admin, super_admin | Accept/reject a suggested code |

Invalid state transitions return `409 Conflict` with a message naming the allowed states (see `app/services/clinical/workflow.py`). Cross-organization access, and (for clinicians) access to another clinician's encounter, returns `404 Not Found` rather than `403`, so existence is not leaked.

Endpoint-level role checks are enforced with `require_roles(...)`; every endpoint also requires a valid access token via `get_current_user`. See `docs/security.md`.

## Live transcription (`/ws/encounters`, Phase 5)

| Type | Path | Notes |
|---|---|---|
| WebSocket | `/ws/encounters/{encounter_id}/live-transcribe?token=<access_token>` | Streams partial/final transcript segments; see `docs/live-transcription.md` for the full protocol |

The token is a query parameter, not a header, since browsers cannot set custom headers on a WebSocket handshake. The encounter must already exist with `status = recording` (create it with `POST /encounters/live` first). On `stop`, the encounter transitions to `transcribed`, so `POST /encounters/{id}/soap-note` works immediately afterward with no separate step.
