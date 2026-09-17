# MedScribe AI

MedScribe AI is a web-based clinical documentation automation platform. It converts doctor-patient transcripts into structured SOAP notes and care plans, suggests ICD-10 and HCPCS medical codes backed by a real, versioned code database, and provides a revenue and analytics dashboard for practice administrators. See `plan (1).md` for the full development plan.

Status: Phase 0 (environment), Phase 1 (database schema and data layer), Phase 2 (authentication and authorization), and Phase 3 (LLM orchestration layer) are complete. Phase 4 and onward (the clinical pipeline itself, live transcription, analytics, frontend) are not yet built.

## Architecture

- Backend: Python, FastAPI, SQLAlchemy 2.0 (async), Alembic migrations.
- Database: PostgreSQL 16 with the pgvector extension for semantic search over medical codes.
- Embeddings: self-hosted Hugging Face sentence-transformers model (`all-MiniLM-L6-v2`), no external embedding API.
- Auth: JWT access/refresh tokens, RBAC, CSRF-protected refresh flow, Redis-backed rate limiting and token revocation, Fernet field-level encryption for patient identifiers. See `docs/security.md`.
- LLM orchestration: a single `app/llm/gateway.py::generate()` entry point over Groq and Gemini free tiers, with failover, quota-aware load balancing, strict JSON schema validation, and request-level caching. See `docs/llm-strategy.md`.
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

9. To exercise the LLM gateway itself, set `GROQ_API_KEY` and/or `GEMINI_API_KEY` in `.env` (both are free-tier). No clinical endpoints call the gateway yet (that starts in Phase 4); `app/llm/gateway.py::generate()` can be called directly, or exercised via the test suite's mocked-provider tests. See `docs/llm-strategy.md`.

## Running tests

```
cd backend
.venv/Scripts/python -m pytest
```

## Deployment

Not yet configured. See Phase 9 of `plan (1).md` for the intended deployment approach (free-tier hosting, CI/CD via GitHub Actions, monitoring).

## Further documentation

- `docs/database-schema.md`: full schema reference
- `docs/datasets.md`: dataset sources and loading instructions
- `docs/security.md`: authentication, authorization, encryption, and audit logging
- `docs/llm-strategy.md`: Groq/Gemini failover strategy, prompt design, and token minimization
