import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_current_user, require_roles
from app.core.db import get_db
from app.core.query import paginate
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.organization import OrganizationOut, UpdateOrganizationRequest
from app.schemas.pagination import Page, PageParams, pagination_params
from app.services.audit import log_audit_event

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationOut)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Organization:
    org = await session.get(Organization, current_user.organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/me", response_model=OrganizationOut)
async def update_my_organization(
    payload: UpdateOrganizationRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> Organization:
    org = await session.get(Organization, current_user.organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.name = payload.name
    await session.commit()
    await session.refresh(org)

    await log_audit_event(
        session,
        user_id=current_user.id,
        action="organization_updated",
        entity_type="organization",
        entity_id=str(org.id),
        ip_address=get_client_ip(request),
    )
    return org


@router.get("", response_model=Page[OrganizationOut])
async def list_organizations(
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(require_roles(UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> Page[OrganizationOut]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    items, total = await paginate(session, stmt, page_params)
    return Page[OrganizationOut](
        items=[OrganizationOut.model_validate(o) for o in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.patch("/{organization_id}/deactivate", response_model=OrganizationOut)
async def deactivate_organization(
    organization_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> Organization:
    org = await session.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.is_active = False
    await session.commit()
    await session.refresh(org)

    await log_audit_event(
        session,
        user_id=current_user.id,
        action="organization_deactivated",
        entity_type="organization",
        entity_id=str(org.id),
        ip_address=get_client_ip(request),
    )
    return org
