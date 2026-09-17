import uuid

from pydantic import BaseModel, Field


class BulkReprocessRequest(BaseModel):
    encounter_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class TaskSubmittedResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
