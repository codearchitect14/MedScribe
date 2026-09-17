from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.db import get_db
from app.models.analytics_rollup import AnalyticsRollup, RollupType
from app.models.user import User, UserRole
from app.schemas.analytics import AnalyticsSeriesResponse, RollupOut, RollupTriggerRequest
from app.services.analytics.export import rows_to_csv, rows_to_xlsx
from app.services.analytics.rollup_service import compute_daily_rollups

router = APIRouter(prefix="/analytics", tags=["analytics"])

CAN_VIEW = (UserRole.admin, UserRole.super_admin)

MAX_DATE_RANGE_DAYS = 366


async def _fetch_rollups(
    session: AsyncSession, org_id, rollup_type: RollupType, start_date: date, end_date: date
) -> list[AnalyticsRollup]:
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_date must be >= start_date")
    if (end_date - start_date).days > MAX_DATE_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date range cannot exceed {MAX_DATE_RANGE_DAYS} days",
        )

    stmt = (
        select(AnalyticsRollup)
        .where(
            AnalyticsRollup.organization_id == org_id,
            AnalyticsRollup.rollup_type == rollup_type,
            AnalyticsRollup.period >= start_date,
            AnalyticsRollup.period <= end_date,
        )
        .order_by(AnalyticsRollup.period)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("/rollup", status_code=status.HTTP_200_OK)
async def trigger_rollup(
    payload: RollupTriggerRequest,
    current_user: User = Depends(require_roles(*CAN_VIEW)),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Computes every rollup type for the caller's organization for one day,
    on demand, rather than waiting for the nightly schedule (plan.md Phase
    7 explicitly allows either). This is a fast aggregation query over
    already-collected data, not an LLM call, so it runs synchronously
    rather than going through Celery like the bulk-reprocess endpoint does.
    """
    target_date = payload.period or (date.today() - timedelta(days=1))
    computed = await compute_daily_rollups(session, current_user.organization_id, target_date)
    return {
        "period": target_date.isoformat(),
        "rollup_types": [rt.value for rt in computed],
    }


@router.get("/{rollup_type}", response_model=AnalyticsSeriesResponse)
async def get_rollup_series(
    rollup_type: RollupType,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(require_roles(*CAN_VIEW)),
    session: AsyncSession = Depends(get_db),
) -> AnalyticsSeriesResponse:
    rollups = await _fetch_rollups(session, current_user.organization_id, rollup_type, start_date, end_date)
    return AnalyticsSeriesResponse(
        rollup_type=rollup_type,
        start_date=start_date,
        end_date=end_date,
        rollups=[RollupOut.model_validate(r) for r in rollups],
    )


@router.get("/{rollup_type}/export")
async def export_rollup_series(
    rollup_type: RollupType,
    start_date: date = Query(...),
    end_date: date = Query(...),
    export_format: str = Query(default="csv", pattern="^(csv|xlsx)$", alias="format"),
    current_user: User = Depends(require_roles(*CAN_VIEW)),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """CSV/Excel export for any analytics table (plan.md Phase 7): flattens
    every day's per-group dimension rows in the range into one table, each
    row tagged with the date it belongs to."""
    rollups = await _fetch_rollups(session, current_user.organization_id, rollup_type, start_date, end_date)

    flattened: list[dict] = []
    for rollup in rollups:
        for dimension_row in rollup.dimensions:
            flattened.append({"period": rollup.period.isoformat(), **dimension_row})

    filename = f"{rollup_type.value}_{start_date.isoformat()}_{end_date.isoformat()}.{export_format}"

    if export_format == "xlsx":
        content = rows_to_xlsx(flattened)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = rows_to_csv(flattened)
        media_type = "text/csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
