"""
Queue CRUD, Pause/Resume, and Retry Policy routes.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.project import Project
from app.models.queue import Queue, QueueStatus
from app.models.retry_policy import RetryPolicy
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.queue import (
    QueueCreate,
    QueueUpdate,
    QueueResponse,
    QueueListResponse,
    RetryPolicyCreate,
    RetryPolicyUpdate,
    RetryPolicyResponse,
    QueueStatsResponse,
)

router = APIRouter(tags=["queues"])


# --- Helpers ---

async def _get_project_for_org(project_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.organization_id == org_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _get_queue_for_org(queue_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Queue:
    """Load a queue ensuring its project belongs to the user's org."""
    result = await db.execute(
        select(Queue)
        .join(Project, Queue.project_id == Project.id)
        .where(Queue.id == queue_id, Project.organization_id == org_id)
    )
    queue = result.scalar_one_or_none()
    if not queue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")
    return queue


# --- Queue CRUD ---

@router.post("/projects/{project_id}/queues", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
async def create_queue(
    project_id: uuid.UUID,
    body: QueueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_org(project_id, current_user.organization_id, db)
    now = datetime.now(timezone.utc)
    queue = Queue(
        project_id=project_id,
        name=body.name,
        concurrency_limit=body.concurrency_limit,
        status=QueueStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db.add(queue)
    await db.flush()
    return queue


@router.get("/projects/{project_id}/queues", response_model=QueueListResponse)
async def list_queues(
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_for_org(project_id, current_user.organization_id, db)
    base_query = select(Queue).where(Queue.project_id == project_id)
    
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(base_query.order_by(Queue.created_at.desc()).offset(offset).limit(page_size))
    items = result.scalars().all()
    
    return QueueListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/queues/{id}", response_model=QueueResponse)
async def get_queue(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_queue_for_org(id, current_user.organization_id, db)


@router.patch("/queues/{id}", response_model=QueueResponse)
async def update_queue(
    id: uuid.UUID,
    body: QueueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    if body.name is not None:
        queue.name = body.name
    if body.concurrency_limit is not None:
        queue.concurrency_limit = body.concurrency_limit
    queue.updated_at = datetime.now(timezone.utc)
    return queue


@router.delete("/queues/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_queue(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    
    # Check for active non-terminal jobs. Blocking delete prevents orphaning in-flight jobs.
    active_statuses = [
        JobStatus.QUEUED, JobStatus.SCHEDULED, JobStatus.CLAIMED, 
        JobStatus.RUNNING, JobStatus.RETRYING
    ]
    active_jobs = await db.execute(
        select(1).where(Job.queue_id == queue.id, Job.status.in_(active_statuses)).limit(1)
    )
    if active_jobs.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete queue with active non-terminal jobs",
        )
    
    await db.delete(queue)
    return None


# --- Pause/Resume ---

@router.post("/queues/{id}/pause", response_model=QueueResponse)
async def pause_queue(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    queue.status = QueueStatus.PAUSED
    queue.updated_at = datetime.now(timezone.utc)
    # Note: Phase 4 claim logic must filter by Queue.status == 'active'
    return queue


@router.post("/queues/{id}/resume", response_model=QueueResponse)
async def resume_queue(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    queue.status = QueueStatus.ACTIVE
    queue.updated_at = datetime.now(timezone.utc)
    return queue


# --- Queue Stats ---

@router.get("/queues/{id}/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    
    result = await db.execute(
        select(Job.status, func.count(Job.id))
        .where(Job.queue_id == queue.id)
        .group_by(Job.status)
    )
    counts = dict(result.all())
    
    return QueueStatsResponse(
        queued=counts.get(JobStatus.QUEUED, 0),
        scheduled=counts.get(JobStatus.SCHEDULED, 0),
        claimed=counts.get(JobStatus.CLAIMED, 0),
        running=counts.get(JobStatus.RUNNING, 0),
        completed=counts.get(JobStatus.COMPLETED, 0),
        failed=counts.get(JobStatus.FAILED, 0),
        retrying=counts.get(JobStatus.RETRYING, 0),
        dead_letter=counts.get(JobStatus.DEAD_LETTER, 0),
    )


# --- Retry Policies ---

@router.post("/queues/{id}/retry-policy", response_model=RetryPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_retry_policy(
    id: uuid.UUID,
    body: RetryPolicyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    
    # Check if policy already exists to return clean 409
    existing = await db.execute(select(1).where(RetryPolicy.queue_id == queue.id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Retry policy already exists for this queue")
        
    now = datetime.now(timezone.utc)
    policy = RetryPolicy(
        queue_id=queue.id,
        max_retries=body.max_retries,
        backoff_strategy=body.backoff_strategy,
        backoff_base_seconds=body.backoff_base_seconds,
        backoff_max_seconds=body.backoff_max_seconds,
        created_at=now,
        updated_at=now,
    )
    db.add(policy)
    
    try:
        await db.flush()
    except IntegrityError:
        # Fallback if race condition inserts duplicate
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Retry policy already exists for this queue")
        
    return policy


@router.get("/queues/{id}/retry-policy", response_model=RetryPolicyResponse)
async def get_retry_policy(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    result = await db.execute(select(RetryPolicy).where(RetryPolicy.queue_id == queue.id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retry policy not found for this queue")
    return policy


@router.patch("/queues/{id}/retry-policy", response_model=RetryPolicyResponse)
async def update_retry_policy(
    id: uuid.UUID,
    body: RetryPolicyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(id, current_user.organization_id, db)
    result = await db.execute(select(RetryPolicy).where(RetryPolicy.queue_id == queue.id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retry policy not found for this queue")
        
    if body.max_retries is not None:
        policy.max_retries = body.max_retries
    if body.backoff_strategy is not None:
        policy.backoff_strategy = body.backoff_strategy
    if body.backoff_base_seconds is not None:
        policy.backoff_base_seconds = body.backoff_base_seconds
    if body.backoff_max_seconds is not None:
        policy.backoff_max_seconds = body.backoff_max_seconds
        
    # We must enforce base <= max in case only one was updated
    if policy.backoff_max_seconds < policy.backoff_base_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="backoff_max_seconds must be >= backoff_base_seconds"
        )
        
    policy.updated_at = datetime.now(timezone.utc)
    return policy
