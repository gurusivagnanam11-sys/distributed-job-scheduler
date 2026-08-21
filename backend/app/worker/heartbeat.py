"""
Worker heartbeat — writes a WorkerHeartbeat row and updates Worker.last_heartbeat_at
in the same transaction (per Phase 0 design decision).

Runs as its own async loop inside the worker process, not blocking job execution.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.worker import Worker
from app.models.worker_heartbeat import WorkerHeartbeat

logger = logging.getLogger("worker.heartbeat")


async def send_heartbeat(worker_id: uuid.UUID) -> None:
    """
    Write a heartbeat row and update Worker.last_heartbeat_at in the same transaction.

    This is a testable standalone function — the loop wrapper calls it on interval.
    """
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        # Update Worker.last_heartbeat_at
        result = await session.execute(
            select(Worker).where(Worker.id == worker_id)
        )
        worker = result.scalar_one_or_none()
        if worker is None:
            logger.error(f"Worker {worker_id} not found for heartbeat")
            return

        worker.last_heartbeat_at = now

        # Insert WorkerHeartbeat row
        hb = WorkerHeartbeat(
            worker_id=worker_id,
            timestamp=now,
        )
        session.add(hb)
        await session.commit()

    logger.debug(
        f"Heartbeat sent for worker {worker_id}",
        extra={"worker_id": str(worker_id)},
    )
