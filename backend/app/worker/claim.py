"""
Atomic job claim — the single most important piece of code in this repo.

Implements the reference query from AGENTS.md §5 with exact transaction boundaries:
1. Compute available_slots IN THE SAME TRANSACTION as the claim (never as a prior query).
2. SELECT ... FOR UPDATE SKIP LOCKED to prevent workers blocking each other.
3. Set lease_expires_at on claim for reaper detection.

The claim function uses raw SQL to keep the locking semantics crystal-clear and
auditable against the reference query. This is the one place where clarity of
transactional behavior matters more than ORM convenience.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.job import Job, JobStatus


async def claim_jobs(
    session: AsyncSession,
    worker_id: uuid.UUID,
    queue_id: uuid.UUID,
    limit: int = 10,
) -> List[Job]:
    """
    Atomically claim up to `limit` jobs from a queue, respecting concurrency_limit.

    This function MUST be called within a transaction that the caller manages.
    The entire operation — computing available slots, locking candidate rows,
    and updating them — happens in a single transaction to prevent race conditions.

    Args:
        session: An AsyncSession. The caller is responsible for commit/rollback.
        worker_id: The UUID of the worker claiming jobs.
        queue_id: The UUID of the queue to claim from.
        limit: Max jobs this worker wants to claim in one poll cycle.

    Returns:
        List of Job ORM instances that were successfully claimed.
        Empty list if the queue is paused, full, or has no eligible jobs.
    """
    lease_seconds = settings.WORKER_LEASE_DURATION_SECONDS

    # ──────────────────────────────────────────────────────────────────────
    # STEP 0: Lock the queue row with SELECT ... FOR UPDATE.
    #
    # This is the critical serialization point: without this lock, concurrent
    # workers each compute available_slots independently and can all see
    # available_slots=3 simultaneously, leading to over-claiming past the
    # concurrency_limit. By locking the queue row (WITHOUT SKIP LOCKED),
    # we force concurrent claim transactions for the same queue to serialize:
    # Worker B waits for Worker A to commit, then sees the updated count.
    #
    # This is an extension of the §5 reference query, not a restructuring.
    # The jobs themselves still use FOR UPDATE SKIP LOCKED (Step 2).
    # ──────────────────────────────────────────────────────────────────────
    queue_check = await session.execute(
        text("""
            SELECT concurrency_limit, status FROM queues
            WHERE id = :queue_id
            FOR UPDATE
        """),
        {"queue_id": queue_id},
    )
    queue_row = queue_check.fetchone()
    if queue_row is None:
        return []
    concurrency_limit, queue_status = queue_row
    if queue_status != "active":
        return []

    # ──────────────────────────────────────────────────────────────────────
    # STEP 1: Compute available_slots IN THE SAME TRANSACTION.
    # available_slots = concurrency_limit - (count of jobs in 'claimed' or 'running')
    #
    # Because we hold a FOR UPDATE lock on the queue row, no other worker
    # can be in this section concurrently for the same queue. This means
    # the count is accurate — it includes all committed claims from workers
    # that already released the lock.
    # ──────────────────────────────────────────────────────────────────────
    running_count_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM jobs
            WHERE queue_id = :queue_id
              AND status IN ('claimed', 'running')
        """),
        {"queue_id": queue_id},
    )
    running_count = running_count_result.scalar_one()
    available_slots = concurrency_limit - running_count

    if available_slots <= 0:
        return []

    # The actual limit is the minimum of what the worker wants and what's available.
    effective_limit = min(limit, available_slots)

    # ──────────────────────────────────────────────────────────────────────
    # STEP 2: SELECT ... FOR UPDATE SKIP LOCKED — reference query from §5.
    #
    # This is the verbatim shape from AGENTS.md:
    #   SELECT id FROM jobs
    #   WHERE queue_id = :queue_id
    #     AND status IN ('queued', 'scheduled', 'retrying')
    #     AND scheduled_at <= now()
    #     AND (depends_on_job_id IS NULL OR EXISTS (
    #           SELECT 1 FROM jobs d WHERE d.id = jobs.depends_on_job_id
    #                                  AND d.status = 'completed'))
    #   ORDER BY priority DESC, scheduled_at ASC
    #   LIMIT :available_slots
    #   FOR UPDATE SKIP LOCKED;
    # ──────────────────────────────────────────────────────────────────────
    select_result = await session.execute(
        text("""
            SELECT id FROM jobs
            WHERE queue_id = :queue_id
              AND status IN ('queued', 'scheduled', 'retrying')
              AND scheduled_at <= now()
              AND (depends_on_job_id IS NULL OR EXISTS (
                    SELECT 1 FROM jobs d
                    WHERE d.id = jobs.depends_on_job_id
                      AND d.status = 'completed'))
            ORDER BY priority DESC, scheduled_at ASC
            LIMIT :effective_limit
            FOR UPDATE SKIP LOCKED
        """),
        {"queue_id": queue_id, "effective_limit": effective_limit},
    )
    claimed_ids = [row[0] for row in select_result.fetchall()]

    if not claimed_ids:
        return []

    # ──────────────────────────────────────────────────────────────────────
    # STEP 3: UPDATE claimed jobs — reference query from §5.
    #
    #   UPDATE jobs SET status = 'claimed', claimed_by_worker_id = :worker_id,
    #          claimed_at = now(),
    #          lease_expires_at = now() + interval ':lease_seconds seconds'
    #   WHERE id = ANY(:claimed_ids);
    # ──────────────────────────────────────────────────────────────────────
    await session.execute(
        text("""
            UPDATE jobs
            SET status = 'claimed',
                claimed_by_worker_id = :worker_id,
                claimed_at = now(),
                lease_expires_at = now() + make_interval(secs => :lease_seconds)
            WHERE id = ANY(:claimed_ids)
        """),
        {
            "worker_id": worker_id,
            "lease_seconds": lease_seconds,
            "claimed_ids": claimed_ids,
        },
    )

    # Re-fetch as ORM objects so callers get proper Job instances.
    from sqlalchemy import select as sa_select
    result = await session.execute(
        sa_select(Job).where(Job.id.in_(claimed_ids))
    )
    jobs = list(result.scalars().all())
    
    from app.services.observability import log_job_event
    for job in jobs:
        await log_job_event(
            session=session,
            job_id=job.id,
            execution_id=None,
            level="INFO",
            message=f"Job {job.id} claimed by worker {worker_id}",
            worker_id=str(worker_id),
            queue_id=str(queue_id),
            attempt=job.attempt_count + 1,
        )
        
    return jobs
