import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.code_suggestion import CodeType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReimbursementRate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A configurable rate table mapping a code to a typical reimbursement
    value, per organization (plan.md Phase 7). Used only to produce an
    *estimated* revenue figure; never a substitute for a real billing
    integration or an actual paid amount. At most one row per
    (organization_id, code_type, code), enforced by a unique index
    (migration 0003); an admin re-sets a rate via upsert.
    """

    __tablename__ = "reimbursement_rates"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    code_type: Mapped[CodeType] = mapped_column(Enum(CodeType, name="code_type"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
