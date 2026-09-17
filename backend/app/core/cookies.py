from fastapi import Response

from app.core.config import get_settings

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"


def _samesite(settings) -> str:
    # SameSite=None is only valid (and only accepted by browsers) alongside
    # Secure=true, which this app already restricts to non-development
    # environments - so REFRESH_COOKIE_SAMESITE=none has no effect in local
    # HTTP dev even if set, by construction rather than by convention.
    if settings.refresh_cookie_samesite == "none" and settings.environment != "development":
        return "none"
    return "strict"


def set_auth_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    settings = get_settings()
    secure = settings.environment != "development"
    samesite = _samesite(settings)
    max_age = settings.refresh_token_expire_days * 24 * 60 * 60

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
        path="/auth",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        max_age=max_age,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
