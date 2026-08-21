"""Security utilities: JWT handling, password hashing.

Password hashing: bcrypt via passlib (Phase 0 design decision — see docs/DESIGN_DECISIONS.md).
Refresh tokens are out of scope for Phase 1 — future improvement.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import pbkdf2_sha256
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# --- Password hashing (bcrypt) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_id: UUID, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token containing the user_id as 'sub' claim."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.JWT_EXPIRY_MINUTES))
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, load User with their Organization.

    Every protected route uses this dependency. The resolved user's
    organization_id is then used to scope all data access — a user
    must never see or modify another org's data.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# ---------------------------------------------------------------------------
# API Key authentication
# ---------------------------------------------------------------------------
# Header choice: X-API-Key (dedicated header, not Authorization: Bearer).
# Rationale: avoids ambiguity when both JWT and API-key tokens are 'Bearer'
# tokens — keeping them on separate headers lets request handlers distinguish
# the auth path without inspecting token contents. FastAPI's APIKeyHeader
# also produces cleaner OpenAPI docs than overloading the Bearer scheme.
#
# Scope: API keys are PROJECT-scoped (stricter than JWT, which is org-scoped).
# A key issued for Project A cannot submit jobs into queues belonging to
# Project B, even within the same organization.
# ---------------------------------------------------------------------------

from app.models.project import Project, ApiKey

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_project_via_api_key(
    raw_key: Optional[str] = Depends(_api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[Project]:
    """Resolve the Project associated with an X-API-Key header value.

    Returns None if the header is absent (allows caller to fall back to JWT).
    Raises 401 if the header is present but the key is invalid or revoked.

    Lookup strategy:
      1. Extract the first 12 chars of the raw key (key_prefix) — O(1) index scan.
      2. Load all ApiKey rows with that prefix (almost always one row).
      3. Verify the full key against the stored sha256_crypt hash.
      4. Reject if revoked_at is not null.
      5. Load and return the associated Project (with organization_id eager-loaded).
    """
    if not raw_key:
        return None

    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_api_key", "message": "Invalid or revoked API key"},
    )

    # Key format: jsk_<64 hex chars>  → prefix = first 12 chars ("jsk_" + 8 hex)
    if len(raw_key) < 12:
        raise _invalid

    prefix = raw_key[:12]

    result = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.project))
        .where(ApiKey.key_prefix == prefix)
    )
    candidates = result.scalars().all()

    # Verify full key hash against each candidate (normally exactly one)
    matched: Optional[ApiKey] = None
    for candidate in candidates:
        if pbkdf2_sha256.verify(raw_key, candidate.key_hash):
            matched = candidate
            break

    if matched is None:
        raise _invalid

    if matched.revoked_at is not None:
        raise _invalid

    return matched.project


async def get_submitter_org_id(
    request: Request,
    api_key_project: Optional[Project] = Depends(get_current_project_via_api_key),
    db: AsyncSession = Depends(get_db),
) -> Tuple[UUID, Optional[UUID]]:
    """Dual-auth dependency for job-submission endpoints.

    Tries API key first (X-API-Key header present → resolved by
    get_current_project_via_api_key). Falls back to JWT (Authorization: Bearer).
    Returns (org_id, project_id_or_none):
      - API key path: (project.organization_id, project.id)
        Callers MUST additionally verify the target queue's project_id == project.id
        (API keys are project-scoped, stricter than org-scoped JWT auth).
      - JWT path: (user.organization_id, None)
        Callers use org_id for scoping just as they always have.

    Raises 401 if neither credential is valid.
    """
    # ── API key path ─────────────────────────────────────────────────────────
    # If the X-API-Key header was present, get_current_project_via_api_key
    # already validated it (and raised 401 on failure) or returned None (absent).
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key is not None:
        # Header was present; api_key_project holds the resolved Project
        # (get_current_project_via_api_key raised 401 if invalid/revoked)
        if api_key_project is not None:
            return (api_key_project.organization_id, api_key_project.id)
        # Defensive guard — should not reach here
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "Invalid or revoked API key"},
        )

    # ── JWT path ──────────────────────────────────────────────────────────────
    # Extract the Bearer token from Authorization header directly (without
    # making the oauth2_scheme mandatory — that would reject API-key-only calls).
    authorization: Optional[str] = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Provide X-API-Key or Authorization: Bearer <token>"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Provide X-API-Key or Authorization: Bearer <token>"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_token", "message": "Invalid or expired token"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user_result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    return (user.organization_id, None)
