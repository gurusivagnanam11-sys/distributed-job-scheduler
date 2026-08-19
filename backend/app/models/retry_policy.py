import uuid
from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class RetryPolicy(TimestampMixin, Base):
    __tablename__ = "retry_policies"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    queue_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    backoff_strategy: Mapped[str] = mapped_column(
        String(50), default="exponential", nullable=False
    )  # Values: "fixed", "linear", "exponential"
    backoff_base_seconds: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    backoff_max_seconds: Mapped[float] = mapped_column(Float, default=3600.0, nullable=False)

    # Relationships
    queue = relationship("Queue", back_populates="retry_policy")
