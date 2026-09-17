# Database Schema

PostgreSQL 16 with the pgvector extension. Schema is version-controlled through Alembic migrations in `backend/alembic/versions/`: `0001` (initial schema), `0002` (encrypts patient identifier columns), `0003` (adds `reimbursement_rates` and `analytics_rollups`, Phase 7).

## Tables

- `organizations`: clinic/practice tenant.
- `users`: id, email, hashed_password, full_name, role (clinician, coder, admin, super_admin), organization_id, is_active.
- `patients`: minimal demographic fields, scoped to an organization.
- `encounters`: one per doctor-patient visit; carries the raw transcript and workflow status (`recording -> transcribed -> note_generated -> under_review -> finalized -> coded -> billed`).
- `soap_notes`: generated Subjective/Objective/Assessment/Plan sections per encounter, with review metadata.
- `care_plans`: generated care plan content per encounter, with review metadata.
- `code_suggestions`: ICD-10 or HCPCS code suggestions per encounter, with a confidence score and an accept/reject flag.
- `icd10_codes`: reference table of ICD-10-CM codes with a pgvector embedding column for semantic search.
- `procedure_codes`: reference table of HCPCS (and a small labeled CPT sample) codes with a pgvector embedding column.
- `note_embeddings`: embeddings of historical notes, for semantic search across past encounters.
- `billing_records`: applied codes, estimated reimbursement, billed amount, and payer per encounter.
- `audit_logs`: user action audit trail.
- `llm_usage_logs`: per-call token usage and latency, by provider and model, for cost tracking and analytics.
- `reimbursement_rates` (Phase 7): a configurable, per-organization rate per `(code_type, code)`, used only to produce an *estimated* revenue figure; unique on `(organization_id, code_type, code)`. See `docs/analytics.md`.
- `analytics_rollups` (Phase 7): one pre-aggregated row per `(organization_id, rollup_type, period)`, unique on that triple; `dimensions` (JSONB) holds the metric's per-group rows. One flexible table for all six analytics metrics rather than one table per metric. See `docs/analytics.md`.

## Indexes

- B-tree indexes on all foreign keys and common lookup columns (`users.email`, `code_suggestions.code`, `audit_logs.timestamp`).
- IVFFlat pgvector indexes (`vector_cosine_ops`) on `icd10_codes.embedding`, `procedure_codes.embedding`, and `note_embeddings.embedding` for approximate nearest neighbor search.

## Embedding dimension

384, matching `sentence-transformers/all-MiniLM-L6-v2`, the default embedding model configured in `EMBEDDING_MODEL_NAME`. Changing the embedding model to one with a different output dimension requires a new migration that alters the vector column dimension and re-embeds existing rows.
