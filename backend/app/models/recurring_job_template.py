import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, ForeignKey, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class RecurringJobTemplate(TimestampMixin, Base):
    __tablename__ = "recurring_job_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    queue_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
    )
    cron_expression: Mapped[str] = mapped_column(String(255), nullable=False)
    job_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    queue = relationship("Queue", back_populates="recurring_templates")
