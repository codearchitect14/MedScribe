# Database Schema

PostgreSQL 16 with the pgvector extension. Schema is version-controlled through Alembic migrations in `backend/alembic/versions/`. The full current schema is defined by migration `0001_initial_schema`.

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

## Indexes

- B-tree indexes on all foreign keys and common lookup columns (`users.email`, `code_suggestions.code`, `audit_logs.timestamp`).
- IVFFlat pgvector indexes (`vector_cosine_ops`) on `icd10_codes.embedding`, `procedure_codes.embedding`, and `note_embeddings.embedding` for approximate nearest neighbor search.

## Embedding dimension

384, matching `sentence-transformers/all-MiniLM-L6-v2`, the default embedding model configured in `EMBEDDING_MODEL_NAME`. Changing the embedding model to one with a different output dimension requires a new migration that alters the vector column dimension and re-embeds existing rows.
