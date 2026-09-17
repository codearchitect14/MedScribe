# Deployment (Phase 9)

This system has not been deployed to a public URL in this environment - doing so needs real hosting accounts and credentials this development session does not have. What follows is the concrete deployment path: what to provision, in what order, the two decisions that actually affect whether it works, and the checklist for the final walkthrough plan.md asks for. `.github/workflows/ci.yml` runs lint/type-check/test/build/audit on every push and PR; a deploy step was deliberately not wired into it (see "CI/CD", below).

## Two decisions that matter more than the specific host

**1. Your Postgres host must support the `pgvector` extension.** This is not universal on free tiers. Confirmed to work: [Supabase](https://supabase.com) (free tier, `pgvector` pre-installed), [Neon](https://neon.tech) (free tier, `CREATE EXTENSION vector` supported). A generic "free Postgres" offering may not support it - check before provisioning, not after `alembic upgrade head` fails on migration `0001`.

**2. Decide whether the frontend and backend will share one origin or not**, and set `REFRESH_COOKIE_SAMESITE` accordingly (`app/core/cookies.py`, `docs/frontend.md`):
   - **Same origin** (recommended): put both behind one reverse-proxy domain (e.g. a platform that supports path-based routing, or an Nginx/Caddy layer in front of both). Leave `REFRESH_COOKIE_SAMESITE=strict` (the default). This is what local dev already does via the Vite proxy (`frontend/vite.config.ts`) - deploying this way means the auth flow behaves identically to what was verified in Phase 8.
   - **Different origins** (e.g. frontend on Vercel, backend on Render, as separate domains with no proxy): set `REFRESH_COOKIE_SAMESITE=none` on the backend. This requires HTTPS (already enforced: `secure` is tied to `ENVIRONMENT != development`), and the frontend must call the backend directly rather than through a dev-only proxy - set `VITE_API_BASE_URL` to the backend's full URL and rebuild.

Whichever is chosen, verify the actual login → reload → still-logged-in flow against the deployed URLs before declaring the walkthrough (below) complete - this exact interaction is what broke in Phase 8 before the proxy/cookie work, and is the one thing most likely to silently fail after a topology change.

## Backend

1. Provision Postgres (pgvector-capable, see above) and Redis (Upstash free tier, or self-hosted alongside the app).
2. Deploy `backend/Dockerfile` to a container host (Render, Railway, Fly.io, or a free-tier VPS - all named in `plan (1).md`). Set every variable from `.env.example` as real secrets on the host; generate fresh `JWT_SECRET`, `CSRF_SECRET`, and `FIELD_ENCRYPTION_KEY` values for production (never reuse a value that has appeared in a local `.env` or in this conversation).
3. Run `alembic upgrade head` against the production database once, then `python -m scripts.load_reference_codes` to populate the ICD-10/HCPCS reference tables (`docs/datasets.md`).
4. Create the first admin: `python -m scripts.create_admin --org "..." --email ... --password ... --name ...` (registration is admin-invited only - `docs/security.md`).
5. Deploy a second instance of the same image running `celery -A app.worker worker` (background tasks - `docs/hardening.md`), and a third running `celery -A app.worker beat` (the nightly analytics rollup - `docs/analytics.md`). Both need the same environment variables as the API instance.
6. Set `GROQ_API_KEY` and/or `GEMINI_API_KEY` to exercise the clinical pipeline for real - without them, generation endpoints fail closed with a clean error (verified in Phase 8), which is safe but not useful for the final walkthrough.

## Frontend

1. `cd frontend && npm run build` produces a static `dist/`; deploy it to Vercel or Netlify (both free-tier, both named in `plan (1).md`), or serve it from the same container as the backend if going the same-origin route above.
2. Set the frontend's env vars per the origin decision above (either nothing extra, if proxied through the same domain, or `VITE_API_BASE_URL` pointing at the backend).
3. Optionally set `VITE_SENTRY_DSN` (`frontend/src/lib/monitoring.ts`) for error tracking (see Monitoring, below).

## Monitoring

- **Error tracking**: set `SENTRY_DSN` (backend, `app/core/monitoring.py`) and/or `VITE_SENTRY_DSN` (frontend) to a free-tier Sentry project's DSN. Both are no-ops until set - nothing else needs to change. Neither sends request/response bodies or PII (`send_default_pii: False` on both sides), consistent with `docs/hardening.md`'s structured-logging posture.
- **Uptime monitoring**: point a free [UptimeRobot](https://uptimerobot.com) monitor at the backend's `GET /health` endpoint (already exists, returns `{"status": "ok"}`, no auth required) and at the frontend's root URL. This is external configuration, not application code - there is nothing to build for it.

## CI/CD

`.github/workflows/ci.yml` runs on every push and pull request to `main`: backend lint + migrate + test + dependency audit, frontend type-check + lint + build + dependency audit. It does **not** include a deploy-on-merge job. That was a deliberate choice, not an oversight: an automatic-deploy workflow needs real hosting secrets (a Render/Railway API token or deploy-hook URL, Vercel/Netlify project credentials) configured in the repository, which this environment cannot provision without the account owner's involvement, and wiring one up untested would be worse than not having one. Add a deploy job once those secrets exist - most of the hosts named above (Render, Vercel, Netlify) also support deploying automatically on push via their own native GitHub integration, which is simpler than a custom Action for a single-service deployment and is the more realistic path for this project.

## Final walkthrough checklist (plan.md Phase 9)

Once deployed, confirm end to end against the real URLs, not localhost:

- [ ] Public homepage loads, login button reachable from every public page
- [ ] Login → dashboard, session survives a hard page reload (the specific thing the origin/cookie decision above affects)
- [ ] Create a patient, create an encounter (text, upload, and live-record paths)
- [ ] Generate a SOAP note, review, finalize (requires a real `GROQ_API_KEY`/`GEMINI_API_KEY`)
- [ ] Generate a care plan and code suggestions; accept/reject a code as a coder
- [ ] Create a billing record
- [ ] Trigger an analytics rollup and view it on the dashboard; export CSV/Excel
- [ ] Confirm `GET /health` and the frontend root both respond, and both monitors (if configured) show green
