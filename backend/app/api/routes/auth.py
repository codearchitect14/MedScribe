import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_current_user, get_redis_client
from app.core.cookies import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, clear_auth_cookies, set_auth_cookies
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    generate_reset_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    UserOut,
)
from app.services.audit import log_audit_event
from app.services.email import send_email
from app.services.rate_limit import RateLimitExceeded, check_login_rate_limit, clear_login_attempts, record_failed_login
from app.services.token_store import (
    consume_password_reset_token,
    is_refresh_token_valid,
    revoke_refresh_token,
    store_password_reset_token,
    store_refresh_token,
)
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_csrf(request: Request) -> None:
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("x-csrf-token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")


async def _issue_tokens(user: User, redis: Redis, response: Response) -> AccessTokenResponse:
    settings = get_settings()
    access_token = create_access_token(user.id, user.role.value, user.organization_id)
    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_token(redis, user.id, jti)
    csrf_token = generate_csrf_token()
    set_auth_cookies(response, refresh_token, csrf_token)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.access_token_expire_minutes,
        csrf_token=csrf_token,
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> AccessTokenResponse:
    email = form_data.username.strip().lower()

    try:
        await check_login_rate_limit(redis, email)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        await record_failed_login(redis, email)
        await log_audit_event(
            session,
            user_id=user.id if user else None,
            action="login_failed",
            entity_type="user",
            entity_id=email,
            ip_address=get_client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await clear_login_attempts(redis, email)
    await log_audit_event(
        session,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=get_client_ip(request),
    )

    return await _issue_tokens(user, redis, response)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> AccessTokenResponse:
    _verify_csrf(request)

    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    payload = decode_token(refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user_id = uuid.UUID(payload["sub"])
    jti = payload["jti"]

    if not await is_refresh_token_valid(redis, user_id, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is no longer active")

    # Rotate: revoke the used refresh token before issuing a new one.
    await revoke_refresh_token(redis, user_id, jti)

    return await _issue_tokens(user, redis, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> None:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token is not None:
        payload = decode_token(refresh_token, expected_type="refresh")
        if payload is not None:
            user_id = uuid.UUID(payload["sub"])
            await revoke_refresh_token(redis, user_id, payload["jti"])
            await log_audit_event(
                session,
                user_id=user_id,
                action="logout",
                entity_type="user",
                entity_id=str(user_id),
                ip_address=get_client_ip(request),
            )

    clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_password_reset(
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> None:
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    # Always return 204 regardless of whether the account exists, to avoid
    # leaking which email addresses are registered.
    if user is not None and user.is_active:
        token = generate_reset_token()
        await store_password_reset_token(redis, token, user.id)
        await send_email(
            to=user.email,
            subject="MedScribe AI password reset",
            body=f"Use this token to reset your password: {token}",
        )


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> None:
    user_id = await consume_password_reset_token(redis, payload.token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(payload.new_password)
    await session.commit()

    await log_audit_event(
        session,
        user_id=user.id,
        action="password_reset",
        entity_type="user",
        entity_id=str(user.id),
    )
