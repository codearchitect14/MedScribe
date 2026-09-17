"""Strict JSON output schemas for each LLM task type.

Every schema is small and flat on purpose: the LLM is used as a text
structuring engine, not a source of medical truth (see plan.md, Design
Principles), so responses are validated immediately and never trusted
free-form.
"""

import enum

from pydantic import BaseModel, Field


class TaskType(str, enum.Enum):
    soap_note = "soap_note"
    care_plan = "care_plan"
    coding_justification = "coding_justification"


class SoapNoteResult(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class CarePlanResult(BaseModel):
    diagnosis_summary: str
    follow_up_actions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    patient_education: list[str] = Field(default_factory=list)
    next_appointment_guidance: str


class CodeJustification(BaseModel):
    code: str
    justification: str
    confidence: float = Field(ge=0.0, le=1.0)


class CodingJustificationResult(BaseModel):
    selected_codes: list[CodeJustification] = Field(default_factory=list)


TASK_SCHEMAS: dict[TaskType, type[BaseModel]] = {
    TaskType.soap_note: SoapNoteResult,
    TaskType.care_plan: CarePlanResult,
    TaskType.coding_justification: CodingJustificationResult,
}

# Per plan Section 5, Phase 3: caps chosen to prevent runaway generations and
# keep free-tier token usage minimal and predictable.
TASK_MAX_OUTPUT_TOKENS: dict[TaskType, int] = {
    TaskType.soap_note: 500,
    TaskType.care_plan: 300,
    TaskType.coding_justification: 200,
}
