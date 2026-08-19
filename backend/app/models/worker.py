import uuid
import enum
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class WorkerStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"  # Finishing current jobs, not accepting new ones


class Worker(TimestampMixin, Base):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[WorkerStatus] = mapped_column(
        SAEnum(WorkerStatus, name="worker_status", values_callable=lambda e: [x.value for x in e]),
        default=WorkerStatus.ONLINE,
        nullable=False,
    )
    # Updated in same transaction as WorkerHeartbeat insert — see design decisions
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    heartbeats = relationship("WorkerHeartbeat", back_populates="worker", cascade="all, delete-orphan", passive_deletes=True)
