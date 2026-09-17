import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.billing_record import BillingStatus


class CreateBillingRecordRequest(BaseModel):
    codes_applied: list[str] = Field(default_factory=list, max_length=100)
    estimated_reimbursement: float | None = Field(default=None, ge=0)
    payer: str | None = Field(default=None, max_length=255)


class UpdateBillingRecordRequest(BaseModel):
    billed_amount: float | None = Field(default=None, ge=0)
    payer: str | None = Field(default=None, max_length=255)
    status: BillingStatus | None = None


class BillingRecordOut(BaseModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    codes_applied: list[str]
    estimated_reimbursement: float | None
    billed_amount: float | None
    payer: str | None
    status: BillingStatus
    created_at: datetime

    model_config = {"from_attributes": True}
