"""
Auth router: signup and login.

Org-creation decision: An Organization is auto-created on signup, named after the
organization_name field the user provides. This avoids a two-step onboarding flow
and lets a new user immediately create projects and submit jobs after signup.
"""
from datetime import timezone, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    SignupResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. Auto-creates an Organization for them."""
    # Check if email already taken
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Check if org name already taken
    existing_org = await db.execute(
        select(Organization).where(Organization.name == body.organization_name)
    )
    if existing_org.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this name already exists",
        )

    # Create org
    now = datetime.now(timezone.utc)
    org = Organization(name=body.organization_name, created_at=now, updated_at=now)
    db.add(org)
    await db.flush()  # Get org.id

    # Create user
    user = User(
        organization_id=org.id,
        email=body.email,
        password_hash=hash_password(body.password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()  # Get user.id

    # Generate token
    expires_in = settings.JWT_EXPIRY_MINUTES * 60
    access_token = create_access_token(user.id)

    return SignupResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            organization_id=user.organization_id,
            is_active=user.is_active,
        ),
        token=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email/password, receive a JWT access token."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    expires_in = settings.JWT_EXPIRY_MINUTES * 60
    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )
