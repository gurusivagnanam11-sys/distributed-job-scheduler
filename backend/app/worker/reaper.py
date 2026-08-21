"""
Reaper — reclaims jobs from dead/stuck workers.

Finds jobs where status IN ('claimed', 'running') AND lease_expires_at < now(),
meaning the worker that held them is presumed dead. For each:
- If retries remain: status='retrying', scheduled_at pushed forward, attempt_count++
- If retries exhausted: DLQ transition (status='dead_letter', DeadLetterEntry row)

Logs every reclaim explicitly with job_id, worker_id, and overdue duration.
Runs as its own loop in the worker process, separate from the claim loop.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.models.dead_letter_entry import DeadLetterEntry
from app.models.retry_policy import RetryPolicy
from app.services.retry import compute_delay

logger = logging.getLogger("worker.reaper")


async def reclaim_stale_jobs(session: AsyncSession) -> List[Tuple[uuid.UUID, str]]:
    """
    Find and reclaim jobs with expired leases.

    This function is independently testable — it takes a session, does its work,
    and the caller manages commit/rollback.

    Returns:
        List of (job_id, action) tuples where action is 'retrying' or 'dead_letter'.
    """
    now = datetime.now(timezone.utc)

    # Find stale jobs: claimed or running with expired lease
    result = await session.execute(
        select(Job).where(
            Job.status.in_([JobStatus.CLAIMED, JobStatus.RUNNING]),
            Job.lease_expires_at < now,
        ).with_for_update(skip_locked=True)
    )
    stale_jobs = list(result.scalars().all())

    if not stale_jobs:
        return []

    reclaimed = []
    for job in stale_jobs:
        overdue = now - job.lease_expires_at
        old_worker_id = job.claimed_by_worker_id

        # Fetch retry policy for this queue
        rp_result = await session.execute(
            select(RetryPolicy).where(RetryPolicy.queue_id == job.queue_id)
        )
        retry_policy = rp_result.scalar_one_or_none()

        # Increment attempt_count (the stale attempt counts as an attempt)
        job.attempt_count += 1

        if retry_policy and job.attempt_count < retry_policy.max_retries:
            # Retry path
            delay_seconds = compute_delay(job.attempt_count, retry_policy)
            job.status = JobStatus.RETRYING
            job.scheduled_at = now + timedelta(seconds=delay_seconds)
            job.claimed_by_worker_id = None
            job.claimed_at = None
            job.lease_expires_at = None
            job.updated_at = now
            action = "retrying"

            logger.warning(
                f"Reclaimed job {job.id} from worker {old_worker_id} "
                f"(lease overdue by {overdue.total_seconds():.1f}s). "
                f"Scheduling retry attempt {job.attempt_count + 1} in {delay_seconds}s.",
                extra={
                    "job_id": str(job.id),
                    "worker_id": str(old_worker_id),
                    "queue_id": str(job.queue_id),
                    "attempt": job.attempt_count,
                    "overdue_seconds": overdue.total_seconds(),
                },
            )
        else:
            # DLQ path: retries exhausted
            job.status = JobStatus.DEAD_LETTER
            job.updated_at = now

            dle = DeadLetterEntry(
                job_id=job.id,
                reason=(
                    f"Lease expired (overdue by {overdue.total_seconds():.1f}s) "
                    f"and retries exhausted (attempt {job.attempt_count})"
                ),
                failed_at=now,
                original_payload=job.payload,
            )
            session.add(dle)
            action = "dead_letter"

            logger.error(
                f"Job {job.id} moved to dead letter queue. "
                f"Reclaimed from worker {old_worker_id} "
                f"(lease overdue by {overdue.total_seconds():.1f}s). "
                f"Retries exhausted at attempt {job.attempt_count}.",
                extra={
                    "job_id": str(job.id),
                    "worker_id": str(old_worker_id),
                    "queue_id": str(job.queue_id),
                    "attempt": job.attempt_count,
                    "overdue_seconds": overdue.total_seconds(),
                },
            )

        reclaimed.append((job.id, action))

    await session.flush()
    return reclaimed
