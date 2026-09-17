import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EncounterStatus(str, enum.Enum):
    recording = "recording"
    transcribed = "transcribed"
    note_generated = "note_generated"
    under_review = "under_review"
    finalized = "finalized"
    coded = "coded"
    billed = "billed"


class Encounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounters"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    clinician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus, name="encounter_status"),
        nullable=False,
        default=EncounterStatus.transcribed,
    )
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    soap_notes: Mapped[list["SoapNote"]] = relationship(back_populates="encounter")
    care_plans: Mapped[list["CarePlan"]] = relationship(back_populates="encounter")
    code_suggestions: Mapped[list["CodeSuggestion"]] = relationship(back_populates="encounter")
