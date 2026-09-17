import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RollupType(str, enum.Enum):
    encounter_volume = "encounter_volume"
    coding_mix = "coding_mix"
    estimated_reimbursement = "estimated_reimbursement"
    turnaround_time = "turnaround_time"
    llm_usage = "llm_usage"
    clinician_productivity = "clinician_productivity"


class AnalyticsRollup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One pre-aggregated row for one (organization, rollup_type, period).

    A single flexible table rather than one table per metric: every rollup
    type is small, read-mostly, and shares the same lifecycle (computed by
    app/tasks/analytics_rollup.py, read by app/api/routes/analytics.py, and
    re-computed idempotently via upsert on the unique
    (organization_id, rollup_type, period) index from migration 0003).
    `dimensions` holds the JSON-serializable list of per-group rows the
    metric actually produced (see app/services/analytics/rollup_service.py
    for the exact shape per rollup type); `created_at` (from
    TimestampMixin) doubles as "computed_at".
    """

    __tablename__ = "analytics_rollups"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    rollup_type: Mapped[RollupType] = mapped_column(
        Enum(RollupType, name="rollup_type"), nullable=False, index=True
    )
    period: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dimensions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
