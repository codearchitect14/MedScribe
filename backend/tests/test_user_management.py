"""Tests for admin user-management endpoints (invite, role change, deactivate).

Added after live end-to-end testing found that an admin could deactivate or
change the role of their own account through these endpoints with no guard,
which immediately invalidates their own session (and, for a sole admin,
locks the organization out of admin actions entirely) - see
app/api/routes/users.py::change_user_role / deactivate_user.
"""

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


def _db_session() -> Session:
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")
    return Session(engine)


@pytest.fixture
def org_and_users():
    suffix = uuid.uuid4().hex[:8]
    with _db_session() as session:
        org = Organization(name=f"User Mgmt Test Org {suffix}")
        session.add(org)
        session.flush()

        users = {}
        for role in (UserRole.admin, UserRole.clinician):
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
            session.flush()
            users[role.value] = {"email": email, "password": password, "id": user.id}

        session.commit()
        org_id = org.id

    return {"org_id": org_id, "users": users}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_cannot_deactivate_own_account(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token = await _login(client, users["admin"]["email"], users["admin"]["password"])
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.patch(f"/users/{users['admin']['id']}/deactivate", headers=admin_headers)
        assert response.status_code == 400, response.text
        assert "own account" in response.json()["detail"].lower()

        # The account must still be usable afterwards.
        me = await client.get("/auth/me", headers=admin_headers)
        assert me.status_code == 200
        assert me.json()["is_active"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_cannot_change_own_role(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token = await _login(client, users["admin"]["email"], users["admin"]["password"])
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        response = await client.patch(
            f"/users/{users['admin']['id']}/role", json={"role": "clinician"}, headers=admin_headers
        )
        assert response.status_code == 400, response.text
        assert "own role" in response.json()["detail"].lower()

        me = await client.get("/auth/me", headers=admin_headers)
        assert me.json()["role"] == "admin"


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_can_still_deactivate_and_change_role_of_other_users(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_token = await _login(client, users["admin"]["email"], users["admin"]["password"])
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        role_change = await client.patch(
            f"/users/{users['clinician']['id']}/role", json={"role": "coder"}, headers=admin_headers
        )
        assert role_change.status_code == 200, role_change.text
        assert role_change.json()["role"] == "coder"

        deactivate = await client.patch(f"/users/{users['clinician']['id']}/deactivate", headers=admin_headers)
        assert deactivate.status_code == 200, deactivate.text
        assert deactivate.json()["is_active"] is False
