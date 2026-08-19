"""Project CRUD — all routes scoped to the current user's organization."""
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.models.project import Project, ApiKey
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyListResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])


# --- Helper: resolve project scoped to org ---

async def _get_project_for_org(
    project_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """Load a project, ensuring it belongs to the user's org. Returns 404 if not found
    or belongs to a different org (intentionally 404, not 403, to avoid leaking existence)."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == org_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


# --- Project CRUD ---

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    project = Project(
        organization_id=current_user.organization_id,
        name=body.name,
        description=body.description,
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    await db.flush()
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects for the current user's organization with pagination."""
    base_query = select(Project).where(
        Project.organization_id == current_user.organization_id
    )

    # Total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Project.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_project_for_org(project_id, current_user.organization_id, db)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_for_org(project_id, current_user.organization_id, db)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_for_org(project_id, current_user.organization_id, db)
    await db.delete(project)
    await db.flush()


# --- API Key management ---

@router.post(
    "/{project_id}/api-keys",
    response_model=ApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    project_id: uuid.UUID,
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for a project.

    The raw key is returned ONCE in this response and is never retrievable again.
    Only the hash is stored; the prefix is kept for identification in list views.
    """
    project = await _get_project_for_org(project_id, current_user.organization_id, db)

    # Generate a cryptographically secure random key
    # Format: jsk_<32 random hex chars> (jsk = job scheduler key)
    raw_key = f"jsk_{secrets.token_hex(32)}"
    key_prefix = raw_key[:12]  # "jsk_" + first 8 hex chars

    from passlib.hash import sha256_crypt
    key_hash = sha256_crypt.hash(raw_key)

    now = datetime.now(timezone.utc)
    api_key = ApiKey(
        project_id=project.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        label=body.label,
        created_at=now,
        updated_at=now,
    )
    db.add(api_key)
    await db.flush()

    return ApiKeyCreateResponse(
        id=api_key.id,
        project_id=api_key.project_id,
        key_prefix=api_key.key_prefix,
        label=api_key.label,
        raw_key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("/{project_id}/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List API keys for a project — shows prefix and label only, never the hash or raw key."""
    await _get_project_for_org(project_id, current_user.organization_id, db)

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.project_id == project_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    return ApiKeyListResponse(
        items=[ApiKeyResponse.model_validate(k) for k in keys]
    )


@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key — sets revoked_at, does NOT hard-delete."""
    await _get_project_for_org(project_id, current_user.organization_id, db)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.project_id == project_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if api_key.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key is already revoked",
        )

    api_key.revoked_at = datetime.now(timezone.utc)
    await db.flush()
