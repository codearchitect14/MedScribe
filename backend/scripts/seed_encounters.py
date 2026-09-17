"""Seed the database with a demo organization, users, patients, and encounters.

Loads the synthetic sample dialogues in data/seed/sample_encounters.json
(built in the internal encounter schema, informed by the structure of public
datasets such as MTS-Dialog and ACI-BENCH) so local development and demos
never require real patient data.

Uses the ORM models (rather than raw SQL) so that encrypted patient fields
(see app/core/encryption.py) are written through their SQLAlchemy type
decorators instead of landing in the database unencrypted.

Usage:
    python -m scripts.seed_encounters
"""

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.encounter import Encounter, EncounterStatus
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.soap_note import SoapNote
from app.models.user import User, UserRole

SAMPLE_FILE = Path("data/seed/sample_encounters.json")

DEMO_ORG_NAME = "MedScribe Demo Clinic"
DEMO_CLINICIAN_EMAIL = "demo.clinician@medscribe-demo.com"
DEMO_CLINICIAN_PASSWORD = "DemoPass123!"


def seed(session: Session) -> None:
    org = Organization(name=DEMO_ORG_NAME, is_active=True)
    session.add(org)
    session.flush()

    clinician = User(
        email=DEMO_CLINICIAN_EMAIL,
        hashed_password=hash_password(DEMO_CLINICIAN_PASSWORD),
        full_name="Dr. Demo Clinician",
        role=UserRole.clinician,
        organization_id=org.id,
        is_active=True,
    )
    session.add(clinician)
    session.flush()

    records = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))

    for index, record in enumerate(records):
        patient = Patient(
            organization_id=org.id,
            external_reference=f"SEED-{index:04d}",
            first_name=record["patient_first_name"],
            last_name=record["patient_last_name"],
            date_of_birth=date.fromisoformat(record["date_of_birth"]),
            sex=record["sex"],
        )
        session.add(patient)
        session.flush()

        encounter = Encounter(
            patient_id=patient.id,
            clinician_id=clinician.id,
            organization_id=org.id,
            status=EncounterStatus.note_generated,
            raw_transcript=record["raw_transcript"],
        )
        session.add(encounter)
        session.flush()

        soap = record["soap_note"]
        session.add(
            SoapNote(
                encounter_id=encounter.id,
                subjective=soap["subjective"],
                objective=soap["objective"],
                assessment=soap["assessment"],
                plan=soap["plan"],
                model_used="seed-data",
                tokens_used=0,
            )
        )

    session.commit()
    print(f"Seeded organization '{DEMO_ORG_NAME}' with {len(records)} demo encounters.")
    print(f"Demo clinician login: {DEMO_CLINICIAN_EMAIL} / {DEMO_CLINICIAN_PASSWORD}")


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.sync_database_url)
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
