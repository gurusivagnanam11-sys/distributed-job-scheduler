"""
Job executor — runs claimed jobs concurrently and records results.

IMPORTANT: Each concurrently-executing job uses its OWN DB session, created
fresh from async_session_factory(). A shared AsyncSession used concurrently
across asyncio tasks would cause hard-to-debug errors or silent corruption.

Handler contract (stub for this assessment):
  The handler inspects job.payload for a "simulate" key:
    - {"simulate": "success"}            → completes normally
    - {"simulate": "fail", "error": "…"} → raises RuntimeError
    - {"simulate": "slow", "duration": N} → sleeps N seconds then succeeds
    - None / unrecognized                → succeeds immediately (no-op)
  Real handler plug-in design (e.g., looking up a callable by name in the
  payload) is not the point of this phase — the stub is sufficient to exercise
  the claim→execute→retry→complete lifecycle.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.models.job import Job, JobStatus
from app.models.job_execution import JobExecution, ExecutionStatus
from app.models.retry_policy import RetryPolicy
from app.services.retry import compute_delay

logger = logging.getLogger("worker.executor")

# Maximum number of jobs a single worker executes concurrently.
MAX_CONCURRENT_EXECUTIONS = 10


async def _run_handler(job: Job) -> dict:
    """
    Stub handler — determines behavior from job.payload.

    Returns a result dict on success. Raises RuntimeError on simulated failure.
    """
    payload = job.payload or {}
    simulate = payload.get("simulate")

    if simulate == "fail":
        error_msg = payload.get("error", "Simulated job failure")
        raise RuntimeError(error_msg)
    elif simulate == "slow":
        duration = payload.get("duration", 1)
        await asyncio.sleep(duration)
        return {"status": "completed", "slept_for": duration}
    elif simulate == "success":
        return {"status": "completed"}
    else:
        # No-op: unrecognized or missing payload succeeds immediately
        return {"status": "completed"}


async def _execute_single_job(job_id: uuid.UUID, worker_id: uuid.UUID) -> None:
    """
    Execute a single claimed job in its own DB session.

    CRITICAL: This function creates its own AsyncSession. It is NOT safe to
    share a session across concurrent asyncio tasks. Each call to this function
    gets an independent connection and transaction.
    """
    async with async_session_factory() as session:
        try:
            # Re-fetch the job within this session (the claim session is separate).
            result = await session.execute(
                select(Job).where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job is None:
                logger.error(f"Job {job_id} not found during execution")
                return

            now = datetime.now(timezone.utc)

            # Transition: claimed → running, increment attempt_count
            job.status = JobStatus.RUNNING
            job.attempt_count += 1
            job.updated_at = now

            # Create execution record
            execution = JobExecution(
                job_id=job.id,
                worker_id=worker_id,
                attempt_number=job.attempt_count,
                status=ExecutionStatus.RUNNING,
                started_at=now,
            )
            session.add(execution)
            await session.flush()
            
            from app.services.observability import log_job_event

            await log_job_event(
                session=session,
                job_id=job.id,
                execution_id=execution.id,
                level="INFO",
                message=f"Started execution attempt {job.attempt_count} for job {job.id}",
                worker_id=str(worker_id),
                queue_id=str(job.queue_id),
                attempt=job.attempt_count,
            )

            # Run the handler
            try:
                handler_result = await _run_handler(job)

                # Success path
                finished_at = datetime.now(timezone.utc)
                job.status = JobStatus.COMPLETED
                job.updated_at = finished_at
                execution.status = ExecutionStatus.COMPLETED
                execution.finished_at = finished_at
                execution.result = handler_result

                await log_job_event(
                    session=session,
                    job_id=job.id,
                    execution_id=execution.id,
                    level="INFO",
                    message=f"Job {job.id} completed on attempt {job.attempt_count}",
                    worker_id=str(worker_id),
                    queue_id=str(job.queue_id),
                    attempt=job.attempt_count,
                )

            except Exception as handler_error:
                # Failure path — determine retry or final failure
                finished_at = datetime.now(timezone.utc)
                execution.status = ExecutionStatus.FAILED
                execution.finished_at = finished_at
                execution.error = str(handler_error)
                
                await log_job_event(
                    session=session,
                    job_id=job.id,
                    execution_id=execution.id,
                    level="ERROR",
                    message=f"Execution failed: {str(handler_error)}",
                    worker_id=str(worker_id),
                    queue_id=str(job.queue_id),
                    attempt=job.attempt_count,
                )

                # Fetch retry policy for this queue
                retry_policy_result = await session.execute(
                    select(RetryPolicy).where(RetryPolicy.queue_id == job.queue_id)
                )
                retry_policy = retry_policy_result.scalar_one_or_none()

                if retry_policy and job.attempt_count < retry_policy.max_retries:
                    # Retry: compute delay, reschedule
                    delay_seconds = compute_delay(job.attempt_count, retry_policy)
                    job.status = JobStatus.RETRYING
                    job.scheduled_at = finished_at + timedelta(seconds=delay_seconds)
                    # Clear claim fields so the job can be re-claimed
                    job.claimed_by_worker_id = None
                    job.claimed_at = None
                    job.lease_expires_at = None
                    job.updated_at = finished_at

                    await log_job_event(
                        session=session,
                        job_id=job.id,
                        execution_id=execution.id,
                        level="INFO",
                        message=f"Job {job.id} failed attempt {job.attempt_count}, retrying in {delay_seconds}s (max {retry_policy.max_retries})",
                        worker_id=str(worker_id),
                        queue_id=str(job.queue_id),
                        attempt=job.attempt_count,
                    )
                else:
                    # No retries left (or no retry policy): DLQ transition
                    job.status = JobStatus.DEAD_LETTER
                    job.updated_at = finished_at

                    # Write DeadLetterEntry row
                    from app.models.dead_letter_entry import DeadLetterEntry
                    dle = DeadLetterEntry(
                        job_id=job.id,
                        reason=(
                            f"Execution failed after {job.attempt_count} attempts. "
                            f"Last error: {str(handler_error)}"
                        ),
                        failed_at=finished_at,
                        original_payload=job.payload,
                    )
                    session.add(dle)

                    await log_job_event(
                        session=session,
                        job_id=job.id,
                        execution_id=execution.id,
                        level="WARNING",
                        message=f"Job {job.id} moved to dead letter queue after {job.attempt_count} attempts",
                        worker_id=str(worker_id),
                        queue_id=str(job.queue_id),
                        attempt=job.attempt_count,
                    )

            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.exception(f"Unexpected error executing job {job_id}: {e}")


async def execute_jobs(jobs: List[Job], worker_id: uuid.UUID) -> None:
    """
    Execute a batch of claimed jobs concurrently, bounded by a semaphore.

    Each job runs in its own DB session (see _execute_single_job docstring).
    asyncio.gather is used for concurrency; a Semaphore caps the number of
    simultaneously-running handlers to avoid overwhelming the worker.
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXECUTIONS)

    async def _bounded_execute(job: Job) -> None:
        async with semaphore:
            await _execute_single_job(job.id, worker_id)

    await asyncio.gather(*[_bounded_execute(job) for job in jobs])
