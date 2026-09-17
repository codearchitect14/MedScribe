"""Tests for the Phase 6 organizations endpoints and RBAC around them."""

import uuid

import pytest
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


@pytest.fixture
def org_and_users():
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Org Test {suffix}")
        session.add(org)
        session.flush()

        users = {}
        for role in (UserRole.admin, UserRole.clinician, UserRole.super_admin):
            email = f"{role.value}.{suffix}@example-medscribe.com"
            password = "TestPass123!"
            user = User(
                email=email,
                hashed_password=hash_password(password),
                full_name=f"Test {role.value}",
                role=role,
                organization_id=org.id,
                is_active=True,
            )
            session.add(user)
            users[role.value] = {"email": email, "password": password}

        session.commit()
        org_id = org.id

    return {"org_id": org_id, "users": users}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_get_my_organization(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        response = await client.get("/organizations/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["id"] == str(org_and_users["org_id"])


@pytest.mark.asyncio(loop_scope="session")
async def test_update_my_organization_requires_admin(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        admin_token = await _login(client, users["admin"]["email"], users["admin"]["password"])

        forbidden = await client.patch(
            "/organizations/me",
            json={"name": "New Name"},
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        assert forbidden.status_code == 403

        allowed = await client.patch(
            "/organizations/me",
            json={"name": "Renamed Org"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["name"] == "Renamed Org"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_organizations_super_admin_only(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token = await _login(client, users["admin"]["email"], users["admin"]["password"])
        super_admin_token = await _login(client, users["super_admin"]["email"], users["super_admin"]["password"])

        forbidden = await client.get("/organizations", headers={"Authorization": f"Bearer {admin_token}"})
        assert forbidden.status_code == 403

        allowed = await client.get("/organizations", headers={"Authorization": f"Bearer {super_admin_token}"})
        assert allowed.status_code == 200
        body = allowed.json()
        assert "items" in body and "total" in body
