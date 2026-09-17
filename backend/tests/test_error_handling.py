"""Tests for the Phase 6 correlation-id middleware and centralized 500 handler."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.correlation import REQUEST_ID_HEADER
from app.core.security import hash_password
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole

settings = get_settings()


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


@pytest.mark.asyncio(loop_scope="session")
async def test_health_response_carries_request_id_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert REQUEST_ID_HEADER in response.headers
        # A well-formed uuid4 was generated since the client sent none.
        uuid.UUID(response.headers[REQUEST_ID_HEADER])


@pytest.mark.asyncio(loop_scope="session")
async def test_client_supplied_request_id_is_echoed_back():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={REQUEST_ID_HEADER: "my-custom-id"})
        assert response.headers[REQUEST_ID_HEADER] == "my-custom-id"


@pytest.mark.asyncio(loop_scope="session")
async def test_unhandled_exception_returns_consistent_500_shape(monkeypatch):
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Error Test Org {suffix}")
        session.add(org)
        session.flush()
        email = f"admin.{suffix}@example-medscribe.com"
        user = User(
            email=email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Error Test Admin",
            role=UserRole.admin,
            organization_id=org.id,
            is_active=True,
        )
        session.add(user)
        session.commit()

    from app.api.routes import users as users_module

    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setattr(users_module, "log_audit_event", _boom)

    # Starlette's ServerErrorMiddleware always re-raises the original
    # exception after generating the error response (so it still reaches
    # server-side logs/the ASGI server), and httpx's ASGITransport re-raises
    # by default when that happens. raise_app_exceptions=False lets this
    # test inspect the actual response the app sent instead.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login", data={"username": email, "password": "TestPass123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = await client.post(
            "/users",
            json={
                "email": f"invitee.{suffix}@example-medscribe.com",
                "full_name": "Invitee",
                "role": "clinician",
                "temporary_password": "InvitePass123!",
            },
            headers=headers,
        )

        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert "request_id" in body
        # The id in the body must match the header on the same response.
        assert body["request_id"] == response.headers[REQUEST_ID_HEADER]
