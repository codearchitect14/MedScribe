"""Tests for the Phase 6 background bulk-reprocessing Celery task.

Two layers are tested separately, deliberately not through Celery's eager
mode: eager mode runs the task inline via asyncio.run(), which cannot be
called from within an already-running event loop - exactly the situation
an async test driving the HTTP endpoint is in. A real Celery worker never
has this problem (it calls the task from a fresh process with no loop
running yet), so this is purely a testability wrinkle, not a production bug.

- test_bulk_reprocess_enqueues_and_rejects_cross_org: HTTP-level. Patches
  `.delay` to a stub so the endpoint's own logic (org-ownership validation,
  202 + task id) is exercised without actually running the task.
- test_bulk_reprocess_task_logic_regenerates_notes: task-level. Awaits the
  task's inner async function directly, which is an ordinary coroutine and
  therefore safe to await from the test's own event loop.
"""

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.llm import gateway
from app.llm.adapters.base import ProviderResponse
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole

settings = get_settings()

SOAP_JSON = json.dumps({"subjective": "s", "objective": "o", "assessment": "a", "plan": "p"})


class AlwaysSoapAdapter:
    name = "groq"

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        return ProviderResponse(content=SOAP_JSON, tokens_input=10, tokens_output=10, model="mock-model")


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


@pytest.fixture
def scripted_adapter(monkeypatch):
    adapter = AlwaysSoapAdapter()
    monkeypatch.setitem(gateway.ADAPTERS, "groq", adapter)
    monkeypatch.setitem(gateway.ADAPTERS, "gemini", adapter)
    return adapter


@pytest.fixture
def clinician():
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Bulk Reprocess Org {suffix}")
        session.add(org)
        session.flush()
        email = f"clinician.{suffix}@example-medscribe.com"
        user = User(
            email=email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Bulk Reprocess Clinician",
            role=UserRole.admin,
            organization_id=org.id,
            is_active=True,
        )
        session.add(user)
        session.commit()

    return {"email": email, "password": "TestPass123!"}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_reprocess_enqueues_and_rejects_cross_org(clinician, monkeypatch):
    from app.api.routes import encounters as encounters_module

    class _FakeAsyncResult:
        id = "fake-task-id-123"

    captured = {}

    def _fake_delay(encounter_ids):
        captured["encounter_ids"] = encounter_ids
        return _FakeAsyncResult()

    monkeypatch.setattr(encounters_module.bulk_reprocess_encounters_task, "delay", _fake_delay)

    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        other_org = Organization(name=f"Other Bulk Org {suffix}")
        session.add(other_org)
        session.flush()
        other_email = f"other.{suffix}@example-medscribe.com"
        other_user = User(
            email=other_email,
            hashed_password=hash_password("TestPass123!"),
            full_name="Other Org User",
            role=UserRole.clinician,
            organization_id=other_org.id,
            is_active=True,
        )
        session.add(other_user)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _login(client, clinician["email"], clinician["password"])
        headers = {"Authorization": f"Bearer {token}"}

        encounter_ids = []
        for _ in range(2):
            patient = await client.post(
                "/patients", json={"first_name": "Bulk", "last_name": "Patient"}, headers=headers
            )
            encounter = await client.post(
                "/encounters",
                json={"patient_id": patient.json()["id"], "raw_transcript": "Doctor: hi. Patient: hi."},
                headers=headers,
            )
            encounter_ids.append(encounter.json()["id"])

        response = await client.post(
            "/encounters/bulk-reprocess",
            json={"encounter_ids": encounter_ids},
            headers=headers,
        )
        assert response.status_code == 202, response.text
        assert response.json()["task_id"] == "fake-task-id-123"
        assert sorted(captured["encounter_ids"]) == sorted(encounter_ids)

        other_token = await _login(client, other_email, "TestPass123!")
        other_headers = {"Authorization": f"Bearer {other_token}"}
        other_patient = await client.post(
            "/patients", json={"first_name": "Other", "last_name": "Org"}, headers=other_headers
        )
        other_encounter = await client.post(
            "/encounters",
            json={"patient_id": other_patient.json()["id"], "raw_transcript": "x"},
            headers=other_headers,
        )

        cross_org = await client.post(
            "/encounters/bulk-reprocess",
            json={"encounter_ids": [other_encounter.json()["id"]]},
            headers=headers,
        )
        assert cross_org.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_bulk_reprocess_task_logic_regenerates_notes(clinician, scripted_adapter):
    from app.tasks.bulk_reprocess import _bulk_reprocess

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _login(client, clinician["email"], clinician["password"])
        headers = {"Authorization": f"Bearer {token}"}

        encounter_ids = []
        for _ in range(3):
            patient = await client.post(
                "/patients", json={"first_name": "Bulk", "last_name": "Patient"}, headers=headers
            )
            encounter = await client.post(
                "/encounters",
                json={"patient_id": patient.json()["id"], "raw_transcript": "Doctor: hi. Patient: hi."},
                headers=headers,
            )
            encounter_ids.append(encounter.json()["id"])

        # One bad id mixed in: must be reported as failed without aborting the batch.
        bad_id = str(uuid.uuid4())
        result = await _bulk_reprocess([*encounter_ids, bad_id])

        assert sorted(result["succeeded"]) == sorted(encounter_ids)
        assert len(result["failed"]) == 1
        assert result["failed"][0]["encounter_id"] == bad_id

        for encounter_id in encounter_ids:
            detail = await client.get(f"/encounters/{encounter_id}", headers=headers)
            assert detail.json()["encounter"]["status"] == "note_generated"
            assert detail.json()["soap_note"]["assessment"] == "a"
