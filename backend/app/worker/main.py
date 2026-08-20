"""
Worker process entry point — standalone process that polls queues and executes jobs.

Lifecycle:
  1. Register self in `workers` table (status='online', started_at=now)
  2. Poll loop: for each active queue, call claim_jobs(), then execute_jobs()
  3. Sleep for POLL_INTERVAL_SECONDS between cycles

Phase 4A scope: no heartbeats, no reaper, no graceful shutdown (those are 4B).
"""
import asyncio
import logging
import platform
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.queue import Queue, QueueStatus
from app.models.worker import Worker, WorkerStatus
from app.worker.claim import claim_jobs
from app.worker.executor import execute_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("worker.main")

# How often the worker polls for new jobs (seconds).
POLL_INTERVAL_SECONDS = 2


async def register_worker() -> uuid.UUID:
    """Register this worker in the workers table and return its ID."""
    worker_name = f"worker-{platform.node()}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    async with async_session_factory() as session:
        worker = Worker(
            name=worker_name,
            status=WorkerStatus.ONLINE,
            started_at=now,
            last_heartbeat_at=now,
        )
        session.add(worker)
        await session.commit()
        worker_id = worker.id

    logger.info(f"Worker registered: {worker_name} (id={worker_id})")
    return worker_id


async def poll_and_execute(worker_id: uuid.UUID) -> int:
    """
    One poll cycle: iterate over active queues, claim and execute jobs.

    Returns the total number of jobs claimed+dispatched in this cycle.
    """
    total_claimed = 0

    # Fetch active queue IDs
    async with async_session_factory() as session:
        result = await session.execute(
            select(Queue.id).where(Queue.status == QueueStatus.ACTIVE)
        )
        queue_ids = [row[0] for row in result.fetchall()]

    for queue_id in queue_ids:
        # Each claim uses its own session+transaction for isolation.
        async with async_session_factory() as session:
            try:
                claimed = await claim_jobs(session, worker_id, queue_id)
                await session.commit()

                if claimed:
                    logger.info(
                        f"Claimed {len(claimed)} jobs from queue {queue_id}",
                        extra={"worker_id": str(worker_id), "queue_id": str(queue_id)},
                    )
                    total_claimed += len(claimed)
                    # Execute concurrently — each job gets its own session (see executor.py)
                    await execute_jobs(claimed, worker_id)
            except Exception:
                await session.rollback()
                logger.exception(f"Error during claim/execute for queue {queue_id}")

    return total_claimed


async def main_loop():
    """Main worker loop: register, then poll forever."""
    worker_id = await register_worker()

    logger.info(f"Worker {worker_id} entering poll loop (interval={POLL_INTERVAL_SECONDS}s)")
    while True:
        try:
            claimed = await poll_and_execute(worker_id)
            if claimed > 0:
                logger.info(f"Poll cycle completed: {claimed} jobs dispatched")
        except Exception:
            logger.exception("Unexpected error in poll cycle")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main_loop())
