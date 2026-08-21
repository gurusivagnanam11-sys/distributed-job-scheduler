import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.models.worker import WorkerStatus

class WorkerResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: WorkerStatus
    last_heartbeat_at: Optional[datetime]
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class WorkerListResponse(BaseModel):
    items: List[WorkerResponse]
    total: int
    page: int
    page_size: int
