"""Computes the Phase 7 analytics metrics for one organization and one day,
and upserts the results into `analytics_rollups`. Called both by the nightly
Celery beat schedule and by the on-demand trigger endpoint
(POST /analytics/rollup) - the plan explicitly allows either.

Every function here computes real numbers from real rows (encounters,
soap_notes, code_suggestions, billing_records, llm_usage_logs,
reimbursement_rates). Nothing is fabricated: where the schema does not yet
capture a data point the plan mentions (e.g. "average review edits per
note" - there is no edit-count instrumentation), that sub-metric is simply
not produced, and the gap is documented in docs/analytics.md rather than
approximated with a fake number.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.analytics_rollup import AnalyticsRollup, RollupType
from app.models.billing_record import BillingRecord
from app.models.code_suggestion import CodeSuggestion, CodeType
from app.models.encounter import Encounter
from app.models.icd10_code import Icd10Code
from app.models.llm_usage_log import LlmUsageLog
from app.models.procedure_code import ProcedureCode
from app.models.reimbursement_rate import ReimbursementRate
from app.models.soap_note import SoapNote, SoapNoteStatus


def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def compute_encounter_volume(session: AsyncSession, org_id: uuid.UUID, target_date: date) -> list[dict]:
    start, end = _day_bounds(target_date)
    stmt = (
        select(Encounter.clinician_id, func.count(Encounter.id))
        .where(
            Encounter.organization_id == org_id,
            Encounter.created_at >= start,
            Encounter.created_at < end,
        )
        .group_by(Encounter.clinician_id)
    )
    rows = (await session.execute(stmt)).all()
    result = [{"clinician_id": str(clinician_id), "count": count} for clinician_id, count in rows]
    result.append({"clinician_id": None, "count": sum(r["count"] for r in result)})
    return result


async def compute_coding_mix(session: AsyncSession, org_id: uuid.UUID, target_date: date) -> list[dict]:
    start, end = _day_bounds(target_date)

    icd10_stmt = (
        select(Icd10Code.chapter, func.count(CodeSuggestion.id))
        .select_from(CodeSuggestion)
        .join(Encounter, Encounter.id == CodeSuggestion.encounter_id)
        .join(Icd10Code, Icd10Code.code == CodeSuggestion.code)
        .where(
            Encounter.organization_id == org_id,
            CodeSuggestion.code_type == CodeType.icd10,
            CodeSuggestion.created_at >= start,
            CodeSuggestion.created_at < end,
        )
        .group_by(Icd10Code.chapter)
    )
    hcpcs_stmt = (
        select(ProcedureCode.category, func.count(CodeSuggestion.id))
        .select_from(CodeSuggestion)
        .join(Encounter, Encounter.id == CodeSuggestion.encounter_id)
        .join(ProcedureCode, ProcedureCode.code == CodeSuggestion.code)
        .where(
            Encounter.organization_id == org_id,
            CodeSuggestion.code_type == CodeType.hcpcs,
            CodeSuggestion.created_at >= start,
            CodeSuggestion.created_at < end,
        )
        .group_by(ProcedureCode.category)
    )

    icd10_rows = (await session.execute(icd10_stmt)).all()
    hcpcs_rows = (await session.execute(hcpcs_stmt)).all()

    result = [
        {"code_type": "icd10", "group": chapter or "unspecified", "count": count}
        for chapter, count in icd10_rows
    ]
    result += [
        {"code_type": "hcpcs", "group": category or "unspecified", "count": count}
        for category, count in hcpcs_rows
    ]
    return result


async def compute_estimated_reimbursement(
    session: AsyncSession, org_id: uuid.UUID, target_date: date
) -> list[dict]:
    start, end = _day_bounds(target_date)
    stmt = (
        select(func.coalesce(func.sum(ReimbursementRate.rate), 0), func.count(CodeSuggestion.id))
        .select_from(CodeSuggestion)
        .join(
            ReimbursementRate,
            (ReimbursementRate.organization_id == org_id)
            & (ReimbursementRate.code_type == CodeSuggestion.code_type)
            & (ReimbursementRate.code == CodeSuggestion.code),
        )
        .join(Encounter, Encounter.id == CodeSuggestion.encounter_id)
        .where(
            Encounter.organization_id == org_id,
            CodeSuggestion.accepted.is_(True),
            CodeSuggestion.created_at >= start,
            CodeSuggestion.created_at < end,
        )
    )
    total, matched_count = (await session.execute(stmt)).one()
    return [
        {
            # An estimate only: real dollars require a real billing integration
            # (see billing_records.billed_amount once that is reconciled).
            "estimated_reimbursement": float(total),
            "codes_matched": matched_count,
        }
    ]


async def compute_turnaround_time(session: AsyncSession, org_id: uuid.UUID, target_date: date) -> list[dict]:
    start, end = _day_bounds(target_date)

    to_finalize_stmt = (
        select(
            func.avg(func.extract("epoch", SoapNote.reviewed_at - Encounter.created_at) / 3600.0),
            func.count(SoapNote.id),
        )
        .select_from(SoapNote)
        .join(Encounter, Encounter.id == SoapNote.encounter_id)
        .where(
            Encounter.organization_id == org_id,
            SoapNote.status == SoapNoteStatus.finalized,
            SoapNote.reviewed_at >= start,
            SoapNote.reviewed_at < end,
        )
    )
    avg_hours_to_finalize, finalized_count = (await session.execute(to_finalize_stmt)).one()

    # Scalar subquery (rather than a join) so an encounter with more than one
    # historical finalized SoapNote row (regenerated after finalization)
    # cannot fan out a billing record into multiple counted pairs.
    latest_finalized_reviewed_at = (
        select(func.max(SoapNote.reviewed_at))
        .where(SoapNote.encounter_id == Encounter.id, SoapNote.status == SoapNoteStatus.finalized)
        .correlate(Encounter)
        .scalar_subquery()
    )
    to_billed_stmt = (
        select(
            func.avg(func.extract("epoch", BillingRecord.created_at - latest_finalized_reviewed_at) / 3600.0),
            func.count(BillingRecord.id),
        )
        .select_from(BillingRecord)
        .join(Encounter, Encounter.id == BillingRecord.encounter_id)
        .where(
            Encounter.organization_id == org_id,
            BillingRecord.created_at >= start,
            BillingRecord.created_at < end,
        )
    )
    avg_hours_finalize_to_billed, billed_count = (await session.execute(to_billed_stmt)).one()

    return [
        {
            "avg_hours_transcript_to_finalize": float(avg_hours_to_finalize)
            if avg_hours_to_finalize is not None
            else None,
            "finalized_count": finalized_count,
            "avg_hours_finalize_to_billed": float(avg_hours_finalize_to_billed)
            if avg_hours_finalize_to_billed is not None
            else None,
            "billed_count": billed_count,
        }
    ]


async def compute_llm_usage(session: AsyncSession, org_id: uuid.UUID, target_date: date) -> list[dict]:
    start, end = _day_bounds(target_date)
    stmt = (
        select(
            LlmUsageLog.provider,
            func.coalesce(func.sum(LlmUsageLog.tokens_input), 0),
            func.coalesce(func.sum(LlmUsageLog.tokens_output), 0),
            func.count(LlmUsageLog.id),
        )
        .select_from(LlmUsageLog)
        .join(Encounter, Encounter.id == LlmUsageLog.encounter_id)
        .where(
            Encounter.organization_id == org_id,
            LlmUsageLog.created_at >= start,
            LlmUsageLog.created_at < end,
        )
        .group_by(LlmUsageLog.provider)
    )
    rows = (await session.execute(stmt)).all()

    settings = get_settings()
    cost_per_1k = {"groq": settings.groq_cost_per_1k_tokens, "gemini": settings.gemini_cost_per_1k_tokens}

    result = []
    for provider, tokens_in, tokens_out, call_count in rows:
        total_tokens = tokens_in + tokens_out
        rate = cost_per_1k.get(provider, 0.0)
        result.append(
            {
                "provider": provider,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "calls": call_count,
                "estimated_cost_usd": round(total_tokens / 1000.0 * rate, 4),
            }
        )
    return result


async def compute_clinician_productivity(
    session: AsyncSession, org_id: uuid.UUID, target_date: date
) -> list[dict]:
    """Encounters finalized and average time-to-finalize per clinician.

    "Average review edits per note" (named in plan.md Phase 7) is not
    produced: this codebase does not instrument how many times a SOAP note
    was edited before finalization, so that sub-metric would have to be
    fabricated. Documented as a gap in docs/analytics.md rather than
    silently approximated.
    """
    start, end = _day_bounds(target_date)
    stmt = (
        select(
            Encounter.clinician_id,
            func.count(SoapNote.id),
            func.avg(func.extract("epoch", SoapNote.reviewed_at - Encounter.created_at) / 3600.0),
        )
        .select_from(SoapNote)
        .join(Encounter, Encounter.id == SoapNote.encounter_id)
        .where(
            Encounter.organization_id == org_id,
            SoapNote.status == SoapNoteStatus.finalized,
            SoapNote.reviewed_at >= start,
            SoapNote.reviewed_at < end,
        )
        .group_by(Encounter.clinician_id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "clinician_id": str(clinician_id),
            "encounters_finalized": count,
            "avg_hours_to_finalize": float(avg_hours) if avg_hours is not None else None,
        }
        for clinician_id, count, avg_hours in rows
    ]


ROLLUP_COMPUTERS = {
    RollupType.encounter_volume: compute_encounter_volume,
    RollupType.coding_mix: compute_coding_mix,
    RollupType.estimated_reimbursement: compute_estimated_reimbursement,
    RollupType.turnaround_time: compute_turnaround_time,
    RollupType.llm_usage: compute_llm_usage,
    RollupType.clinician_productivity: compute_clinician_productivity,
}


async def _upsert_rollup(
    session: AsyncSession, org_id: uuid.UUID, rollup_type: RollupType, target_date: date, dimensions: list[dict]
) -> None:
    stmt = pg_insert(AnalyticsRollup).values(
        id=uuid.uuid4(),
        organization_id=org_id,
        rollup_type=rollup_type,
        period=target_date,
        dimensions=dimensions,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["organization_id", "rollup_type", "period"],
        set_={"dimensions": dimensions},
    )
    await session.execute(stmt)


async def compute_daily_rollups(
    session: AsyncSession, org_id: uuid.UUID, target_date: date
) -> dict[RollupType, list[dict]]:
    """Computes and upserts every rollup type for one organization and one
    day. Idempotent: re-running it for the same (org, day) overwrites the
    prior result rather than duplicating rows, so this is safe to call both
    from the nightly schedule and from an on-demand recompute request.
    """
    computed: dict[RollupType, list[dict]] = {}
    for rollup_type, compute_fn in ROLLUP_COMPUTERS.items():
        dimensions = await compute_fn(session, org_id, target_date)
        computed[rollup_type] = dimensions
        await _upsert_rollup(session, org_id, rollup_type, target_date, dimensions)

    await session.commit()
    return computed
