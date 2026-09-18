import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, require_roles
from app.core.db import get_db
from app.core.query import paginate
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import UserOut
from app.schemas.pagination import Page, PageParams, pagination_params
from app.schemas.user import InviteUserRequest, RoleChangeRequest
from app.services.audit import log_audit_event

router = APIRouter(prefix="/users", tags=["users"])

UserSort = Literal["created_at", "-created_at", "email", "-email"]


@router.get("", response_model=Page[UserOut])
async def list_users(
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    sort: UserSort = Query(default="-created_at"),
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin, UserRole.coder)),
    session: AsyncSession = Depends(get_db),
) -> Page[UserOut]:
    stmt = select(User).where(User.organization_id == current_user.organization_id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    sort_column = User.created_at if sort.lstrip("-") == "created_at" else User.email
    stmt = stmt.order_by(sort_column.desc() if sort.startswith("-") else sort_column.asc())

    items, total = await paginate(session, stmt, page_params)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: InviteUserRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> User:
    existing = await session.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.temporary_password),
        full_name=payload.full_name,
        role=payload.role,
        organization_id=current_user.organization_id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    await log_audit_event(
        session,
        user_id=current_user.id,
        action="user_invited",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
    )

    return user


@router.patch("/{user_id}/role", response_model=UserOut)
async def change_user_role(
    user_id: uuid.UUID,
    payload: RoleChangeRequest,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> User:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role. Ask another admin to do this.",
        )

    user = await session.get(User, user_id)
    if user is None or user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    previous_role = user.role
    user.role = payload.role
    await session.commit()
    await session.refresh(user)

    await log_audit_event(
        session,
        user_id=current_user.id,
        action=f"role_changed:{previous_role.value}->{payload.role.value}",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
    )

    return user


@router.patch("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> User:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account. Ask another admin to do this.",
        )

    user = await session.get(User, user_id)
    if user is None or user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await session.commit()
    await session.refresh(user)

    await log_audit_event(
        session,
        user_id=current_user.id,
        action="user_deactivated",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
    )

    return user
