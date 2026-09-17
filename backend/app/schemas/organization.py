import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
