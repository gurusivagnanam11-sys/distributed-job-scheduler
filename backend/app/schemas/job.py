import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator
from croniter import croniter

from app.models.job import JobStatus


# A grace window of 60 seconds is allowed for `scheduled_at` to avoid
# rejecting valid jobs created slightly in the past due to network delays or unsynced clocks.
GRACE_WINDOW_SECONDS = 60


def validate_scheduled_time(dt: Optional[datetime]) -> None:
    if dt is None:
        return
    now = datetime.now(timezone.utc)
    if dt < (now - timedelta(seconds=GRACE_WINDOW_SECONDS)):
        raise ValueError("scheduled_at cannot be more than 60 seconds in the past")


class JobCreateBase(BaseModel):
    payload: Optional[dict] = Field(None, description="Arbitrary JSON payload for the job")
    priority: int = Field(0, description="Higher number = higher priority")
    dedupe_key: Optional[str] = Field(None, max_length=255, description="Idempotency key")
    depends_on_job_id: Optional[uuid.UUID] = Field(None, description="Job ID this job depends on")


class JobCreateBatchItem(JobCreateBase):
    scheduled_at: Optional[datetime] = Field(None, description="Future timestamp to schedule the job")
    
    @model_validator(mode="after")
    def check_scheduled_at(self) -> "JobCreateBatchItem":
        validate_scheduled_time(self.scheduled_at)
        return self


class JobCreate(JobCreateBase):
    scheduled_at: Optional[datetime] = Field(None, description="For Delayed/Scheduled jobs")
    cron_expression: Optional[str] = Field(None, max_length=255, description="For Recurring jobs")
    batch: Optional[List[JobCreateBatchItem]] = Field(None, max_length=500, description="For Batch jobs")

    @model_validator(mode="after")
    def validate_job_submission(self) -> "JobCreate":
        # Check mutual exclusivity
        provided_types = sum([
            self.scheduled_at is not None,
            self.cron_expression is not None,
            self.batch is not None and len(self.batch) > 0
        ])
        
        if provided_types > 1:
            raise ValueError("Provide at most one of scheduled_at, cron_expression, or batch")

        # Validate cron
        if self.cron_expression is not None:
            if not croniter.is_valid(self.cron_expression):
                raise ValueError("Invalid cron_expression")
                
        # Validate scheduled_at
        if self.scheduled_at is not None:
            validate_scheduled_time(self.scheduled_at)

        return self


class JobResponse(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    status: JobStatus
    priority: int
    payload: Optional[dict]
    scheduled_at: datetime
    claimed_by_worker_id: Optional[uuid.UUID]
    claimed_at: Optional[datetime]
    lease_expires_at: Optional[datetime]
    attempt_count: int
    depends_on_job_id: Optional[uuid.UUID]
    dedupe_key: Optional[str]
    batch_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int


class RecurringJobTemplateResponse(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    cron_expression: str
    job_payload: Optional[dict]
    is_active: bool
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecurringJobTemplateListResponse(BaseModel):
    items: List[RecurringJobTemplateResponse]
    total: int
    page: int
    page_size: int


class RecurringJobTemplateUpdate(BaseModel):
    is_active: Optional[bool] = None
