import uuid
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.core.database import async_session_factory
from app.models.job import Job, JobStatus
from app.models.dead_letter_entry import DeadLetterEntry
from app.worker.reaper import reclaim_stale_jobs
from tests.test_worker import _create_test_infra

@pytest.mark.asyncio
async def test_reaper_concurrent_no_double_reclaim():
    # Setup: create queue and 5 stale jobs (no retries left, so they go to DLQ)
    async with async_session_factory() as setup_session:
        _, _, queue, _ = await _create_test_infra(setup_session, concurrency_limit=10)
        
        from app.models.worker import Worker
        worker = Worker(id=uuid.uuid4(), name=str(uuid.uuid4()), status="online")
        setup_session.add(worker)
        
        now = datetime.now(timezone.utc)
        for i in range(5):
            job = Job(
                queue_id=queue.id,
                status=JobStatus.CLAIMED,
                priority=0,
                scheduled_at=now,
                claimed_by_worker_id=worker.id,
                lease_expires_at=now - timedelta(minutes=5),  # Definitely expired
                attempt_count=3,
                created_at=now,
                updated_at=now,
            )
            setup_session.add(job)
            
        await setup_session.commit()
        queue_id = queue.id

    # Concurrent reclaim: 3 sessions call reclaim_stale_jobs simultaneously
    async def run_reaper():
        async with async_session_factory() as session:
            reclaimed = await reclaim_stale_jobs(session)
            await session.commit()
            return reclaimed

    results = await asyncio.gather(run_reaper(), run_reaper(), run_reaper())
    
    # Flatten reclaimed jobs
    all_reclaimed = []
    for res in results:
        all_reclaimed.extend(res)
        
    job_ids = [j[0] for j in all_reclaimed]
    
    # Assert each job was reclaimed exactly once
    assert len(job_ids) == 5, f"Expected exactly 5 reclaims, got {len(job_ids)}"
    assert len(job_ids) == len(set(job_ids)), "Duplicate reclaim detected among concurrent reapers!"
    
    # Assert DB state is consistent (exactly 5 DLQ entries)
    async with async_session_factory() as session:
        dlq_result = await session.execute(
            select(func.count()).select_from(DeadLetterEntry).join(Job).where(Job.queue_id == queue_id)
        )
        assert dlq_result.scalar_one() == 5, f"Expected exactly 5 DeadLetterEntry rows, got {dlq_result.scalar_one()}"
