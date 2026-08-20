import enum
import uuid
from sqlalchemy import String, Integer, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class QueueStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class Queue(TimestampMixin, Base):
    __tablename__ = "queues"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    status: Mapped[QueueStatus] = mapped_column(
        SAEnum(QueueStatus, name="queue_status", values_callable=lambda e: [x.value for x in e]),
        default=QueueStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Relationships
    project = relationship("Project", back_populates="queues")
    retry_policy = relationship("RetryPolicy", back_populates="queue", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    jobs = relationship("Job", back_populates="queue", cascade="all, delete-orphan", passive_deletes=True)
    recurring_templates = relationship("RecurringJobTemplate", back_populates="queue", passive_deletes=True)
