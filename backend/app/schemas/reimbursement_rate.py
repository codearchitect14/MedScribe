import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.code_suggestion import CodeType


class UpsertReimbursementRateRequest(BaseModel):
    code_type: CodeType
    code: str = Field(min_length=1, max_length=20)
    rate: float = Field(ge=0)


class ReimbursementRateOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    code_type: CodeType
    code: str
    rate: float
    created_at: datetime

    model_config = {"from_attributes": True}
