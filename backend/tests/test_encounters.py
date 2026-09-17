"""End-to-end tests for the Phase 4 clinical pipeline: transcript ingestion,
SOAP note generation/review/finalize, care plan generation, and pgvector-
backed code suggestion generation with accept/reject.

Requires postgres and redis (see README.md). The LLM provider adapters are
monkeypatched (same approach as tests/test_llm_gateway.py) so no real
Groq/Gemini keys are needed; everything else (Redis quota/cache, Postgres,
pgvector similarity search) is real.
"""

import json
import re
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

SOAP_JSON = json.dumps(
    {
        "subjective": "Patient reports elevated home glucose readings over the past month.",
        "objective": "Vital signs stable. No acute distress.",
        "assessment": "Type 2 diabetes mellitus with hyperglycemia.",
        "plan": "Increase metformin dose, recheck A1C in three months.",
    }
)

CARE_PLAN_JSON = json.dumps(
    {
        "diagnosis_summary": "Type 2 diabetes mellitus, suboptimal control.",
        "follow_up_actions": ["Recheck A1C in 3 months"],
        "medications": ["Metformin dose increase (clinician to confirm)"],
        "patient_education": ["Diet and exercise counseling"],
        "next_appointment_guidance": "Return in 3 months",
    }
)


class ScriptedAdapter:
    """Returns a canned response keyed off the max_tokens cap for each task
    type (500=soap_note, 300=care_plan, 200=coding_justification), so it
    can stand in for whichever provider the gateway selects."""

    name = "groq"

    def __init__(self):
        self.calls: list[dict] = []

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        self.calls.append({"user_prompt": user_prompt, "max_tokens": max_tokens})
        if max_tokens == 500:
            content = SOAP_JSON
        elif max_tokens == 300:
            content = CARE_PLAN_JSON
        elif max_tokens == 200:
            match = re.search(r"-\s*(\S+):", user_prompt)
            code = match.group(1) if match else "NOT-A-REAL-CODE"
            content = json.dumps(
                {
                    "selected_codes": [
                        {"code": code, "justification": "matches assessment", "confidence": 0.9},
                        {"code": "NOT-A-REAL-CODE", "justification": "hallucinated", "confidence": 0.5},
                    ]
                }
            )
        else:
            raise AssertionError(f"unexpected max_tokens {max_tokens}")
        return ProviderResponse(content=content, tokens_input=100, tokens_output=50, model="mock-model")


def _require_db():
    engine = create_engine(settings.sync_database_url)
    try:
        conn = engine.connect()
        conn.close()
    except OperationalError:
        pytest.skip("database not reachable; start docker compose postgres service first")


@pytest.fixture
def scripted_adapter(monkeypatch):
    adapter = ScriptedAdapter()
    monkeypatch.setitem(gateway.ADAPTERS, "groq", adapter)
    monkeypatch.setitem(gateway.ADAPTERS, "gemini", adapter)
    return adapter


@pytest.fixture
def org_and_users():
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Encounter Test Org {suffix}")
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

    return {"org_id": org_id, "users": users}


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio(loop_scope="session")
async def test_full_pipeline_happy_path(org_and_users, scripted_adapter):
    users = org_and_users["users"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        coder_token = await _login(client, users["coder"]["email"], users["coder"]["password"])
        clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
        coder_headers = {"Authorization": f"Bearer {coder_token}"}

        patient = await client.post(
            "/patients",
            json={"first_name": "Jane", "last_name": "Doe", "sex": "female"},
            headers=clinician_headers,
        )
        assert patient.status_code == 201, patient.text
        patient_id = patient.json()["id"]

        raw_transcript = (
            "Doctor: How have your blood sugars been, um, running lately?\n"
            "Patient: You know, they have been high, like 180 in the mornings.\n"
        )
        encounter = await client.post(
            "/encounters",
            json={"patient_id": patient_id, "raw_transcript": raw_transcript},
            headers=clinician_headers,
        )
        assert encounter.status_code == 201, encounter.text
        encounter_body = encounter.json()
        encounter_id = encounter_body["id"]
        assert encounter_body["status"] == "transcribed"
        # Transcript cleaning: speaker labels normalized, filler words stripped.
        cleaned = encounter_body["raw_transcript"]
        assert cleaned.startswith("Doctor: How have your blood sugars been")
        assert "um" not in {w.strip(",.").lower() for w in cleaned.split()}
        assert "you" in cleaned.lower()  # "You know," retains "You"; only the filler phrase itself is dropped

        # Generating codes before a SOAP note exists is rejected by the workflow guard.
        premature_codes = await client.post(f"/encounters/{encounter_id}/codes", headers=clinician_headers)
        assert premature_codes.status_code == 409

        soap = await client.post(f"/encounters/{encounter_id}/soap-note", headers=clinician_headers)
        assert soap.status_code == 201, soap.text
        assert soap.json()["assessment"] == "Type 2 diabetes mellitus with hyperglycemia."
        assert soap.json()["status"] == "draft"

        detail = await client.get(f"/encounters/{encounter_id}", headers=clinician_headers)
        assert detail.json()["encounter"]["status"] == "note_generated"

        edited = await client.patch(
            f"/encounters/{encounter_id}/soap-note",
            json={"assessment": "Type 2 diabetes mellitus, edited by clinician."},
            headers=clinician_headers,
        )
        assert edited.status_code == 200
        assert edited.json()["assessment"] == "Type 2 diabetes mellitus, edited by clinician."

        # Finalizing before review is rejected.
        premature_finalize = await client.post(
            f"/encounters/{encounter_id}/soap-note/finalize", headers=clinician_headers
        )
        assert premature_finalize.status_code == 409

        reviewed = await client.post(f"/encounters/{encounter_id}/soap-note/review", headers=clinician_headers)
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "reviewed"

        finalized = await client.post(f"/encounters/{encounter_id}/soap-note/finalize", headers=clinician_headers)
        assert finalized.status_code == 200
        assert finalized.json()["status"] == "finalized"

        # A finalized note can no longer be edited.
        locked_edit = await client.patch(
            f"/encounters/{encounter_id}/soap-note",
            json={"assessment": "should not be allowed"},
            headers=clinician_headers,
        )
        assert locked_edit.status_code == 409

        care_plan = await client.post(f"/encounters/{encounter_id}/care-plan", headers=clinician_headers)
        assert care_plan.status_code == 201, care_plan.text
        care_plan_content = json.loads(care_plan.json()["content"])
        assert care_plan_content["diagnosis_summary"] == "Type 2 diabetes mellitus, suboptimal control."

        # Coding is a clinician-accessible generation step, but only coder/admin decide accept/reject.
        codes = await client.post(f"/encounters/{encounter_id}/codes", headers=clinician_headers)
        assert codes.status_code == 201, codes.text
        code_list = codes.json()
        # The hallucinated "NOT-A-REAL-CODE" must be discarded; only the real
        # pgvector-retrieved candidate is persisted.
        assert all(c["code"] != "NOT-A-REAL-CODE" for c in code_list)
        assert len(code_list) == 1
        suggestion_id = code_list[0]["id"]
        assert code_list[0]["code_type"] in ("icd10", "hcpcs")

        final_detail = await client.get(f"/encounters/{encounter_id}", headers=clinician_headers)
        assert final_detail.json()["encounter"]["status"] == "coded"

        clinician_decide = await client.patch(
            f"/encounters/{encounter_id}/codes/{suggestion_id}",
            json={"accepted": True},
            headers=clinician_headers,
        )
        assert clinician_decide.status_code == 403

        coder_decide = await client.patch(
            f"/encounters/{encounter_id}/codes/{suggestion_id}",
            json={"accepted": True},
            headers=coder_headers,
        )
        assert coder_decide.status_code == 200
        assert coder_decide.json()["accepted"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_encounter_org_isolation(org_and_users, scripted_adapter):
    users = org_and_users["users"]
    suffix = uuid.uuid4().hex[:8]

    with Session(create_engine(settings.sync_database_url)) as session:
        other_org = Organization(name=f"Other Encounter Org {suffix}")
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
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

        patient = await client.post(
            "/patients",
            json={"first_name": "Ann", "last_name": "Owner"},
            headers=clinician_headers,
        )
        patient_id = patient.json()["id"]
        encounter = await client.post(
            "/encounters",
            json={"patient_id": patient_id, "raw_transcript": "Doctor: hello. Patient: hi."},
            headers=clinician_headers,
        )
        encounter_id = encounter.json()["id"]

        other_token = await _login(client, other_admin_email, "OtherPass123!")
        other_headers = {"Authorization": f"Bearer {other_token}"}

        cross_org = await client.get(f"/encounters/{encounter_id}", headers=other_headers)
        assert cross_org.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_clinician_cannot_see_another_clinicians_encounter(org_and_users, scripted_adapter):
    users = org_and_users["users"]
    suffix = uuid.uuid4().hex[:8]

    with Session(create_engine(settings.sync_database_url)) as session:
        other_clinician_email = f"other-clinician.{suffix}@example-medscribe.com"
        other_clinician = User(
            email=other_clinician_email,
            hashed_password=hash_password("OtherPass123!"),
            full_name="Other Clinician",
            role=UserRole.clinician,
            organization_id=org_and_users["org_id"],
            is_active=True,
        )
        session.add(other_clinician)
        session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

        patient = await client.post(
            "/patients",
            json={"first_name": "Sam", "last_name": "Private"},
            headers=clinician_headers,
        )
        patient_id = patient.json()["id"]
        encounter = await client.post(
            "/encounters",
            json={"patient_id": patient_id, "raw_transcript": "Doctor: hello. Patient: hi."},
            headers=clinician_headers,
        )
        encounter_id = encounter.json()["id"]

        other_token = await _login(client, other_clinician_email, "OtherPass123!")
        other_headers = {"Authorization": f"Bearer {other_token}"}

        same_org_other_clinician = await client.get(f"/encounters/{encounter_id}", headers=other_headers)
        assert same_org_other_clinician.status_code == 404
