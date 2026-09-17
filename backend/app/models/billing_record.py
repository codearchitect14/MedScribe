import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BillingStatus(str, enum.Enum):
    pending = "pending"
    submitted = "submitted"
    paid = "paid"
    denied = "denied"


class BillingRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_records"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False, index=True
    )
    codes_applied: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    estimated_reimbursement: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    billed_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    payer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[BillingStatus] = mapped_column(
        Enum(BillingStatus, name="billing_status"),
        nullable=False,
        default=BillingStatus.pending,
    )

    encounter: Mapped["Encounter"] = relationship()
