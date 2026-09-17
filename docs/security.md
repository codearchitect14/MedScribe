# Security

This document covers authentication, authorization, encryption, and audit logging as implemented in Phase 2.

## Authentication

- Registration is admin-invited only. There is no public self-signup endpoint. The first admin for a new organization is created with `scripts/create_admin.py` (a local script, not an HTTP endpoint); every subsequent user is created by an existing admin or super_admin through `POST /users`.
- Login is `POST /auth/login`, an OAuth2 password flow (`OAuth2PasswordRequestForm`: `username` is the user's email, `password` is the password). Failed logins are rate-limited per email through Redis: 5 attempts per 15 minutes by default (`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_SECONDS`).
- Passwords are hashed with bcrypt via passlib. Plaintext passwords are never stored.
- A successful login issues:
  - A short-lived JWT access token (default 30 minutes, `ACCESS_TOKEN_EXPIRE_MINUTES`) returned in the response body. The frontend is expected to hold this in memory only, never in `localStorage`.
  - A longer-lived JWT refresh token (default 7 days, `REFRESH_TOKEN_EXPIRE_DAYS`) set as an `httpOnly`, `secure` (outside development), `SameSite=Strict` cookie scoped to `/auth`. `SameSite` is configurable (`REFRESH_COOKIE_SAMESITE`) for deployments that put the frontend and backend on different domains with no shared reverse-proxy origin - see `docs/deployment.md`.
  - A CSRF token, both returned in the response body and set as a non-`httpOnly` cookie, for the double-submit CSRF pattern described below.
- `POST /auth/refresh` rotates the refresh token: it revokes the presented token's `jti` and issues a new access/refresh/CSRF token set. `POST /auth/logout` revokes the current refresh token's `jti` and clears both cookies.
- Refresh token `jti` values are tracked in Redis (`app/services/token_store.py`) so they can be revoked before their natural JWT expiry, on both logout and rotation.

## CSRF protection

The refresh and logout flow relies on a cookie the browser sends automatically, so it is protected with the double-submit cookie pattern: the CSRF token is set as a readable cookie and must also be sent back as the `X-CSRF-Token` header on `POST /auth/refresh`. A request with a missing or mismatched header is rejected with 403, independent of whether the access token itself is valid.

## Authorization (RBAC)

Roles are `clinician`, `coder`, `admin`, `super_admin` (`app/models/user.py`). Route-level access control is enforced with the `require_roles(...)` FastAPI dependency (`app/api/deps.py`), for example:

```python
current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin))
```

Every authenticated endpoint also depends on `get_current_user`, which validates the JWT access token and loads the corresponding active user.

## Organization-level data isolation

Every query that lists or mutates organization-scoped data filters on `organization_id` server-side (see `app/api/routes/users.py`), not just in the UI. An admin from one organization cannot see or modify users (or, in later phases, patients/encounters) belonging to another organization, even with a valid token. Covered by `tests/test_auth.py::test_organization_isolation`.

## Password reset

`POST /auth/password-reset/request` generates a single-use, time-limited token (default 30 minutes, `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`), stores it in Redis keyed to the user, and sends it by email. The endpoint always returns 204 regardless of whether the email exists, to avoid leaking which addresses are registered. `POST /auth/password-reset/confirm` consumes the token (one-time use) and updates the password hash.

No transactional email provider is wired up yet (out of scope for Phase 2); `app/services/email.py` logs the message instead. Wire in a free-tier provider (Resend, Brevo) there when needed, gated on `ENVIRONMENT != "development"`.

## Rate limiting

Failed login attempts are counted per email in Redis with a sliding TTL window (`app/services/rate_limit.py`). Exceeding the configured threshold returns 429 until the window expires. Successful login clears the counter.

## Audit logging

`app/services/audit.py` writes to the `audit_logs` table (created in Phase 1). Phase 2 records: `login`, `login_failed`, `logout`, `password_reset`, `user_invited`, `role_changed:<from>-><to>`, `user_deactivated`. Each entry carries the acting user id (where known), the entity type/id, a timestamp, and the client IP.

## Encryption at rest

Patient identifier fields (`first_name`, `last_name`, `date_of_birth`, `external_reference`) are encrypted at the application layer with Fernet symmetric encryption (`app/core/encryption.py`), transparent to the ORM via `EncryptedString`/`EncryptedDate` SQLAlchemy type decorators. The key is read from `FIELD_ENCRYPTION_KEY` in the environment and must never be committed to source control. Generate one with:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Because encryption is applied by the ORM's bind/result processing, any code path that writes these columns must go through the SQLAlchemy models, not raw SQL (`scripts/seed_encounters.py` was written this way for exactly this reason).

## Transport and headers

`SecurityHeadersMiddleware` (`app/core/middleware.py`) sets `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, and `Referrer-Policy` on every response, and adds `Strict-Transport-Security` outside of `ENVIRONMENT=development`. CORS is restricted to `FRONTEND_ORIGIN`. TLS termination itself is expected to happen at the hosting platform/reverse proxy in deployed environments (Phase 9).

## Compliance note

This system implements the technical safeguards above, but formal HIPAA compliance additionally requires a signed Business Associate Agreement with hosting/LLM providers and a full compliance audit, which is outside the scope of this reference build. Do not use it with real patient data until that is addressed (see Phase 9 of the development plan).
