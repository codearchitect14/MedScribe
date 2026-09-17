import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.db import get_db
from app.core.query import paginate
from app.models.reimbursement_rate import ReimbursementRate
from app.models.user import User, UserRole
from app.schemas.pagination import Page, PageParams, pagination_params
from app.schemas.reimbursement_rate import ReimbursementRateOut, UpsertReimbursementRateRequest

router = APIRouter(prefix="/reimbursement-rates", tags=["reimbursement-rates"])

CAN_READ = (UserRole.admin, UserRole.super_admin, UserRole.coder)
CAN_WRITE = (UserRole.admin, UserRole.super_admin)


@router.get("", response_model=Page[ReimbursementRateOut])
async def list_reimbursement_rates(
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(require_roles(*CAN_READ)),
    session: AsyncSession = Depends(get_db),
) -> Page[ReimbursementRateOut]:
    stmt = (
        select(ReimbursementRate)
        .where(ReimbursementRate.organization_id == current_user.organization_id)
        .order_by(ReimbursementRate.code_type, ReimbursementRate.code)
    )
    items, total = await paginate(session, stmt, page_params)
    return Page[ReimbursementRateOut](
        items=[ReimbursementRateOut.model_validate(r) for r in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.put("", response_model=ReimbursementRateOut, status_code=status.HTTP_200_OK)
async def upsert_reimbursement_rate(
    payload: UpsertReimbursementRateRequest,
    current_user: User = Depends(require_roles(*CAN_WRITE)),
    session: AsyncSession = Depends(get_db),
) -> ReimbursementRate:
    """Reference data an admin adjusts, not hardcoded (plan.md Phase 7):
    setting a rate for a code that already has one replaces it."""
    stmt = (
        pg_insert(ReimbursementRate)
        .values(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            code_type=payload.code_type,
            code=payload.code,
            rate=payload.rate,
        )
        .on_conflict_do_update(
            index_elements=["organization_id", "code_type", "code"],
            set_={"rate": payload.rate},
        )
        .returning(ReimbursementRate)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reimbursement_rate(
    rate_id: uuid.UUID,
    current_user: User = Depends(require_roles(*CAN_WRITE)),
    session: AsyncSession = Depends(get_db),
) -> None:
    rate = await session.get(ReimbursementRate, rate_id)
    if rate is None or rate.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reimbursement rate not found")
    await session.delete(rate)
    await session.commit()
