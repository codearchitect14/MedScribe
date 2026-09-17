# MedScribe AI

MedScribe AI is a web-based clinical documentation automation platform. It converts doctor-patient transcripts into structured SOAP notes and care plans, suggests ICD-10 and HCPCS medical codes backed by a real, versioned code database, and provides a revenue and analytics dashboard for practice administrators. See `plan (1).md` for the full development plan.

Status: Phase 0 (environment), Phase 1 (database schema and data layer), Phase 2 (authentication and authorization), Phase 3 (LLM orchestration layer), Phase 4 (core clinical pipeline), and Phase 5 (live transcription) are complete on the backend. Phase 5's frontend recording component, and Phase 6 onward (backend hardening, analytics, the rest of the frontend), are not yet built.

## Architecture

- Backend: Python, FastAPI, SQLAlchemy 2.0 (async), Alembic migrations.
- Database: PostgreSQL 16 with the pgvector extension for semantic search over medical codes.
- Embeddings: self-hosted Hugging Face sentence-transformers model (`all-MiniLM-L6-v2`), no external embedding API.
- Auth: JWT access/refresh tokens, RBAC, CSRF-protected refresh flow, Redis-backed rate limiting and token revocation, Fernet field-level encryption for patient identifiers. See `docs/security.md`.
- LLM orchestration: a single `app/llm/gateway.py::generate()` entry point over Groq and Gemini free tiers, with failover, quota-aware load balancing, strict JSON schema validation, and request-level caching. See `docs/llm-strategy.md`.
- Clinical pipeline: transcript ingestion (pasted text, uploaded audio, or live in-browser recording, all via self-hosted faster-whisper), SOAP note generation/review/finalize, care plan generation, and pgvector-backed ICD-10/HCPCS code suggestion with clinician/coder accept-reject, all gated by an explicit encounter status workflow.
- Live transcription: a WebSocket endpoint streams partial/final transcript segments back to the client in near real time, with a bounded worker pool, periodic checkpointing, and a config flag to fall back to the batch upload path. See `docs/live-transcription.md`.
- Queue/cache: Redis.
- Containerization: Docker Compose.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ and `uv` (or `pip`) for running backend scripts outside a container

## Local setup

1. Copy the environment template and adjust host ports if 5432/6379 are already in use on your machine:

   ```
   cp .env.example .env
   ```

2. Start Postgres (with pgvector) and Redis:

   ```
   docker compose up -d postgres redis
   ```

3. Install backend dependencies:

   ```
   cd backend
   uv venv .venv
   uv pip install -e . --python .venv
   cp ../.env.example .env
   ```

4. Run database migrations:

   ```
   .venv/Scripts/python -m alembic upgrade head        # Windows
   .venv/bin/python -m alembic upgrade head             # macOS/Linux
   ```

5. Load ICD-10 and HCPCS reference codes (generates embeddings, see `docs/datasets.md`):

   ```
   python -m scripts.load_reference_codes
   ```

6. Seed demo organization, users, patients, and encounters:

   ```
   python -m scripts.seed_encounters
   ```

7. Create the first admin user for an organization (registration is admin-invited only; there is no public self-signup):

   ```
   python -m scripts.create_admin --org "Your Clinic" --email admin@example.com --password "ChangeMe123!" --name "Admin User"
   ```

8. Start the API:

   ```
   .venv/Scripts/python -m uvicorn app.main:app --reload   # or: docker compose up -d backend worker
   ```

   Then log in at `POST /auth/login` (OAuth2 password flow: `username` is the email) and use the returned bearer token for subsequent requests. See `docs/security.md` for the full auth flow, RBAC, and CSRF details.

9. Set `GROQ_API_KEY` and/or `GEMINI_API_KEY` in `.env` to exercise the clinical pipeline against real providers (both are free-tier). Create a patient, then an encounter:

   ```
   POST /patients                              {"first_name": "...", "last_name": "..."}
   POST /encounters                             {"patient_id": "...", "raw_transcript": "Doctor: ... Patient: ..."}
   POST /encounters/audio                       multipart: patient_id + audio file (transcribed via faster-whisper)
   POST /encounters/{id}/soap-note               generate
   PATCH /encounters/{id}/soap-note              edit
   POST /encounters/{id}/soap-note/review        transcribed note -> under review
   POST /encounters/{id}/soap-note/finalize      under review -> finalized (required before coding)
   POST /encounters/{id}/care-plan               generate (from the SOAP note's Assessment/Plan only)
   POST /encounters/{id}/codes                   generate ICD-10/HCPCS suggestions (pgvector + LLM, finalized notes only)
   PATCH /encounters/{id}/codes/{suggestion_id}   accept/reject (coder/admin only)
   GET  /encounters/{id}                          full detail: transcript, note, care plan, code suggestions
   ```

   Without real API keys, run the test suite instead (it mocks the provider adapters).

10. For live in-browser transcription, first create the encounter, then open a WebSocket:

    ```
    POST /encounters/live                                        {"patient_id": "..."}   -> status "recording"
    WS   /ws/encounters/{id}/live-transcribe?token=<access_token>
    ```

    See `docs/live-transcription.md` for the full message protocol (binary PCM16 audio in; `queued`/`ready`/`partial`/`final`/`stopped`/`error` JSON messages out).

## Running tests

```
cd backend
.venv/Scripts/python -m pytest -m "not slow"
```

The `slow` marker covers tests that load the Whisper model (audio transcription). Run them as a separate invocation:

```
.venv/Scripts/python -m pytest -m slow
```

On memory-constrained hosts, run them separately rather than in one combined `pytest` invocation: loading sentence-transformers/torch (embeddings) and faster-whisper/ctranslate2 (transcription) in the same process at the same time can exceed available memory on a small dev machine (`mkl_malloc: failed to allocate memory`). This is a resource ceiling of a constrained host, not a code issue — both suites pass reliably run separately, and in a real deployment Whisper runs in its own worker process anyway (see Phase 5 of `plan (1).md`).

## Deployment

Not yet configured. See Phase 9 of `plan (1).md` for the intended deployment approach (free-tier hosting, CI/CD via GitHub Actions, monitoring).

## Further documentation

- `docs/database-schema.md`: full schema reference
- `docs/datasets.md`: dataset sources and loading instructions
- `docs/security.md`: authentication, authorization, encryption, and audit logging
- `docs/llm-strategy.md`: Groq/Gemini failover strategy, prompt design, and token minimization
- `docs/api-reference.md`: endpoint summary; the live OpenAPI docs at `/docs` are authoritative
- `docs/live-transcription.md`: the WebSocket protocol, audio format, worker pool, checkpointing, and fallback behavior
