"""Nightly (or on-demand) analytics rollup computation (plan.md Phase 7).

Same async/Celery bridging pattern as app/tasks/bulk_reprocess.py: the
clinical/analytics services are async, Celery's default execution model is
synchronous per task, so the task drives its own event loop via
asyncio.run() around a dedicated async function with its own fresh
AsyncSession, rather than reusing any request-scoped ones.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import select

from app.core.db import async_session_factory
from app.models.organization import Organization
from app.services.analytics.rollup_service import compute_daily_rollups
from app.worker import celery_app

logger = structlog.get_logger(__name__)


async def _compute_rollups_for_all_organizations(target_date: date) -> dict:
    summary: dict[str, str] = {}
    async with async_session_factory() as session:
        org_ids = (
            await session.execute(select(Organization.id).where(Organization.is_active.is_(True)))
        ).scalars().all()

        for org_id in org_ids:
            try:
                await compute_daily_rollups(session, org_id, target_date)
                summary[str(org_id)] = "ok"
            except Exception as exc:  # noqa: BLE001 - one org's failure must not abort the run
                logger.exception("analytics_rollup.org_failed", organization_id=str(org_id))
                summary[str(org_id)] = f"error: {exc}"

    logger.info("analytics_rollup.completed", period=target_date.isoformat(), organizations=len(summary))
    return {"period": target_date.isoformat(), "organizations": summary}


def _resolve_target_date(target_date_iso: str | None) -> date:
    if target_date_iso is None:
        # Nightly run: roll up "yesterday" (the day that just fully ended).
        return (datetime.now(UTC) - timedelta(days=1)).date()
    return date.fromisoformat(target_date_iso)


@celery_app.task(name="compute_analytics_rollups")
def compute_analytics_rollups_task(target_date_iso: str | None = None) -> dict:
    target = _resolve_target_date(target_date_iso)
    return asyncio.run(_compute_rollups_for_all_organizations(target))
