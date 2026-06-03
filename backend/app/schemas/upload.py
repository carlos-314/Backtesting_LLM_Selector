import uuid
from datetime import date, datetime

from pydantic import BaseModel


class UploadBatchResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    week_date: date
    status: str
    error_detail: str | None = None
    row_count: int | None = None
    warning_count: int = 0
    duplicate_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
