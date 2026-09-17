import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CreateContactInquiryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    organization_name: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=5000)


class ContactInquiryOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    organization_name: str | None
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
