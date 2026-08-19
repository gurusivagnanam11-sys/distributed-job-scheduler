import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    String, Integer, Text, ForeignKey, DateTime, Enum as SAEnum,
    Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class JobStatus(str, enum.Enum):
    """Job status enum — values defined in AGENTS.md §4."""
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    queue_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", values_callable=lambda e: [x.value for x in e]),
        default=JobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    
    # Claim tracking
    claimed_by_worker_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Retry tracking
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Workflow dependencies (nullable — for workflow deps, Phase 7)
    depends_on_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Idempotent submission
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Batch grouping
    batch_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Relationships
    queue = relationship("Queue", back_populates="jobs")
    claimed_by_worker = relationship("Worker", foreign_keys=[claimed_by_worker_id])
    dependency = relationship("Job", remote_side="Job.id", foreign_keys=[depends_on_job_id])
    
    # RESTRICT delete: Job cannot be deleted if it has executions (audit trail)
    executions = relationship("JobExecution", back_populates="job", passive_deletes=False)
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan", passive_deletes=True)
    dead_letter_entries = relationship("DeadLetterEntry", back_populates="job", passive_deletes=False)

    __table_args__ = (
        # Unique constraint for idempotent submission within a queue
        UniqueConstraint("queue_id", "dedupe_key", name="uq_job_queue_dedupe_key"),
        # Index for the claim query: status + scheduled_at + priority
        Index("ix_jobs_claimable", "queue_id", "status", "scheduled_at", "priority"),
    )
