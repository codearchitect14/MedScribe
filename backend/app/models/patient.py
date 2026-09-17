import uuid
from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.encryption import EncryptedDate, EncryptedString
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    external_reference: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    first_name: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    last_name: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    sex: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="patients")
