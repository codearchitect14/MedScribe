"""End-to-end tests for the Phase 2 auth and RBAC flows.

Requires the postgres and redis services from docker-compose.yml to be
running and migrated (see README.md). Skips automatically if unreachable.
Creates its own organization/users per test run using unique emails, so it
is safe to run against a shared dev database without clobbering other data.
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
    """Creates a fresh organization with one admin, one clinician, one coder."""
    suffix = uuid.uuid4().hex[:8]
    with _db_session() as session:
        org = Organization(name=f"Test Org {suffix}")
        session.add(org)
        session.flush()

        users = {}
        for role in (UserRole.admin, UserRole.clinician, UserRole.coder):
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

    yield {"org_id": org_id, "users": users}


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success_and_failure(org_and_users):
    admin = org_and_users["users"]["admin"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await _login(client, admin["email"], admin["password"])
        assert ok["token_type"] == "bearer"
        assert "access_token" in ok
        assert "csrf_token" in ok

        bad = await client.post(
            "/auth/login", data={"username": admin["email"], "password": "wrong-password"}
        )
        assert bad.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_rbac_enforced_per_role(org_and_users):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_tokens = await _login(client, users["admin"]["email"], users["admin"]["password"])
        clinician_tokens = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        coder_tokens = await _login(client, users["coder"]["email"], users["coder"]["password"])

        admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
        clinician_headers = {"Authorization": f"Bearer {clinician_tokens['access_token']}"}
        coder_headers = {"Authorization": f"Bearer {coder_tokens['access_token']}"}

        # /users listing: admin and coder allowed, clinician forbidden.
        assert (await client.get("/users", headers=admin_headers)).status_code == 200
        assert (await client.get("/users", headers=coder_headers)).status_code == 200
        assert (await client.get("/users", headers=clinician_headers)).status_code == 403

        # No token at all: unauthorized.
        assert (await client.get("/users")).status_code == 401

        # Inviting a user: admin only, not coder.
        invite_payload = {
            "email": f"invitee.{uuid.uuid4().hex[:8]}@example-medscribe.com",
            "full_name": "Invited User",
            "role": "clinician",
            "temporary_password": "InvitePass123!",
        }
        assert (await client.post("/users", json=invite_payload, headers=coder_headers)).status_code == 403
        created = await client.post("/users", json=invite_payload, headers=admin_headers)
        assert created.status_code == 201
        assert created.json()["email"] == invite_payload["email"]

        # /auth/me works for any authenticated role.
        me = await client.get("/auth/me", headers=clinician_headers)
        assert me.status_code == 200
        assert me.json()["role"] == "clinician"


@pytest.mark.asyncio(loop_scope="session")
async def test_refresh_requires_matching_csrf_and_rotates_token(org_and_users):
    admin = org_and_users["users"]["admin"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tokens = await _login(client, admin["email"], admin["password"])
        csrf = tokens["csrf_token"]

        # Missing CSRF header is rejected.
        no_csrf = await client.post("/auth/refresh")
        assert no_csrf.status_code == 403

        # Wrong CSRF header is rejected.
        wrong_csrf = await client.post("/auth/refresh", headers={"X-CSRF-Token": "not-the-token"})
        assert wrong_csrf.status_code == 403

        # Correct CSRF header rotates the token successfully.
        good = await client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert good.status_code == 200
        new_tokens = good.json()
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["csrf_token"] != csrf

        # The old CSRF token no longer matches the rotated cookie.
        reuse = await client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert reuse.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_logout_revokes_refresh_token(org_and_users):
    admin = org_and_users["users"]["admin"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tokens = await _login(client, admin["email"], admin["password"])
        csrf = tokens["csrf_token"]

        logout_response = await client.post("/auth/logout")
        assert logout_response.status_code == 204

        after_logout = await client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert after_logout.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_password_reset_flow(org_and_users):
    admin = org_and_users["users"]["admin"]
    from app.core.redis import get_redis
    from app.services.token_store import store_password_reset_token
    from app.core.security import generate_reset_token

    redis = get_redis()
    token = generate_reset_token()
    await store_password_reset_token(redis, token, admin["id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        confirm = await client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": "BrandNewPass123!"},
        )
        assert confirm.status_code == 204

        old_login = await client.post(
            "/auth/login", data={"username": admin["email"], "password": admin["password"]}
        )
        assert old_login.status_code == 401

        new_login = await client.post(
            "/auth/login", data={"username": admin["email"], "password": "BrandNewPass123!"}
        )
        assert new_login.status_code == 200

        # Token is single-use.
        reuse = await client.post(
            "/auth/password-reset/confirm",
            json={"token": token, "new_password": "AnotherPass123!"},
        )
        assert reuse.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_organization_isolation(org_and_users):
    """A user from one organization must never see users from another."""
    users = org_and_users["users"]
    suffix = uuid.uuid4().hex[:8]

    with _db_session() as session:
        other_org = Organization(name=f"Other Org {suffix}")
        session.add(other_org)
        session.flush()
        other_admin_email = f"other-admin.{suffix}@example-medscribe.com"
        other_admin = User(
            email=other_admin_email,
            hashed_password=hash_password("OtherPass123!"),
            full_name="Other Org Admin",
            role=UserRole.admin,
            organization_id=other_org.id,
            is_active=True,
        )
        session.add(other_admin)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tokens = await _login(client, users["admin"]["email"], users["admin"]["password"])
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        listing = await client.get("/users", headers=headers)
        assert listing.status_code == 200
        emails_seen = {u["email"] for u in listing.json()}
        assert other_admin_email not in emails_seen
