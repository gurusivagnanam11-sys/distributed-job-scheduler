import uuid
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan", passive_deletes=True)
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan", passive_deletes=True)
