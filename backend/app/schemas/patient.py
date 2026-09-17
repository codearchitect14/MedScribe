import uuid
from datetime import date

from pydantic import BaseModel, Field


class CreatePatientRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=20)
    external_reference: str | None = Field(default=None, max_length=100)


class PatientOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date | None
    sex: str | None
    external_reference: str | None

    model_config = {"from_attributes": True}
