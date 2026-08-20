"""
Job submission and read endpoints.

Job Submission handles 5 types:
- Immediate (scheduled_at=None) -> scheduled_at = now
- Delayed/Scheduled (scheduled_at=future) -> scheduled_at = future
- Recurring (cron_expression=str) -> creates RecurringJobTemplate
- Batch (batch=[...]) -> creates multiple Jobs in a single transaction

Dedupe Behavior:
- If a dedupe_key is provided and a job with that key already exists in a non-terminal state,
  we return the existing job (status 200 OK) instead of creating a new one or throwing an error.
- If the existing job is in a terminal state (completed, failed, dead_letter), we create a new one (201).
"""
import uuid
from datetime import datetime, timezone
from typing import Union, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.job import Job, JobStatus
from app.models.recurring_job_template import RecurringJobTemplate
from app.models.queue import Queue
from app.models.project import Project
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobResponse,
    JobListResponse,
    RecurringJobTemplateResponse,
    RecurringJobTemplateListResponse,
    RecurringJobTemplateUpdate,
)
from app.routers.queues import _get_queue_for_org

router = APIRouter(tags=["jobs"])


async def _validate_dependency(depends_on_job_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> Job:
    """Validate that the referenced job exists and belongs to the user's org."""
    result = await db.execute(
        select(Job)
        .join(Queue, Job.queue_id == Queue.id)
        .join(Project, Queue.project_id == Project.id)
        .where(Job.id == depends_on_job_id, Project.organization_id == org_id)
    )
    dep_job = result.scalar_one_or_none()
    if not dep_job:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dependency job {depends_on_job_id} not found in your organization."
        )
    return dep_job


async def _get_existing_dedupe_job(queue_id: uuid.UUID, dedupe_key: str, db: AsyncSession) -> Optional[Job]:
    """Check for an existing job with this dedupe_key that is NOT in a terminal state."""
    terminal_statuses = [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.DEAD_LETTER]
    
    result = await db.execute(
        select(Job)
        .where(
            Job.queue_id == queue_id,
            Job.dedupe_key == dedupe_key,
            Job.status.notin_(terminal_statuses)
        )
    )
    return result.scalar_one_or_none()


@router.post(
    "/queues/{queue_id}/jobs",
    response_model=Union[JobResponse, List[JobResponse], RecurringJobTemplateResponse],
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Returned existing job due to dedupe_key match"}},
)
async def submit_job(
    queue_id: uuid.UUID,
    body: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    response: __import__("fastapi").Response = None,  # To set 200 dynamically
):
    # Ensure queue exists and belongs to org
    queue = await _get_queue_for_org(queue_id, current_user.organization_id, db)
    now = datetime.now(timezone.utc)

    # 1. RECURRING JOB
    if body.cron_expression is not None:
        # compute next_run_at
        cron = croniter(body.cron_expression, now)
        next_run = cron.get_next(datetime)
        
        template = RecurringJobTemplate(
            queue_id=queue.id,
            cron_expression=body.cron_expression,
            job_payload=body.payload,
            is_active=True,
            next_run_at=next_run,
            created_at=now,
            updated_at=now,
        )
        db.add(template)
        await db.flush()
        return template

    # 2. BATCH JOBS
    if body.batch is not None:
        batch_id = str(uuid.uuid4())
        created_jobs = []
        
        for idx, item in enumerate(body.batch):
            if item.depends_on_job_id:
                try:
                    await _validate_dependency(item.depends_on_job_id, current_user.organization_id, db)
                except HTTPException as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Batch item {idx} failed dependency validation: {e.detail}"
                    )
            
            # Check dedupe for this item
            if item.dedupe_key:
                existing = await _get_existing_dedupe_job(queue.id, item.dedupe_key, db)
                if existing:
                    created_jobs.append(existing)
                    continue  # skip creation
            
            sched = item.scheduled_at if item.scheduled_at else now
            job = Job(
                queue_id=queue.id,
                status=JobStatus.SCHEDULED if sched > now else JobStatus.QUEUED,
                priority=item.priority,
                payload=item.payload,
                scheduled_at=sched,
                depends_on_job_id=item.depends_on_job_id,
                dedupe_key=item.dedupe_key,
                batch_id=batch_id,
                created_at=now,
                updated_at=now,
            )
            db.add(job)
            created_jobs.append(job)
            
        await db.flush()
        return created_jobs

    # 3. SINGLE JOB (Immediate / Delayed)
    if body.depends_on_job_id:
        await _validate_dependency(body.depends_on_job_id, current_user.organization_id, db)
        
    if body.dedupe_key:
        existing = await _get_existing_dedupe_job(queue.id, body.dedupe_key, db)
        if existing:
            if response:
                response.status_code = status.HTTP_200_OK
            return existing

    sched = body.scheduled_at if body.scheduled_at else now
    job = Job(
        queue_id=queue.id,
        status=JobStatus.SCHEDULED if sched > now else JobStatus.QUEUED,
        priority=body.priority,
        payload=body.payload,
        scheduled_at=sched,
        depends_on_job_id=body.depends_on_job_id,
        dedupe_key=body.dedupe_key,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.flush()
    return job


@router.get("/queues/{queue_id}/jobs", response_model=JobListResponse)
async def list_jobs(
    queue_id: uuid.UUID,
    status: Optional[JobStatus] = Query(None),
    batch_id: Optional[str] = Query(None),
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(queue_id, current_user.organization_id, db)
    
    query = select(Job).where(Job.queue_id == queue.id)
    if status:
        query = query.where(Job.status == status)
    if batch_id:
        query = query.where(Job.batch_id == batch_id)
    if created_after:
        query = query.where(Job.created_at >= created_after)
    if created_before:
        query = query.where(Job.created_at <= created_before)
        
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return JobListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.get("/jobs/{id}", response_model=JobResponse)
async def get_job(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job)
        .join(Queue, Job.queue_id == Queue.id)
        .join(Project, Queue.project_id == Project.id)
        .where(Job.id == id, Project.organization_id == current_user.organization_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


# --- RECURRING TEMPLATE MANAGEMENT ---

@router.get("/queues/{queue_id}/recurring-jobs", response_model=RecurringJobTemplateListResponse)
async def list_recurring_templates(
    queue_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(queue_id, current_user.organization_id, db)
    
    query = select(RecurringJobTemplate).where(RecurringJobTemplate.queue_id == queue.id)
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(RecurringJobTemplate.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return RecurringJobTemplateListResponse(items=list(items), total=total, page=page, page_size=page_size)


@router.patch("/queues/{queue_id}/recurring-jobs/{template_id}", response_model=RecurringJobTemplateResponse)
async def update_recurring_template(
    queue_id: uuid.UUID,
    template_id: uuid.UUID,
    body: RecurringJobTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(queue_id, current_user.organization_id, db)
    
    result = await db.execute(
        select(RecurringJobTemplate)
        .where(RecurringJobTemplate.id == template_id, RecurringJobTemplate.queue_id == queue.id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        
    if body.is_active is not None:
        template.is_active = body.is_active
        
    template.updated_at = datetime.now(timezone.utc)
    return template


@router.delete("/queues/{queue_id}/recurring-jobs/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring_template(
    queue_id: uuid.UUID,
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_org(queue_id, current_user.organization_id, db)
    
    result = await db.execute(
        select(RecurringJobTemplate)
        .where(RecurringJobTemplate.id == template_id, RecurringJobTemplate.queue_id == queue.id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        
    await db.delete(template)
    return None
