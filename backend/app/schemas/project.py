"""Pydantic schemas for Project CRUD and API key management."""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# --- Project schemas ---

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project name (1-255 chars)")
    description: Optional[str] = Field(None, max_length=2000)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class ProjectResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int


# --- API Key schemas ---

class ApiKeyCreate(BaseModel):
    label: Optional[str] = Field(None, max_length=255, description="Human-readable label for the key")


class ApiKeyCreateResponse(BaseModel):
    """Returned once on creation — raw_key is NEVER retrievable again."""
    id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: Optional[str]
    raw_key: str  # Only shown once!
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyResponse(BaseModel):
    """List view — shows prefix and label only, never the hash or raw key."""
    id: uuid.UUID
    project_id: uuid.UUID
    key_prefix: str
    label: Optional[str]
    created_at: datetime
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ApiKeyListResponse(BaseModel):
    items: List[ApiKeyResponse]
