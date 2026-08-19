import uuid
from datetime import datetime
from sqlalchemy import Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class DeadLetterEntry(TimestampMixin, Base):
    __tablename__ = "dead_letter_entries"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="dead_letter_entries")
