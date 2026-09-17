# Revenue and Analytics (Phase 7)

Backend only, like Phases 4-6: the dashboard UI that consumes these endpoints is Phase 8. This document covers the six metrics, the pre-aggregation design, the reimbursement rate table, and what got deliberately left out rather than faked.

## Design: pre-aggregated rollups, not on-the-fly queries

`analytics_rollups` (migration 0003) is one table for every metric type, rather than one table per metric: `(organization_id, rollup_type, period, dimensions)`, unique on `(organization_id, rollup_type, period)`. `dimensions` is a JSONB array of small, self-describing rows — its exact shape depends on `rollup_type` (documented per metric below). A single flexible table keeps the schema surface small for six metrics that share the same lifecycle (computed once per org per day, read many times) and the same size (one row per group per day, not one row per event).

`app/services/analytics/rollup_service.py` computes all six rollup types for one organization and one day from the real underlying tables (encounters, soap_notes, code_suggestions, billing_records, llm_usage_logs, reimbursement_rates) and upserts the result. It is idempotent: re-running it for the same `(org, day)` overwrites rather than duplicates, so it is safe to call from both the nightly schedule and an on-demand trigger.

Reading a date range (`GET /analytics/{rollup_type}`) fetches the matching pre-aggregated rows and returns them as-is; it never touches the raw encounter/note/code tables at request time. Week/month views are a client-side (or later, server-side) sum over the daily rows already stored, not a separately precomputed granularity.

## Computing rollups: nightly and on-demand

- **Nightly**: `compute_analytics_rollups` (Celery beat, `app/worker.py`, 02:00 UTC) rolls up "yesterday" for every organization with `is_active = true`. Run `celery -A app.worker beat` alongside a worker to actually fire it on schedule.
- **On-demand**: `POST /analytics/rollup` (admin/super_admin) recomputes every rollup type for the caller's own organization for one day (defaults to yesterday). This runs synchronously in the request, not through Celery: it is an aggregation query over already-collected data, not an LLM call, so it is fast enough not to need the background-job treatment Phase 6 gives `POST /encounters/bulk-reprocess`.

## The six metrics

Each function lives in `app/services/analytics/rollup_service.py`; each row shape below is exactly what lands in `dimensions`.

1. **Encounter volume** (`compute_encounter_volume`) — one row per clinician (`{"clinician_id": "...", "count": N}`) plus one row with `clinician_id: null` for the organization total, for encounters created that day.
2. **Coding mix** (`compute_coding_mix`) — one row per ICD-10 chapter / HCPCS category (`{"code_type": "icd10"|"hcpcs", "group": "...", "count": N}`), for code suggestions generated that day, joined against the reference tables from Phase 1.
3. **Estimated reimbursement** (`compute_estimated_reimbursement`) — one row (`{"estimated_reimbursement": total, "codes_matched": N}`): the sum of `reimbursement_rates.rate` for every *accepted* code suggestion that day that has a matching rate row. Explicitly an estimate: it is illustrative rate-table data times accepted-code counts, not a reconciled paid amount. A real billed amount belongs in `billing_records.billed_amount` once a real payer integration exists.
4. **Turnaround time** (`compute_turnaround_time`) — one row (`{"avg_hours_transcript_to_finalize": h, "finalized_count": N, "avg_hours_finalize_to_billed": h, "billed_count": N}`): average hours from `encounters.created_at` to the SOAP note's `reviewed_at` (finalize events that day), and from finalize to `billing_records.created_at` (billing events that day).
5. **LLM usage and cost** (`compute_llm_usage`) — one row per provider (`{"provider": "groq"|"gemini", "tokens_input": N, "tokens_output": N, "calls": N, "estimated_cost_usd": x}`), from `llm_usage_logs`. `estimated_cost_usd` uses `GROQ_COST_PER_1K_TOKENS`/`GEMINI_COST_PER_1K_TOKENS` (both default `0.0`, since both providers are used on free tiers in this reference build); set a real published rate to project cost at paid-tier volume.
6. **Clinician productivity** (`compute_clinician_productivity`) — one row per clinician (`{"clinician_id": "...", "encounters_finalized": N, "avg_hours_to_finalize": h}`), for notes finalized that day.

### What is not produced, and why

The plan names **"average review edits per note"** as part of clinician productivity. This codebase does not instrument how many times a SOAP note was edited (`PATCH /encounters/{id}/soap-note`) before finalization — there is no edit-count column or audit trail for note edits, only the final content. Rather than approximate this with a fabricated number, `compute_clinician_productivity` simply does not produce it. Adding real support would mean either an `edit_count` column on `soap_notes` incremented on each `PATCH`, or an audit-log entry per edit; either is a small, well-scoped addition for whoever picks this up next.

## Reimbursement rate table

`reimbursement_rates` (migration 0003): `(organization_id, code_type, code, rate)`, unique per `(organization_id, code_type, code)`. Reference data an admin adjusts, not hardcoded, per the plan. `PUT /reimbursement-rates` upserts (setting a rate for a code that already has one replaces it, rather than erroring or duplicating); `GET /reimbursement-rates` lists (paginated, admin/super_admin/coder); `DELETE /reimbursement-rates/{id}` removes one. Rates are per-organization only — there is no global default fallback, so a rate table starts empty and an admin populates the codes that matter to their practice.

## CSV / Excel export

`GET /analytics/{rollup_type}/export?start_date=...&end_date=...&format=csv|xlsx` (`app/services/analytics/export.py`) flattens every day's `dimensions` rows across the requested range into one table (each row tagged with its `period`) and returns it as a file download — `text/csv` or a real `.xlsx` workbook (`openpyxl`), not a CSV with an xlsx extension. Same underlying flattened rows feed both formats, so there is exactly one code path per format regardless of which of the six metrics is being exported.

## Access control

Every analytics and reimbursement-rate endpoint requires `admin` or `super_admin` (reimbursement-rate reads also allow `coder`, since coders need to see the rates they are billing against). All of it is organization-scoped: an admin only ever sees or triggers rollups for their own organization, verified in `tests/test_analytics.py::test_analytics_scoped_to_own_organization`.
