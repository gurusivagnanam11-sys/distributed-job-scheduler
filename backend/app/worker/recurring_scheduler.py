"""
Stub for Recurring Job Scheduler (Phase 4 wiring).
"""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter

from app.models.recurring_job_template import RecurringJobTemplate
from app.models.job import Job, JobStatus


async def schedule_recurring_jobs(db: AsyncSession) -> int:
    """
    Find active recurring templates whose next_run_at has passed.
    For each, create a new Job and advance next_run_at.
    
    Returns:
        The number of jobs scheduled.
    """
    now = datetime.now(timezone.utc)
    
    # In a real distributed worker, we'd want row-level locking (`FOR UPDATE SKIP LOCKED`)
    # to prevent multiple scheduler instances from advancing the same template.
    # We will just do a simple query here and let Phase 4 handle lock semantics if needed.
    result = await db.execute(
        select(RecurringJobTemplate)
        .where(RecurringJobTemplate.is_active == True)
        .where(RecurringJobTemplate.next_run_at <= now)
    )
    templates = result.scalars().all()
    
    jobs_created = 0
    for template in templates:
        # Create the new job
        job = Job(
            queue_id=template.queue_id,
            status=JobStatus.QUEUED,
            payload=template.job_payload,
            scheduled_at=template.next_run_at, # schedule it for when it was supposed to run
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        jobs_created += 1
        
        # Advance next_run_at
        cron = croniter(template.cron_expression, now)
        template.next_run_at = cron.get_next(datetime)
        template.updated_at = now
        
    await db.flush()
    return jobs_created
