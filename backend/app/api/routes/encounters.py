import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis_client, require_roles
from app.core.db import get_db
from app.core.query import paginate
from app.llm.gateway import GenerationContext
from app.models.billing_record import BillingRecord
from app.models.care_plan import CarePlan
from app.models.code_suggestion import CodeSuggestion
from app.models.encounter import Encounter, EncounterStatus
from app.models.patient import Patient
from app.models.soap_note import SoapNote, SoapNoteStatus
from app.models.user import User, UserRole
from app.schemas.billing import BillingRecordOut, CreateBillingRecordRequest, UpdateBillingRecordRequest
from app.schemas.encounter import (
    CarePlanOut,
    CodeSuggestionDecisionRequest,
    CodeSuggestionOut,
    CreateEncounterRequest,
    CreateLiveEncounterRequest,
    EncounterDetailOut,
    EncounterOut,
    SoapNoteOut,
    UpdateCarePlanRequest,
    UpdateSoapNoteRequest,
)
from app.schemas.pagination import Page, PageParams, pagination_params
from app.schemas.tasks import BulkReprocessRequest, TaskSubmittedResponse
from app.services.clinical import workflow
from app.services.clinical.care_plan_service import generate_care_plan
from app.services.clinical.coding_service import generate_code_suggestions
from app.services.clinical.soap_note_service import generate_soap_note
from app.services.clinical.transcript_cleaning import clean_transcript
from app.services.clinical.transcription import transcribe_audio_file
from app.tasks.bulk_reprocess import bulk_reprocess_encounters_task

router = APIRouter(prefix="/encounters", tags=["encounters"])

CAN_CREATE_ENCOUNTERS = (UserRole.clinician, UserRole.admin, UserRole.super_admin)
CAN_DECIDE_CODES = (UserRole.coder, UserRole.admin, UserRole.super_admin)


async def _get_authorized_encounter(
    encounter_id: uuid.UUID, current_user: User, session: AsyncSession
) -> Encounter:
    encounter = await session.get(Encounter, encounter_id)
    if encounter is None or encounter.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    if current_user.role == UserRole.clinician and encounter.clinician_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return encounter


async def _get_latest_soap_note(session: AsyncSession, encounter_id: uuid.UUID) -> SoapNote | None:
    result = await session.execute(
        select(SoapNote).where(SoapNote.encounter_id == encounter_id).order_by(SoapNote.generated_at.desc())
    )
    return result.scalars().first()


async def _get_latest_care_plan(session: AsyncSession, encounter_id: uuid.UUID) -> CarePlan | None:
    result = await session.execute(
        select(CarePlan).where(CarePlan.encounter_id == encounter_id).order_by(CarePlan.generated_at.desc())
    )
    return result.scalars().first()


async def _get_latest_billing_record(session: AsyncSession, encounter_id: uuid.UUID) -> BillingRecord | None:
    result = await session.execute(
        select(BillingRecord)
        .where(BillingRecord.encounter_id == encounter_id)
        .order_by(BillingRecord.created_at.desc())
    )
    return result.scalars().first()


async def _require_patient_in_org(session: AsyncSession, patient_id: uuid.UUID, org_id: uuid.UUID) -> None:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")


@router.post("", response_model=EncounterOut, status_code=status.HTTP_201_CREATED)
async def create_encounter(
    payload: CreateEncounterRequest,
    current_user: User = Depends(require_roles(*CAN_CREATE_ENCOUNTERS)),
    session: AsyncSession = Depends(get_db),
) -> Encounter:
    await _require_patient_in_org(session, payload.patient_id, current_user.organization_id)

    encounter = Encounter(
        patient_id=payload.patient_id,
        clinician_id=current_user.id,
        organization_id=current_user.organization_id,
        status=EncounterStatus.transcribed,
        raw_transcript=clean_transcript(payload.raw_transcript),
    )
    session.add(encounter)
    await session.commit()
    await session.refresh(encounter)
    return encounter


@router.post("/audio", response_model=EncounterOut, status_code=status.HTTP_201_CREATED)
async def create_encounter_from_audio(
    patient_id: uuid.UUID = Form(...),
    audio: UploadFile = File(...),
    current_user: User = Depends(require_roles(*CAN_CREATE_ENCOUNTERS)),
    session: AsyncSession = Depends(get_db),
) -> Encounter:
    await _require_patient_in_org(session, patient_id, current_user.organization_id)

    suffix = Path(audio.filename or "audio").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        raw_text = transcribe_audio_file(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    encounter = Encounter(
        patient_id=patient_id,
        clinician_id=current_user.id,
        organization_id=current_user.organization_id,
        status=EncounterStatus.transcribed,
        raw_transcript=clean_transcript(raw_text),
        audio_reference=audio.filename,
    )
    session.add(encounter)
    await session.commit()
    await session.refresh(encounter)
    return encounter


@router.post("/live", response_model=EncounterOut, status_code=status.HTTP_201_CREATED)
async def create_live_encounter(
    payload: CreateLiveEncounterRequest,
    current_user: User = Depends(require_roles(*CAN_CREATE_ENCOUNTERS)),
    session: AsyncSession = Depends(get_db),
) -> Encounter:
    """Creates the encounter a live recording will attach to. The client
    then opens a WebSocket to /ws/encounters/{id}/live-transcribe using the
    returned id (see docs/live-transcription.md)."""
    await _require_patient_in_org(session, payload.patient_id, current_user.organization_id)

    encounter = Encounter(
        patient_id=payload.patient_id,
        clinician_id=current_user.id,
        organization_id=current_user.organization_id,
        status=EncounterStatus.recording,
        raw_transcript=None,
    )
    session.add(encounter)
    await session.commit()
    await session.refresh(encounter)
    return encounter


@router.get("/{encounter_id}", response_model=EncounterDetailOut)
async def get_encounter(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EncounterDetailOut:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    soap_note = await _get_latest_soap_note(session, encounter_id)
    care_plan = await _get_latest_care_plan(session, encounter_id)
    billing_record = await _get_latest_billing_record(session, encounter_id)
    codes_result = await session.execute(
        select(CodeSuggestion).where(CodeSuggestion.encounter_id == encounter_id)
    )
    return EncounterDetailOut(
        encounter=EncounterOut.model_validate(encounter),
        soap_note=SoapNoteOut.model_validate(soap_note) if soap_note else None,
        care_plan=CarePlanOut.model_validate(care_plan) if care_plan else None,
        billing_record=BillingRecordOut.model_validate(billing_record) if billing_record else None,
        code_suggestions=[CodeSuggestionOut.model_validate(c) for c in codes_result.scalars().all()],
    )


EncounterSort = Literal["created_at", "-created_at"]


@router.get("", response_model=Page[EncounterOut])
async def list_encounters(
    status_filter: EncounterStatus | None = Query(default=None, alias="status"),
    patient_id: uuid.UUID | None = Query(default=None),
    sort: EncounterSort = Query(default="-created_at"),
    page_params: PageParams = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Page[EncounterOut]:
    stmt = select(Encounter).where(Encounter.organization_id == current_user.organization_id)
    if current_user.role == UserRole.clinician:
        stmt = stmt.where(Encounter.clinician_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(Encounter.status == status_filter)
    if patient_id is not None:
        stmt = stmt.where(Encounter.patient_id == patient_id)

    stmt = stmt.order_by(Encounter.created_at.asc() if sort == "created_at" else Encounter.created_at.desc())

    items, total = await paginate(session, stmt, page_params)
    return Page[EncounterOut](
        items=[EncounterOut.model_validate(e) for e in items],
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )


@router.post("/{encounter_id}/soap-note", response_model=SoapNoteOut, status_code=status.HTTP_201_CREATED)
async def create_soap_note(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> SoapNote:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_soap_generation_allowed(encounter)

    context = GenerationContext(session=session, redis=redis, encounter_id=encounter.id)
    return await generate_soap_note(encounter, context)


@router.patch("/{encounter_id}/soap-note", response_model=SoapNoteOut)
async def update_soap_note(
    encounter_id: uuid.UUID,
    payload: UpdateSoapNoteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SoapNote:
    await _get_authorized_encounter(encounter_id, current_user, session)
    soap_note = await _get_latest_soap_note(session, encounter_id)
    if soap_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOAP note has been generated yet")
    if soap_note.status == SoapNoteStatus.finalized:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot edit a finalized SOAP note")

    for field in ("subjective", "objective", "assessment", "plan"):
        value = getattr(payload, field)
        if value is not None:
            setattr(soap_note, field, value)

    await session.commit()
    await session.refresh(soap_note)
    return soap_note


@router.post("/{encounter_id}/soap-note/review", response_model=SoapNoteOut)
async def review_soap_note(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SoapNote:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_review_allowed(encounter)

    soap_note = await _get_latest_soap_note(session, encounter_id)
    if soap_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOAP note has been generated yet")

    encounter.status = EncounterStatus.under_review
    soap_note.status = SoapNoteStatus.reviewed
    await session.commit()
    await session.refresh(soap_note)
    return soap_note


@router.post("/{encounter_id}/soap-note/finalize", response_model=SoapNoteOut)
async def finalize_soap_note(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SoapNote:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_finalize_allowed(encounter)

    soap_note = await _get_latest_soap_note(session, encounter_id)
    if soap_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOAP note has been generated yet")

    encounter.status = EncounterStatus.finalized
    soap_note.status = SoapNoteStatus.finalized
    soap_note.reviewed_by = current_user.id
    soap_note.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(soap_note)
    return soap_note


@router.post("/{encounter_id}/care-plan", response_model=CarePlanOut, status_code=status.HTTP_201_CREATED)
async def create_care_plan(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> CarePlan:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_care_plan_generation_allowed(encounter)

    soap_note = await _get_latest_soap_note(session, encounter_id)
    if soap_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOAP note has been generated yet")

    context = GenerationContext(session=session, redis=redis, encounter_id=encounter.id)
    return await generate_care_plan(soap_note, context)


@router.patch("/{encounter_id}/care-plan", response_model=CarePlanOut)
async def update_care_plan(
    encounter_id: uuid.UUID,
    payload: UpdateCarePlanRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CarePlan:
    await _get_authorized_encounter(encounter_id, current_user, session)
    care_plan = await _get_latest_care_plan(session, encounter_id)
    if care_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No care plan has been generated yet")

    care_plan.content = payload.content
    await session.commit()
    await session.refresh(care_plan)
    return care_plan


@router.post("/{encounter_id}/codes", response_model=list[CodeSuggestionOut], status_code=status.HTTP_201_CREATED)
async def create_code_suggestions(
    encounter_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_client),
) -> list[CodeSuggestion]:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_code_generation_allowed(encounter)

    soap_note = await _get_latest_soap_note(session, encounter_id)
    if soap_note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOAP note has been generated yet")

    context = GenerationContext(session=session, redis=redis, encounter_id=encounter.id)
    return await generate_code_suggestions(encounter, soap_note, context)


@router.patch("/{encounter_id}/codes/{suggestion_id}", response_model=CodeSuggestionOut)
async def decide_code_suggestion(
    encounter_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    payload: CodeSuggestionDecisionRequest,
    current_user: User = Depends(require_roles(*CAN_DECIDE_CODES)),
    session: AsyncSession = Depends(get_db),
) -> CodeSuggestion:
    encounter = await session.get(Encounter, encounter_id)
    if encounter is None or encounter.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    workflow.require_code_decision_allowed(encounter)

    suggestion = await session.get(CodeSuggestion, suggestion_id)
    if suggestion is None or suggestion.encounter_id != encounter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code suggestion not found")

    suggestion.accepted = payload.accepted
    await session.commit()
    await session.refresh(suggestion)
    return suggestion


@router.post(
    "/{encounter_id}/billing-record", response_model=BillingRecordOut, status_code=status.HTTP_201_CREATED
)
async def create_billing_record(
    encounter_id: uuid.UUID,
    payload: CreateBillingRecordRequest,
    current_user: User = Depends(require_roles(*CAN_DECIDE_CODES)),
    session: AsyncSession = Depends(get_db),
) -> BillingRecord:
    encounter = await _get_authorized_encounter(encounter_id, current_user, session)
    workflow.require_billing_record_creation_allowed(encounter)

    record = BillingRecord(
        encounter_id=encounter.id,
        codes_applied=payload.codes_applied,
        estimated_reimbursement=payload.estimated_reimbursement,
        payer=payload.payer,
    )
    session.add(record)

    encounter.status = EncounterStatus.billed
    session.add(encounter)

    await session.commit()
    await session.refresh(record)
    return record


@router.patch("/{encounter_id}/billing-record/{record_id}", response_model=BillingRecordOut)
async def update_billing_record(
    encounter_id: uuid.UUID,
    record_id: uuid.UUID,
    payload: UpdateBillingRecordRequest,
    current_user: User = Depends(require_roles(*CAN_DECIDE_CODES)),
    session: AsyncSession = Depends(get_db),
) -> BillingRecord:
    await _get_authorized_encounter(encounter_id, current_user, session)

    record = await session.get(BillingRecord, record_id)
    if record is None or record.encounter_id != encounter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing record not found")

    if payload.billed_amount is not None:
        record.billed_amount = payload.billed_amount
    if payload.payer is not None:
        record.payer = payload.payer
    if payload.status is not None:
        record.status = payload.status

    await session.commit()
    await session.refresh(record)
    return record


@router.post("/bulk-reprocess", response_model=TaskSubmittedResponse, status_code=status.HTTP_202_ACCEPTED)
async def bulk_reprocess_encounters(
    payload: BulkReprocessRequest,
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.super_admin)),
    session: AsyncSession = Depends(get_db),
) -> TaskSubmittedResponse:
    """Regenerates SOAP notes for a batch of historical encounters in the
    background (Celery), rather than inline, since a batch of LLM calls can
    easily exceed a normal HTTP request timeout."""
    owned = await session.execute(
        select(Encounter.id).where(
            Encounter.id.in_(payload.encounter_ids),
            Encounter.organization_id == current_user.organization_id,
        )
    )
    owned_ids = {row[0] for row in owned.all()}
    unauthorized = [str(eid) for eid in payload.encounter_ids if eid not in owned_ids]
    if unauthorized:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Encounter(s) not found in your organization: {', '.join(unauthorized)}",
        )

    task = bulk_reprocess_encounters_task.delay([str(eid) for eid in payload.encounter_ids])
    return TaskSubmittedResponse(task_id=task.id)
