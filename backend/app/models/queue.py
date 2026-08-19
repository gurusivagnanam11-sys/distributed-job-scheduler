import uuid
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


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

    # Relationships
    project = relationship("Project", back_populates="queues")
    retry_policy = relationship("RetryPolicy", back_populates="queue", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    jobs = relationship("Job", back_populates="queue", cascade="all, delete-orphan", passive_deletes=True)
