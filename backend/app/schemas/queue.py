"""Pydantic schemas for Queue CRUD, Retry Policies, and Stats."""
import uuid
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, model_validator
from app.models.queue import QueueStatus
from app.models.job import JobStatus


# --- Queue Schemas ---

class QueueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Queue name (1-255 chars)")
    concurrency_limit: int = Field(10, gt=0, description="Maximum concurrent jobs")


class QueueUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    concurrency_limit: Optional[int] = Field(None, gt=0)


class QueueResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    concurrency_limit: int
    status: QueueStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QueueListResponse(BaseModel):
    items: List[QueueResponse]
    total: int
    page: int
    page_size: int


# --- Retry Policy Schemas ---

class RetryPolicyCreate(BaseModel):
    max_retries: int = Field(3, ge=0)
    backoff_strategy: Literal["fixed", "linear", "exponential"] = "exponential"
    backoff_base_seconds: float = Field(2.0, gt=0)
    backoff_max_seconds: float = Field(3600.0, gt=0)

    @model_validator(mode="after")
    def validate_backoff(self) -> "RetryPolicyCreate":
        if self.backoff_max_seconds < self.backoff_base_seconds:
            raise ValueError("backoff_max_seconds must be >= backoff_base_seconds")
        return self


class RetryPolicyUpdate(BaseModel):
    max_retries: Optional[int] = Field(None, ge=0)
    backoff_strategy: Optional[Literal["fixed", "linear", "exponential"]] = None
    backoff_base_seconds: Optional[float] = Field(None, gt=0)
    backoff_max_seconds: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_backoff(self) -> "RetryPolicyUpdate":
        base = self.backoff_base_seconds
        max_sec = self.backoff_max_seconds
        
        # We can only validate if both are provided.
        # If one is provided, we'd need DB state to validate against the other,
        # but schema-level validation can only check what's here.
        if base is not None and max_sec is not None:
            if max_sec < base:
                raise ValueError("backoff_max_seconds must be >= backoff_base_seconds")
        return self


class RetryPolicyResponse(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    max_retries: int
    backoff_strategy: str
    backoff_base_seconds: float
    backoff_max_seconds: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Queue Stats Schema ---

class QueueStatsResponse(BaseModel):
    queued: int = 0
    scheduled: int = 0
    claimed: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    retrying: int = 0
    dead_letter: int = 0


class QueueMetricsResponse(BaseModel):
    id: uuid.UUID
    counts: QueueStatsResponse
    throughput_24h: int
    success_rate_24h: float
    avg_execution_duration_seconds_24h: float
