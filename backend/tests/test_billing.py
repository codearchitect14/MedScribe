"""Tests for the Phase 6 billing-record endpoints and the coded -> billed
workflow transition."""

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
        "subjective": "Patient reports elevated glucose readings.",
        "objective": "Vital signs stable.",
        "assessment": "Type 2 diabetes mellitus with hyperglycemia.",
        "plan": "Increase metformin dose.",
    }
)


class ScriptedAdapter:
    name = "groq"

    async def complete(self, *, system_prompt, user_prompt, max_tokens, json_mode=True):
        if max_tokens == 500:
            content = SOAP_JSON
        elif max_tokens == 200:
            match = re.search(r"-\s*(\S+):", user_prompt)
            code = match.group(1) if match else "E11.9"
            content = json.dumps(
                {"selected_codes": [{"code": code, "justification": "matches", "confidence": 0.9}]}
            )
        else:
            content = json.dumps({"diagnosis_summary": "n/a", "next_appointment_guidance": "n/a"})
        return ProviderResponse(content=content, tokens_input=50, tokens_output=25, model="mock-model")


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
def clinician_and_coder():
    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        org = Organization(name=f"Billing Test Org {suffix}")
        session.add(org)
        session.flush()

        users = {}
        for role in (UserRole.clinician, UserRole.coder):
            email = f"{role.value}.{suffix}@example-medscribe.com"
            user = User(
                email=email,
                hashed_password=hash_password("TestPass123!"),
                full_name=f"Test {role.value}",
                role=role,
                organization_id=org.id,
                is_active=True,
            )
            session.add(user)
            users[role.value] = {"email": email, "password": "TestPass123!"}

        session.commit()

    return users


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _drive_encounter_to_coded(client: AsyncClient, headers: dict) -> str:
    patient = await client.post(
        "/patients", json={"first_name": "Bill", "last_name": "Test"}, headers=headers
    )
    patient_id = patient.json()["id"]

    encounter = await client.post(
        "/encounters",
        json={"patient_id": patient_id, "raw_transcript": "Doctor: hi. Patient: my sugar is high."},
        headers=headers,
    )
    encounter_id = encounter.json()["id"]

    await client.post(f"/encounters/{encounter_id}/soap-note", headers=headers)
    await client.post(f"/encounters/{encounter_id}/soap-note/review", headers=headers)
    await client.post(f"/encounters/{encounter_id}/soap-note/finalize", headers=headers)
    await client.post(f"/encounters/{encounter_id}/codes", headers=headers)
    return encounter_id


@pytest.mark.asyncio(loop_scope="session")
async def test_billing_record_lifecycle(clinician_and_coder, scripted_adapter):
    users = clinician_and_coder
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        coder_token = await _login(client, users["coder"]["email"], users["coder"]["password"])
        clinician_headers = {"Authorization": f"Bearer {clinician_token}"}
        coder_headers = {"Authorization": f"Bearer {coder_token}"}

        encounter_id = await _drive_encounter_to_coded(client, clinician_headers)

        # Clinicians cannot create billing records.
        forbidden = await client.post(
            f"/encounters/{encounter_id}/billing-record",
            json={"codes_applied": ["E11.9"], "estimated_reimbursement": 120.5},
            headers=clinician_headers,
        )
        assert forbidden.status_code == 403

        created = await client.post(
            f"/encounters/{encounter_id}/billing-record",
            json={"codes_applied": ["E11.9"], "estimated_reimbursement": 120.5, "payer": "Acme Insurance"},
            headers=coder_headers,
        )
        assert created.status_code == 201, created.text
        record = created.json()
        assert record["status"] == "pending"
        assert record["codes_applied"] == ["E11.9"]

        # Encounter transitions coded -> billed.
        detail = await client.get(f"/encounters/{encounter_id}", headers=coder_headers)
        assert detail.json()["encounter"]["status"] == "billed"
        assert detail.json()["billing_record"]["id"] == record["id"]

        # A second billing-record creation is rejected (already billed, not coded).
        second = await client.post(
            f"/encounters/{encounter_id}/billing-record",
            json={"codes_applied": ["E11.9"]},
            headers=coder_headers,
        )
        assert second.status_code == 409

        updated = await client.patch(
            f"/encounters/{encounter_id}/billing-record/{record['id']}",
            json={"status": "submitted", "billed_amount": 100.0},
            headers=coder_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "submitted"
        assert updated.json()["billed_amount"] == 100.0


@pytest.mark.asyncio(loop_scope="session")
async def test_billing_record_creation_requires_coded_status(clinician_and_coder, scripted_adapter):
    users = clinician_and_coder
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        coder_token = await _login(client, users["coder"]["email"], users["coder"]["password"])
        clinician_token = await _login(client, users["clinician"]["email"], users["clinician"]["password"])
        coder_headers = {"Authorization": f"Bearer {coder_token}"}
        clinician_headers = {"Authorization": f"Bearer {clinician_token}"}

        patient = await client.post(
            "/patients", json={"first_name": "Early", "last_name": "Bill"}, headers=clinician_headers
        )
        patient_id = patient.json()["id"]
        encounter = await client.post(
            "/encounters",
            json={"patient_id": patient_id, "raw_transcript": "Doctor: hi. Patient: hi."},
            headers=clinician_headers,
        )
        encounter_id = encounter.json()["id"]

        too_early = await client.post(
            f"/encounters/{encounter_id}/billing-record",
            json={"codes_applied": []},
            headers=coder_headers,
        )
        assert too_early.status_code == 409
