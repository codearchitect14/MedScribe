# HIPAA-Style Safeguards Review (Phase 9)

This document is the Phase 9 compliance review the plan asks for: a checklist of where each HIPAA-style safeguard category is actually implemented in this codebase, plus the two things not documented anywhere else yet - minimum necessary data collection, and a data retention/deletion policy - and the compliance disclaimer that governs all of it.

**Read this first**: this system implements the *technical* safeguards below. It is not HIPAA compliant, and cannot become compliant through code alone. Formal compliance additionally requires a signed Business Associate Agreement (BAA) with every vendor that touches PHI - the hosting provider, and, if real patient data is ever processed, Groq and/or Google (neither currently offers a BAA on their free tier, to the authors' knowledge; verify directly before any production use) - plus a full compliance audit by a qualified party. **Do not use this system with real patient data until that is in place.** Everything in this repository, including its seed/test data (`docs/datasets.md`), is synthetic or de-identified for exactly this reason.

## Safeguards checklist

| Category | Where | Notes |
|---|---|---|
| **Access controls** | `app/api/deps.py` (`require_roles`), `app/models/user.py` (clinician/coder/admin/super_admin) | Every endpoint requires a valid access token; role checks are per-endpoint, not just per-page. See `docs/security.md`. |
| **Organization-level data isolation** | Every list/detail query filters on `organization_id` server-side | Enforced at the query layer, not the UI - verified by `tests/test_auth.py::test_organization_isolation` and the analytics/encounters equivalents. |
| **Audit logging** | `app/services/audit.py`, `audit_logs` table | Login, logout, password reset, user invited/role-changed/deactivated, organization updated. See `docs/security.md`. Does not yet cover read access to clinical records (see Gaps, below). |
| **Encryption in transit** | `SecurityHeadersMiddleware` (HSTS outside dev), CORS restricted to one origin | TLS termination itself happens at the hosting platform, not in application code - see `docs/data-flow-review.md`, item 2. |
| **Encryption at rest** | `app/core/encryption.py` (Fernet, patient identifier fields) | See `docs/security.md`. Clinical text (transcripts, notes) is *not* separately field-encrypted - it relies on the database's own at-rest encryption, which is the hosting provider's responsibility to enable (most managed Postgres offerings, including the free tiers named in `plan (1).md`, enable disk-level encryption by default; verify for the one actually chosen). |
| **Minimum necessary data collection** | `app/models/patient.py` | See below. |
| **Data retention / deletion** | Not yet implemented as code | See below. |
| **Authentication strength** | JWT access/refresh with rotation, CSRF-protected refresh, Redis-backed login rate limiting | `docs/security.md`. |

## Minimum necessary data collection

The `patients` table (`app/models/patient.py`) collects exactly: first name, last name, date of birth, sex, and an optional external reference id. No address, phone number, SSN, insurance id, or any other identifier is collected anywhere in the schema. This was a deliberate design constraint from Phase 1 (`docs/database-schema.md`: "store only the minimum needed, no unnecessary PHI fields"), re-confirmed here rather than newly added: reviewing the full schema (`docs/database-schema.md`) turns up no field outside `patients` and the clinical content tables (`encounters.raw_transcript`, `soap_notes`, `care_plans`) that holds patient-identifying or clinical information.

## Data retention and deletion policy

Not yet enforced by any code in this repository - this section states the intended policy so a future implementer has a specification to build against, rather than inventing one under deployment pressure:

- **Clinical records** (transcripts, SOAP notes, care plans, code suggestions, billing records) should be retained only as long as the operating organization's own regulatory obligations require (typically several years post-encounter in most US jurisdictions; this varies by state and specialty - confirm with counsel for a real deployment) and deleted thereafter.
- **Audit logs** should be retained separately from, and typically longer than, the clinical records they describe, since their purpose is to reconstruct who accessed what after the fact.
- **A deactivated user** (`PATCH /users/{id}/deactivate`) is not deleted - deactivation only prevents login. This is intentional: audit log entries and encounter records reference the user by id, and deleting the row would either break those references or require anonymizing them, which the current schema does not implement.
- **Not implemented**: there is no scheduled job that purges data past a retention window, and no per-patient "delete my data" endpoint. Both are reasonable, scoped follow-ups - the former as a Celery beat task alongside the existing analytics rollup schedule (`app/worker.py`), the latter as an admin-only endpoint that would need to decide what "delete" means for a record an audit log or a billing record still references (hard delete vs. anonymize-in-place).

## Known gaps (not implemented, stated plainly)

- No audit log entry is written for *reading* a clinical record (`GET /encounters/{id}`), only for the auth/user-management/organization actions listed in `docs/security.md`. A HIPAA-aligned deployment handling real PHI would want read access logged too.
- No automated data retention/deletion job (above).
- No BAA-backed LLM provider is configured; Groq and Gemini are used on their free/standard tiers, per `docs/llm-strategy.md`.
