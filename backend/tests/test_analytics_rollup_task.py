"""Tests for the Phase 7 nightly analytics rollup Celery task.

Same approach as tests/test_bulk_reprocess.py: the task's inner async
function is awaited directly rather than going through Celery eager mode,
since eager mode's asyncio.run() cannot be called from within an already-
running event loop (which an async test is).
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.analytics_rollup import AnalyticsRollup, RollupType
from app.models.encounter import Encounter, EncounterStatus
from app.models.organization import Organization
from app.models.patient import Patient
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
async def test_rollup_task_covers_every_active_organization():
    from app.tasks.analytics_rollup import _compute_rollups_for_all_organizations

    _require_db()
    suffix = uuid.uuid4().hex[:8]
    with Session(create_engine(settings.sync_database_url)) as session:
        active_org = Organization(name=f"Active Rollup Org {suffix}", is_active=True)
        inactive_org = Organization(name=f"Inactive Rollup Org {suffix}", is_active=False)
        session.add_all([active_org, inactive_org])
        session.flush()

        clinician = User(
            email=f"clinician.{suffix}@example-medscribe.com",
            hashed_password="x",
            full_name="Task Test Clinician",
            role=UserRole.clinician,
            organization_id=active_org.id,
            is_active=True,
        )
        session.add(clinician)
        session.flush()

        patient = Patient(organization_id=active_org.id, first_name="Task", last_name="Patient")
        session.add(patient)
        session.flush()

        encounter = Encounter(
            patient_id=patient.id,
            clinician_id=clinician.id,
            organization_id=active_org.id,
            status=EncounterStatus.transcribed,
            raw_transcript="x",
        )
        session.add(encounter)
        session.commit()
        active_org_id = active_org.id
        inactive_org_id = inactive_org.id

    result = await _compute_rollups_for_all_organizations(date.today())

    assert str(active_org_id) in result["organizations"]
    assert result["organizations"][str(active_org_id)] == "ok"
    # Inactive organizations are skipped entirely, not just given empty rollups.
    assert str(inactive_org_id) not in result["organizations"]

    with Session(create_engine(settings.sync_database_url)) as session:
        rollup = session.execute(
            select(AnalyticsRollup).where(
                AnalyticsRollup.organization_id == active_org_id,
                AnalyticsRollup.rollup_type == RollupType.encounter_volume,
                AnalyticsRollup.period == date.today(),
            )
        ).scalar_one_or_none()
        assert rollup is not None
        total_row = next(r for r in rollup.dimensions if r["clinician_id"] is None)
        assert total_row["count"] == 1


def test_resolve_target_date_defaults_to_yesterday():
    from datetime import UTC, datetime, timedelta

    from app.tasks.analytics_rollup import _resolve_target_date

    expected = (datetime.now(UTC) - timedelta(days=1)).date()
    assert _resolve_target_date(None) == expected


def test_resolve_target_date_uses_explicit_value():
    from app.tasks.analytics_rollup import _resolve_target_date

    assert _resolve_target_date("2026-01-15") == date(2026, 1, 15)
