"""
Recurring job scheduler — creates Job rows from active RecurringJobTemplate records.

Uses SELECT ... FOR UPDATE SKIP LOCKED on template rows to prevent duplicate
job creation when multiple worker processes run this scheduler concurrently.
This is the same locking pattern used in job claiming — consistent with the
rest of the codebase's approach to concurrency control.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from croniter import croniter

from app.models.recurring_job_template import RecurringJobTemplate
from app.models.job import Job, JobStatus

logger = logging.getLogger("worker.recurring_scheduler")


async def schedule_recurring_jobs(session: AsyncSession) -> int:
    """
    Find active recurring templates whose next_run_at has passed, lock them
    with FOR UPDATE SKIP LOCKED, create Job rows, and advance next_run_at.

    Uses FOR UPDATE SKIP LOCKED so that if two workers run this concurrently,
    one locks a template and the other skips it — preventing duplicate jobs.

    This function is independently testable — the caller manages commit/rollback.

    Returns:
        The number of jobs created.
    """
    now = datetime.now(timezone.utc)

    # SELECT ... FOR UPDATE SKIP LOCKED on templates whose next_run_at has passed.
    # This prevents two concurrent scheduler ticks from both creating a job
    # for the same template.
    result = await session.execute(
        text("""
            SELECT id FROM recurring_job_templates
            WHERE is_active = true
              AND next_run_at <= :now
            FOR UPDATE SKIP LOCKED
        """),
        {"now": now},
    )
    template_ids = [row[0] for row in result.fetchall()]

    if not template_ids:
        return 0

    # Re-fetch as ORM objects (already locked by the FOR UPDATE above)
    from sqlalchemy import select as sa_select
    templates_result = await session.execute(
        sa_select(RecurringJobTemplate).where(
            RecurringJobTemplate.id.in_(template_ids)
        )
    )
    templates = list(templates_result.scalars().all())

    jobs_created = 0
    for template in templates:
        job = Job(
            queue_id=template.queue_id,
            status=JobStatus.QUEUED,
            payload=template.job_payload,
            scheduled_at=template.next_run_at,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        jobs_created += 1

        # Advance next_run_at
        cron = croniter(template.cron_expression, now)
        template.next_run_at = cron.get_next(datetime)
        template.updated_at = now

        logger.info(
            f"Created recurring job for template {template.id}, "
            f"next run at {template.next_run_at}",
            extra={"queue_id": str(template.queue_id)},
        )

    await session.flush()
    return jobs_created
