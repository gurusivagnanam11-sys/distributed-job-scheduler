"""
Worker tests — Phase 4A.

The concurrent claim test (test_concurrent_claim_no_double_assignment) is the single
most important test in this repo. It exercises FOR UPDATE SKIP LOCKED under real
contention with separate DB connections, not sequential calls dressed up as concurrent.
"""
import uuid
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from collections import Counter

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.job import Job, JobStatus
from app.models.queue import Queue, QueueStatus
from app.models.job_execution import JobExecution, ExecutionStatus
from app.models.retry_policy import RetryPolicy
from app.models.worker import Worker, WorkerStatus
from app.models.organization import Organization
from app.models.user import User
from app.models.project import Project
from app.worker.claim import claim_jobs
from app.worker.executor import _execute_single_job, execute_jobs


# ---------------------------------------------------------------------------
# Helpers — create test fixtures directly via the ORM to avoid HTTP round-trips.
# Each test function gets its own org/project/queue/worker to avoid cross-test
# interference (the test DB is shared within the session, per conftest.py).
# ---------------------------------------------------------------------------

async def _create_test_infra(
    session: AsyncSession,
    *,
    concurrency_limit: int = 10,
    queue_status: QueueStatus = QueueStatus.ACTIVE,
    with_retry_policy: bool = False,
    max_retries: int = 3,
    backoff_strategy: str = "fixed",
    backoff_base_seconds: float = 1.0,
):
    """Create an org → project → queue (+ optional retry policy) for testing."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    org = Organization(name=f"TestOrg-{suffix}", created_at=now, updated_at=now)
    session.add(org)
    await session.flush()

    project = Project(
        organization_id=org.id, name=f"TestProj-{suffix}",
        created_at=now, updated_at=now,
    )
    session.add(project)
    await session.flush()

    queue = Queue(
        project_id=project.id, name=f"TestQueue-{suffix}",
        concurrency_limit=concurrency_limit, status=queue_status,
    )
    session.add(queue)
    await session.flush()

    retry_policy = None
    if with_retry_policy:
        retry_policy = RetryPolicy(
            queue_id=queue.id,
            max_retries=max_retries,
            backoff_strategy=backoff_strategy,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=3600.0,
        )
        session.add(retry_policy)
        await session.flush()

    return org, project, queue, retry_policy


async def _create_worker(session: AsyncSession) -> Worker:
    """Register a test worker."""
    now = datetime.now(timezone.utc)
    worker = Worker(
        name=f"test-worker-{uuid.uuid4().hex[:8]}",
        status=WorkerStatus.ONLINE,
        started_at=now,
        last_heartbeat_at=now,
    )
    session.add(worker)
    await session.flush()
    return worker


async def _create_jobs(
    session: AsyncSession,
    queue_id: uuid.UUID,
    count: int,
    *,
    status: JobStatus = JobStatus.QUEUED,
    scheduled_at: datetime | None = None,
    depends_on_job_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> list[Job]:
    """Create N jobs in a queue."""
    now = datetime.now(timezone.utc)
    sched = scheduled_at or now
    jobs = []
    for i in range(count):
        job = Job(
            queue_id=queue_id,
            status=status,
            priority=i,  # varied priority for ordering tests
            payload=payload,
            scheduled_at=sched,
            depends_on_job_id=depends_on_job_id,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        jobs.append(job)
    await session.flush()
    return jobs


# ===========================================================================
# TEST 1: Concurrent claim — the most important test in the repo.
#
# Spins up 5 simulated workers calling claim_jobs() concurrently against a
# queue with 10 jobs and concurrency_limit=3. Uses REAL concurrent DB
# sessions/connections, not sequential calls.
#
# Asserts:
#   (a) No job is claimed by more than one worker
#   (b) Total jobs claimed across all workers in the first round == 3
#       (the concurrency limit), verifying the limit is respected DURING
#       contention, not just after settlement
#   (c) The concurrency_limit is never exceeded (no brief over-claim)
# ===========================================================================

@pytest.mark.asyncio
async def test_concurrent_claim_no_double_assignment():
    # Setup: create queue with concurrency_limit=3 and 10 jobs
    async with async_session_factory() as setup_session:
        _, _, queue, _ = await _create_test_infra(
            setup_session, concurrency_limit=3,
        )
        await _create_jobs(setup_session, queue.id, 10)
        queue_id = queue.id
        await setup_session.commit()

    # Create 5 workers
    worker_ids = []
    async with async_session_factory() as session:
        for _ in range(5):
            w = await _create_worker(session)
            worker_ids.append(w.id)
        await session.commit()

    # Concurrent claim: each worker calls claim_jobs() with its OWN session.
    # This is the real test — 5 connections hitting FOR UPDATE SKIP LOCKED.
    async def worker_claim(worker_id: uuid.UUID) -> list[uuid.UUID]:
        async with async_session_factory() as session:
            claimed = await claim_jobs(session, worker_id, queue_id, limit=10)
            await session.commit()
            return [(job.id, worker_id) for job in claimed]

    results = await asyncio.gather(*[worker_claim(wid) for wid in worker_ids])

    # Flatten: list of (job_id, worker_id) tuples
    all_claims = []
    for worker_result in results:
        all_claims.extend(worker_result)

    # (a) No job claimed by more than one worker
    job_ids_claimed = [job_id for job_id, _ in all_claims]
    assert len(job_ids_claimed) == len(set(job_ids_claimed)), \
        f"DUPLICATE CLAIM DETECTED: {[jid for jid, cnt in Counter(job_ids_claimed).items() if cnt > 1]}"

    # (b) Total claimed in this round == concurrency_limit (3), not more.
    # This verifies the limit was respected DURING contention, not just
    # eventually. The atomic transaction ensures available_slots is computed
    # correctly even when 5 workers race.
    assert len(all_claims) == 3, \
        f"Expected exactly 3 claims (concurrency_limit=3), got {len(all_claims)}"

    # (c) Verify in the DB: at most 3 jobs in claimed/running status right now.
    async with async_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT COUNT(*) FROM jobs
                WHERE queue_id = :queue_id
                  AND status IN ('claimed', 'running')
            """),
            {"queue_id": queue_id},
        )
        active_count = result.scalar_one()
        assert active_count <= 3, \
            f"Concurrency limit violated: {active_count} jobs active, limit is 3"


# ===========================================================================
# TEST 2: Paused queue yields no claims
# ===========================================================================

@pytest.mark.asyncio
async def test_paused_queue_yields_no_claims():
    async with async_session_factory() as session:
        _, _, queue, _ = await _create_test_infra(
            session, concurrency_limit=10, queue_status=QueueStatus.PAUSED,
        )
        await _create_jobs(session, queue.id, 5)
        worker = await _create_worker(session)
        await session.commit()

        claimed = await claim_jobs(session, worker.id, queue.id)
        assert claimed == [], f"Paused queue should yield no claims, got {len(claimed)}"


# ===========================================================================
# TEST 3: Dependency blocks claim until dependency is completed
# ===========================================================================

@pytest.mark.asyncio
async def test_dependency_blocks_claim():
    async with async_session_factory() as session:
        _, _, queue, _ = await _create_test_infra(session, concurrency_limit=10)
        worker = await _create_worker(session)

        # Create dependency job (Job A)
        now = datetime.now(timezone.utc)
        job_a = Job(
            queue_id=queue.id, status=JobStatus.QUEUED, priority=0,
            scheduled_at=now, created_at=now, updated_at=now,
        )
        session.add(job_a)
        await session.flush()

        # Create dependent job (Job B depends on Job A)
        job_b = Job(
            queue_id=queue.id, status=JobStatus.QUEUED, priority=10,
            scheduled_at=now, depends_on_job_id=job_a.id,
            created_at=now, updated_at=now,
        )
        session.add(job_b)
        await session.commit()

        # Claim: should get Job A but NOT Job B (dependency not completed)
        claimed = await claim_jobs(session, worker.id, queue.id)
        await session.commit()
        claimed_ids = {j.id for j in claimed}
        assert job_a.id in claimed_ids, "Job A should be claimable"
        assert job_b.id not in claimed_ids, "Job B should NOT be claimable (dep not met)"

    # Now complete Job A and try again
    async with async_session_factory() as session:
        result = await session.execute(select(Job).where(Job.id == job_a.id))
        a = result.scalar_one()
        a.status = JobStatus.COMPLETED
        a.updated_at = datetime.now(timezone.utc)

        # Clear claimed state on B so the claim query picks it up
        result_b = await session.execute(select(Job).where(Job.id == job_b.id))
        b = result_b.scalar_one()
        # B is still queued, just has a dependency
        await session.commit()

    async with async_session_factory() as session:
        # Create a new worker for the second claim
        worker2 = await _create_worker(session)
        await session.commit()

        claimed2 = await claim_jobs(session, worker2.id, queue.id)
        await session.commit()
        claimed_ids2 = {j.id for j in claimed2}
        assert job_b.id in claimed_ids2, \
            "Job B should now be claimable after Job A completed"


# ===========================================================================
# TEST 4: Retry increments attempt_count, reschedules, and job becomes
#         re-claimable after scheduled_at passes.
# ===========================================================================

@pytest.mark.asyncio
async def test_retry_increments_and_reschedules():
    # Setup: queue with retry policy (fixed, 1s delay, max 3 retries)
    async with async_session_factory() as session:
        _, _, queue, retry_policy = await _create_test_infra(
            session, concurrency_limit=10,
            with_retry_policy=True, max_retries=3,
            backoff_strategy="fixed", backoff_base_seconds=1.0,
        )
        worker = await _create_worker(session)
        now = datetime.now(timezone.utc)

        # Create a job that will fail
        job = Job(
            queue_id=queue.id, status=JobStatus.QUEUED, priority=0,
            payload={"simulate": "fail", "error": "test failure"},
            scheduled_at=now, created_at=now, updated_at=now,
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        queue_id = queue.id
        worker_id = worker.id

    # Claim the job
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 1

    # Execute (will fail and trigger retry)
    await _execute_single_job(job_id, worker_id)

    # Verify: job should be in 'retrying' status with attempt_count=1
    async with async_session_factory() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one()
        assert job.status == JobStatus.RETRYING, f"Expected retrying, got {job.status}"
        assert job.attempt_count == 1
        assert job.scheduled_at > now, "scheduled_at should be pushed forward"
        original_scheduled_at = job.scheduled_at

    # Try to claim it now — should NOT be claimable (scheduled_at is in the future)
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 0, "Job should not be claimable before scheduled_at"

    # Manually move scheduled_at to the past so it becomes claimable again
    async with async_session_factory() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one()
        job.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    # Now claim again — should succeed
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 1, "Job should be claimable after scheduled_at passes"
        assert claimed[0].id == job_id


# ===========================================================================
# TEST 5: Exhausted retries → status=failed (not dead_letter — that's 4B)
# ===========================================================================

@pytest.mark.asyncio
async def test_exhausted_retries_sets_failed():
    async with async_session_factory() as session:
        _, _, queue, _ = await _create_test_infra(
            session, concurrency_limit=10,
            with_retry_policy=True, max_retries=2,
            backoff_strategy="fixed", backoff_base_seconds=0.1,
        )
        worker = await _create_worker(session)
        now = datetime.now(timezone.utc)

        job = Job(
            queue_id=queue.id, status=JobStatus.QUEUED, priority=0,
            payload={"simulate": "fail", "error": "always fails"},
            scheduled_at=now, created_at=now, updated_at=now,
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        queue_id = queue.id
        worker_id = worker.id

    # Attempt 1: claim + execute (fail → retrying, attempt_count=1)
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
    await _execute_single_job(job_id, worker_id)

    async with async_session_factory() as session:
        r = await session.execute(select(Job).where(Job.id == job_id))
        j = r.scalar_one()
        assert j.status == JobStatus.RETRYING
        assert j.attempt_count == 1
        # Move scheduled_at back so it's claimable
        j.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    # Attempt 2: claim + execute (fail → retrying, attempt_count=2)
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 1
    await _execute_single_job(job_id, worker_id)

    async with async_session_factory() as session:
        r = await session.execute(select(Job).where(Job.id == job_id))
        j = r.scalar_one()
        # max_retries=2, attempt_count=2 → exhausted → failed
        assert j.status == JobStatus.FAILED, \
            f"Expected failed after exhausting retries, got {j.status}"
        assert j.attempt_count == 2

    # Verify it's no longer claimable
    async with async_session_factory() as session:
        # Move scheduled_at back just to be sure
        r = await session.execute(select(Job).where(Job.id == job_id))
        j = r.scalar_one()
        j.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 0, "Failed job should never be re-claimable"


# ===========================================================================
# TEST 6: Successful execution records JobExecution with correct data
# ===========================================================================

@pytest.mark.asyncio
async def test_successful_execution_records_job_execution():
    async with async_session_factory() as session:
        _, _, queue, _ = await _create_test_infra(session, concurrency_limit=10)
        worker = await _create_worker(session)
        now = datetime.now(timezone.utc)

        job = Job(
            queue_id=queue.id, status=JobStatus.QUEUED, priority=0,
            payload={"simulate": "success"},
            scheduled_at=now, created_at=now, updated_at=now,
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        queue_id = queue.id
        worker_id = worker.id

    # Claim
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        assert len(claimed) == 1

    # Execute
    await _execute_single_job(job_id, worker_id)

    # Verify final state
    async with async_session_factory() as session:
        r = await session.execute(select(Job).where(Job.id == job_id))
        job = r.scalar_one()
        assert job.status == JobStatus.COMPLETED
        assert job.attempt_count == 1

        # Verify JobExecution record
        er = await session.execute(
            select(JobExecution).where(JobExecution.job_id == job_id)
        )
        execution = er.scalar_one()
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.attempt_number == 1
        assert execution.started_at is not None
        assert execution.finished_at is not None
        assert execution.finished_at >= execution.started_at
        assert execution.worker_id == worker_id
        assert execution.result == {"status": "completed"}
