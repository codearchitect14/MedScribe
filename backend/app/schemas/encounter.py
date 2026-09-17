import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.code_suggestion import CodeType
from app.models.encounter import EncounterStatus
from app.models.soap_note import SoapNoteStatus
from app.schemas.billing import BillingRecordOut

# Generous but bounded: rejects obviously-oversized payloads early rather
# than accepting arbitrary request bodies (plan.md Phase 6 hardening).
MAX_TRANSCRIPT_LENGTH = 50_000
MAX_NOTE_FIELD_LENGTH = 5_000
MAX_CARE_PLAN_LENGTH = 20_000


class CreateEncounterRequest(BaseModel):
    patient_id: uuid.UUID
    raw_transcript: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_LENGTH)


class CreateLiveEncounterRequest(BaseModel):
    patient_id: uuid.UUID


class EncounterOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    clinician_id: uuid.UUID
    organization_id: uuid.UUID
    status: EncounterStatus
    raw_transcript: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SoapNoteOut(BaseModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    subjective: str | None
    objective: str | None
    assessment: str | None
    plan: str | None
    model_used: str | None
    tokens_used: int | None
    status: SoapNoteStatus
    generated_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class UpdateSoapNoteRequest(BaseModel):
    subjective: str | None = Field(default=None, max_length=MAX_NOTE_FIELD_LENGTH)
    objective: str | None = Field(default=None, max_length=MAX_NOTE_FIELD_LENGTH)
    assessment: str | None = Field(default=None, max_length=MAX_NOTE_FIELD_LENGTH)
    plan: str | None = Field(default=None, max_length=MAX_NOTE_FIELD_LENGTH)


class CarePlanOut(BaseModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    content: str | None
    generated_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class UpdateCarePlanRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CARE_PLAN_LENGTH)


class CodeSuggestionOut(BaseModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    code_type: CodeType
    code: str
    description: str
    confidence_score: float | None
    accepted: bool | None

    model_config = {"from_attributes": True}


class CodeSuggestionDecisionRequest(BaseModel):
    accepted: bool


class EncounterDetailOut(BaseModel):
    encounter: EncounterOut
    soap_note: SoapNoteOut | None
    care_plan: CarePlanOut | None
    code_suggestions: list[CodeSuggestionOut]
    billing_record: BillingRecordOut | None
