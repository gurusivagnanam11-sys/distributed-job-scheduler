"""Pydantic schemas for authentication (signup, login, token response)."""
import uuid
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    organization_name: str = Field(
        ..., min_length=1, max_length=255,
        description="Name for the auto-created organization",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    organization_id: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}


class SignupResponse(BaseModel):
    user: UserResponse
    token: TokenResponse
