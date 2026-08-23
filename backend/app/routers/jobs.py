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
from typing import Union, List, Optional, Tuple
from uuid import UUID as _UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from croniter import croniter

from app.core.database import get_db
from app.core.security import get_current_user, get_submitter_org_id
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
    submitter: Tuple[_UUID, Optional[_UUID]] = Depends(get_submitter_org_id),
    db: AsyncSession = Depends(get_db),
    response: __import__("fastapi").Response = None,  # To set 200 dynamically
):
    """Submit a job. Accepts either JWT (Authorization: Bearer) or API key (X-API-Key).

    API keys are project-scoped: a key for Project A cannot submit into queues
    belonging to Project B, even within the same organization.
    JWT auth is org-scoped (any queue in the same org is accessible).
    """
    org_id, api_key_project_id = submitter

    # Ensure queue exists and belongs to org
    queue = await _get_queue_for_org(queue_id, org_id, db)

    # Extra project-scope check for API key auth (stricter than JWT)
    if api_key_project_id is not None and queue.project_id != api_key_project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "project_scope_violation",
                    "message": "API key is not authorized for this queue's project"},
        )

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
                    await _validate_dependency(item.depends_on_job_id, org_id, db)
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
        await _validate_dependency(body.depends_on_job_id, org_id, db)
        
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
    q_id = queue.id
    try:
        await db.flush()
    except IntegrityError as e:
        if "uq_job_queue_dedupe_key" in str(e):
            await db.rollback()
            existing = await _get_existing_dedupe_job(q_id, body.dedupe_key, db)
            if existing:
                if response:
                    response.status_code = status.HTTP_200_OK
                return existing
        raise e
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


# --- OBSERVABILITY ---

from app.schemas.job import (
    JobEventResponse,
    JobTimelineResponse,
    JobExecutionResponse,
    JobExecutionListResponse,
)
from app.models.job_log import JobLog
from app.models.job_execution import JobExecution

@router.get("/jobs/{id}/timeline", response_model=JobTimelineResponse)
async def get_job_timeline(
    id: uuid.UUID,
    job: Job = Depends(get_job),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the timeline of events for a job, derived from Job timestamps and JobLog rows.
    Reuses the get_job dependency to guarantee identical org-scoping.
    """
    events = []
    
    # 1. Base created event
    events.append(
        JobEventResponse(
            timestamp=job.created_at,
            event_type="created",
            message="Job created"
        )
    )
    
    # 2. Fetch all JobLogs
    result = await db.execute(
        select(JobLog).where(JobLog.job_id == id).order_by(JobLog.timestamp.asc())
    )
    job_logs = result.scalars().all()
    
    # Optional: We could join JobExecution to get attempt_number and worker_id
    # if it's not in the log message, but for this implementation we'll fetch
    # executions to map execution_id to attempt_number and worker_id.
    exec_result = await db.execute(
        select(JobExecution).where(JobExecution.job_id == id)
    )
    executions = {e.id: e for e in exec_result.scalars().all()}
    
    for log in job_logs:
        exec_ref = executions.get(log.execution_id) if log.execution_id else None
        
        # Best effort mapping log message to event type based on executor.py log strings
        event_type = "info"
        msg_lower = log.message.lower()
        if "claimed by worker" in msg_lower:
            event_type = "claimed"
        elif "started execution attempt" in msg_lower:
            event_type = "started"
        elif "completed on attempt" in msg_lower:
            event_type = "completed"
        elif "failed attempt" in msg_lower and "retrying" in msg_lower:
            event_type = "retrying"
        elif "moved to dead letter queue" in msg_lower:
            event_type = "dead_letter"
        elif "execution failed" in msg_lower:
            event_type = "failed"
            
        events.append(
            JobEventResponse(
                timestamp=log.timestamp,
                event_type=event_type,
                attempt_number=exec_ref.attempt_number if exec_ref else None,
                worker_id=exec_ref.worker_id if exec_ref else None,
                message=log.message
            )
        )
        
    # Sort just in case, though they should be roughly ordered
    events.sort(key=lambda e: e.timestamp)
    
    return JobTimelineResponse(job_id=job.id, events=events)


@router.get("/jobs/{id}/executions", response_model=JobExecutionListResponse)
async def list_job_executions(
    id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    job: Job = Depends(get_job),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated list of execution attempts for a job.
    Reuses get_job for org-scoping.
    """
    query = select(JobExecution).where(JobExecution.job_id == id)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(JobExecution.attempt_number.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    response_items = []
    for item in items:
        dur = None
        if item.finished_at and item.started_at:
            dur = (item.finished_at - item.started_at).total_seconds()
            
        response_items.append(
            JobExecutionResponse(
                id=item.id,
                job_id=item.job_id,
                worker_id=item.worker_id,
                attempt_number=item.attempt_number,
                status=item.status.value,
                started_at=item.started_at,
                finished_at=item.finished_at,
                result=item.result,
                error=item.error,
                duration_seconds=dur,
            )
        )
    
    return JobExecutionListResponse(items=response_items, total=total, page=page, page_size=page_size)


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


# --- MANUAL RETRY (DLQ re-queue) ---

@router.post("/jobs/{id}/retry", response_model=JobResponse)
async def retry_job(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually re-queue a dead_letter job.

    Resets attempt_count=0, status='queued', scheduled_at=now(), clears claim fields.
    This is the "retry failed job" button for the dashboard (Phase 6).
    """
    result = await db.execute(
        select(Job)
        .join(Queue, Job.queue_id == Queue.id)
        .join(Project, Queue.project_id == Project.id)
        .where(Job.id == id, Project.organization_id == current_user.organization_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.status != JobStatus.DEAD_LETTER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only dead_letter jobs can be retried. Current status: {job.status.value}",
        )

    now = datetime.now(timezone.utc)
    job.status = JobStatus.QUEUED
    job.attempt_count = 0
    job.scheduled_at = now
    job.claimed_by_worker_id = None
    job.claimed_at = None
    job.lease_expires_at = None
    job.updated_at = now

    return job


# --- AI FAILURE SUMMARY ---

from app.schemas.job import JobFailureSummaryResponse
from app.core.config import settings

@router.get("/jobs/{id}/failure-summary", response_model=JobFailureSummaryResponse)
async def get_job_failure_summary(
    id: uuid.UUID,
    job: Job = Depends(get_job),
    db: AsyncSession = Depends(get_db),
):
    """
    Get an AI-generated plain-English summary of a job's most recent failure.
    Uses Google Gemini (gemini-1.5-flash) and caches the result on the JobExecution row.
    """
    from app.models.job_execution import ExecutionStatus
    
    # 1. Find most recent failed execution
    result = await db.execute(
        select(JobExecution)
        .where(JobExecution.job_id == id, JobExecution.status == ExecutionStatus.FAILED)
        .order_by(JobExecution.attempt_number.desc())
        .limit(1)
    )
    execution = result.scalar_one_or_none()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This job has no failed executions"
        )
        
    # 2. Return cached if available
    if execution.ai_failure_summary:
        return JobFailureSummaryResponse(
            job_id=job.id,
            execution_id=execution.id,
            attempt_number=execution.attempt_number,
            summary=execution.ai_failure_summary,
            cached=True
        )
        
    # 3. Handle case where error string is empty or None
    raw_error = execution.error or "No error message recorded."
    
    # 4. Call Gemini API
    try:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")
            
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        prompt = f"Analyze this error message: '{raw_error}'. Provide a one-sentence plain-English summary of the likely cause plus one suggested next step."
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = await model.generate_content_async(prompt)
        
        summary_text = response.text
        
        # 5. Cache result
        execution.ai_failure_summary = summary_text
        await db.commit()
        
        return JobFailureSummaryResponse(
            job_id=job.id,
            execution_id=execution.id,
            attempt_number=execution.attempt_number,
            summary=summary_text,
            cached=False
        )
        
    except Exception as e:
        # 6. Graceful degradation on LLM failure
        return JobFailureSummaryResponse(
            job_id=job.id,
            execution_id=execution.id,
            attempt_number=execution.attempt_number,
            summary=None,
            cached=False,
            raw_error=raw_error,
            note="AI summarization unavailable"
        )
