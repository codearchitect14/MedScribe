from datetime import date

from pydantic import BaseModel

from app.models.analytics_rollup import RollupType


class RollupTriggerRequest(BaseModel):
    period: date | None = None  # defaults to "yesterday" in the task, matching the nightly schedule


class RollupOut(BaseModel):
    rollup_type: RollupType
    period: date
    dimensions: list[dict]

    model_config = {"from_attributes": True}


class AnalyticsSeriesResponse(BaseModel):
    rollup_type: RollupType
    start_date: date
    end_date: date
    rollups: list[RollupOut]
