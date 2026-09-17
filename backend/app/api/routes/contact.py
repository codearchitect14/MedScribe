from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_redis_client, require_roles
from app.core.db import get_db
from app.core.query import paginate
from app.models.contact_inquiry import ContactInquiry
from app.models.user import User, UserRole
from app.schemas.contact import ContactInquiryOut, CreateContactInquiryRequest
from app.schemas.pagination import Page, PageParams, pagination_params

router = APIRouter(prefix="/contact", tags=["contact"])

RATE_LIMIT_MAX_PER_HOUR = 5


async def _check_and_record_rate_limit(redis: Redis, ip: str | None) -> None:
    """A public, unauthenticated form is an open spam/abuse surface; a
    simple per-IP counter (distinct from the login rate limiter, which is
    per-account) keeps this endpoint from being used to flood the inbox or
    the database.
    """
    key = f"contact_rate_limit:{ip or 'unknown'}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 3600)
    if count > RATE_LIMIT_MAX_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions. Please try again later.",
        )


@router.post("", response_model=ContactInquiryOut, status_code=status.HTTP_201_CREATED)
async def submit_contact_inquiry(
    payload: CreateContactInquiryRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> ContactInquiry:
    await _check_and_record_rate_limit(redis, get_client_ip(request))

    inquiry = ContactInquiry(
        name=payload.name,
        email=payload.email,
        organization_name=payload.organization_name,
        message=payload.message,
    )
    session.add(inquiry)
    await session.commit()
    await session.refresh(inquiry)
    return inquiry


@router.get("", response_model=Page[ContactInquiryOut])
async def list_contact_inquiries(
    page_params: PageParams = Depends(pagination_params),
    # Marketing-site leads are platform-level, not tied to any tenant
    # organization, so this is super_admin only rather than any org admin.
    _current_user: User = Depends(require_roles(UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> Page[ContactInquiryOut]:
    stmt = select(ContactInquiry).order_by(ContactInquiry.created_at.desc())
    items, total = await paginate(session, stmt, page_params)
    return Page[ContactInquiryOut](
        items=[ContactInquiryOut.model_validate(i) for i in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )
