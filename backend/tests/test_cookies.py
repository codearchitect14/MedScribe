"""Tests for the Phase 9 configurable refresh-cookie SameSite policy
(app/core/cookies.py) - see docs/deployment.md for why this exists."""

from fastapi import Response

from app.core.cookies import set_auth_cookies


def _cookie_headers(response: Response) -> list[str]:
    return [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]


def test_samesite_defaults_to_strict(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "refresh_cookie_samesite", "strict")

    response = Response()
    set_auth_cookies(response, "refresh-token-value", "csrf-token-value")
    headers = _cookie_headers(response)
    assert len(headers) == 2
    for header in headers:
        assert "samesite=strict" in header.lower()


def test_samesite_none_requires_non_development_environment(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "refresh_cookie_samesite", "none")

    # Configured "none" but still in development: must not actually apply,
    # since a browser would reject a non-Secure SameSite=None cookie anyway,
    # and local dev serves over plain HTTP.
    monkeypatch.setattr(settings, "environment", "development")
    dev_response = Response()
    set_auth_cookies(dev_response, "refresh-token-value", "csrf-token-value")
    for header in _cookie_headers(dev_response):
        assert "samesite=none" not in header.lower()
        assert "samesite=strict" in header.lower()

    # Configured "none" and in production: applies, and must be paired with Secure.
    monkeypatch.setattr(settings, "environment", "production")
    prod_response = Response()
    set_auth_cookies(prod_response, "refresh-token-value", "csrf-token-value")
    for header in _cookie_headers(prod_response):
        assert "samesite=none" in header.lower()
        assert "secure" in header.lower()
