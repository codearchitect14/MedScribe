import enum
import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CodeType(str, enum.Enum):
    icd10 = "icd10"
    hcpcs = "hcpcs"


class CodeSuggestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "code_suggestions"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False, index=True
    )
    code_type: Mapped[CodeType] = mapped_column(Enum(CodeType, name="code_type"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    encounter: Mapped["Encounter"] = relationship(back_populates="code_suggestions")
