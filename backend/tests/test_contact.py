"""Tests for the Phase 8 public contact form endpoint."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
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


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clean_contact_rate_limit():
    # httpx's ASGITransport reports a fixed client address (127.0.0.1) for
    # every request by default, so every test in this file (and any rerun
    # of the suite within the same hour) shares one per-IP counter unless
    # it is reset first.
    from app.core.redis import get_redis

    await get_redis().delete("contact_rate_limit:127.0.0.1")
    yield


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_contact_inquiry_and_validation():
    _require_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/contact-requests",
            json={
                "name": "Jane Prospect",
                "email": "jane@example-medscribe.com",
                "organization_name": "Acme Clinic",
                "message": "Interested in a demo.",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Jane Prospect"
        assert "id" in body

        invalid = await client.post(
            "/contact-requests",
            json={"name": "", "email": "not-an-email", "message": ""},
        )
        assert invalid.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_contact_inquiry_rate_limited_per_ip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "name": "Repeat Sender",
            "email": "repeat@example-medscribe.com",
            "message": "hello",
        }
        statuses = []
        for _ in range(6):
            response = await client.post("/contact-requests", json=payload)
            statuses.append(response.status_code)
        assert statuses[:5] == [201] * 5
        assert statuses[5] == 429


@pytest.mark.asyncio(loop_scope="session")
async def test_list_contact_inquiries_requires_super_admin():
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Contact Test Org {suffix}")
        session.add(org)
        session.flush()

        admin_email = f"admin.{suffix}@example-medscribe.com"
        admin = User(
            email=admin_email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Org Admin",
            role=UserRole.admin,
            organization_id=org.id,
            is_active=True,
        )
        super_admin_email = f"super-admin.{suffix}@example-medscribe.com"
        super_admin = User(
            email=super_admin_email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Super Admin",
            role=UserRole.super_admin,
            organization_id=org.id,
            is_active=True,
        )
        session.add_all([admin, super_admin])
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_login = await client.post(
            "/auth/login", data={"username": admin_email, "password": "TestPass123!"}
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        forbidden = await client.get("/contact-requests", headers=admin_headers)
        assert forbidden.status_code == 403

        super_admin_login = await client.post(
            "/auth/login", data={"username": super_admin_email, "password": "TestPass123!"}
        )
        super_admin_headers = {"Authorization": f"Bearer {super_admin_login.json()['access_token']}"}
        allowed = await client.get("/contact-requests", headers=super_admin_headers)
        assert allowed.status_code == 200
        assert "items" in allowed.json()
