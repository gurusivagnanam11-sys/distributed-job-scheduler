"""
Worker process entry point — standalone process that polls queues and executes jobs.

Lifecycle:
  1. Register self in `workers` table (status='online', started_at=now)
  2. Launch background tasks: heartbeat loop, reaper loop, recurring scheduler loop.
  3. Main poll loop: for each active queue, call claim_jobs(), then execute_jobs()
  4. On SIGTERM/SIGINT: graceful shutdown (stop claiming, wait for in-flight jobs).
"""
import asyncio
import logging
import platform
import signal
import uuid
from datetime import datetime, timezone
from typing import Set

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.queue import Queue, QueueStatus
from app.models.worker import Worker, WorkerStatus
from app.worker.claim import claim_jobs
from app.worker.executor import execute_jobs
from app.worker.heartbeat import send_heartbeat
from app.worker.reaper import reclaim_stale_jobs
from app.worker.recurring_scheduler import schedule_recurring_jobs

from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger("worker.main")

POLL_INTERVAL_SECONDS = 2
shutdown_event = asyncio.Event()


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


async def mark_worker_offline(worker_id: uuid.UUID):
    """Mark the worker as offline during shutdown."""
    async with async_session_factory() as session:
        result = await session.execute(select(Worker).where(Worker.id == worker_id))
        worker = result.scalar_one_or_none()
        if worker:
            worker.status = WorkerStatus.OFFLINE
            worker.last_heartbeat_at = datetime.now(timezone.utc)
            await session.commit()
    logger.info(f"Worker {worker_id} marked offline.")


# --- Loops ---

async def heartbeat_loop(worker_id: uuid.UUID):
    """Periodically write a heartbeat row."""
    interval = settings.HEARTBEAT_INTERVAL_SECONDS
    while not shutdown_event.is_set():
        try:
            await send_heartbeat(worker_id)
        except Exception:
            logger.exception("Error sending heartbeat")
        
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def reaper_loop():
    """Periodically reclaim stale jobs."""
    interval = settings.REAPER_INTERVAL_SECONDS
    while not shutdown_event.is_set():
        try:
            async with async_session_factory() as session:
                reclaimed = await reclaim_stale_jobs(session)
                if reclaimed:
                    await session.commit()
                    logger.info(f"Reaper: reclaimed {len(reclaimed)} stale jobs")
        except Exception:
            logger.exception("Error in reaper loop")
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def recurring_scheduler_loop():
    """Periodically schedule recurring jobs."""
    interval = settings.RECURRING_SCHEDULER_INTERVAL_SECONDS
    while not shutdown_event.is_set():
        try:
            async with async_session_factory() as session:
                created = await schedule_recurring_jobs(session)
                if created > 0:
                    await session.commit()
                    logger.info(f"Recurring Scheduler: created {created} jobs")
        except Exception:
            logger.exception("Error in recurring scheduler loop")
            
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def poll_and_execute(worker_id: uuid.UUID) -> int:
    """
    One poll cycle: iterate over active queues, claim and execute jobs.
    Returns the total number of jobs claimed+dispatched in this cycle.
    """
    total_claimed = 0

    async with async_session_factory() as session:
        result = await session.execute(
            select(Queue.id).where(Queue.status == QueueStatus.ACTIVE)
        )
        queue_ids = [row[0] for row in result.fetchall()]

    for queue_id in queue_ids:
        if shutdown_event.is_set():
            break

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
                    # Create a task for execution so it runs concurrently with further polling
                    task = asyncio.create_task(execute_jobs(claimed, worker_id))
                    background_tasks.add(task)
                    task.add_done_callback(background_tasks.discard)
            except Exception:
                await session.rollback()
                logger.exception(f"Error during claim/execute for queue {queue_id}")

    return total_claimed


background_tasks: Set[asyncio.Task] = set()

async def main_loop():
    """Main worker loop: register, launch background loops, then poll."""
    worker_id = await register_worker()

    loop = asyncio.get_running_loop()
    def signal_handler():
        logger.info("Received shutdown signal. Stopping new claims...")
        shutdown_event.set()

    # In Windows, add_signal_handler is not fully supported, but we'll try for POSIX compatibility
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Fallback for Windows testing if needed (though docker is usually linux)
        pass

    logger.info(f"Worker {worker_id} entering poll loop (interval={POLL_INTERVAL_SECONDS}s)")
    
    # Launch background loops
    hb_task = asyncio.create_task(heartbeat_loop(worker_id))
    reaper_task = asyncio.create_task(reaper_loop())
    sched_task = asyncio.create_task(recurring_scheduler_loop())

    while not shutdown_event.is_set():
        try:
            claimed = await poll_and_execute(worker_id)
            if claimed > 0:
                logger.info(f"Poll cycle completed: {claimed} jobs dispatched")
        except Exception:
            logger.exception("Unexpected error in poll cycle")

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=POLL_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass

    # --- Shutdown Phase ---
    logger.info("Worker shutting down. Waiting for in-flight jobs to complete...")
    
    # Wait for background tasks (heartbeat, reaper, scheduler) to finish their current sleep/work
    await asyncio.gather(hb_task, reaper_task, sched_task, return_exceptions=True)

    # Wait for executing jobs
    if background_tasks:
        logger.info(f"Waiting on {len(background_tasks)} in-flight job tasks...")
        done, pending = await asyncio.wait(
            background_tasks,
            timeout=settings.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS
        )
        if pending:
            logger.warning(f"{len(pending)} tasks did not complete within timeout and will be abandoned (reaper will handle them).")
        else:
            logger.info("All in-flight jobs completed gracefully.")

    await mark_worker_offline(worker_id)
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main_loop())
