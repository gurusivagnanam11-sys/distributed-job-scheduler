"""
Observability service for managing JobLog writes and structured logging.
"""
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_log import JobLog

# Use a generic worker logger since this handles events from multiple modules
logger = logging.getLogger("worker")

async def log_job_event(
    session: AsyncSession,
    job_id: uuid.UUID,
    execution_id: Optional[uuid.UUID],
    level: str,
    message: str,
    **extra_fields,
):
    """
    Log an event to both the database (JobLog) and the structured logger.

    Args:
        session: DB Session to add the JobLog to.
        job_id: The job this log belongs to.
        execution_id: The execution attempt this log belongs to (if any).
        level: Log level ("INFO", "WARNING", "ERROR", etc).
        message: The log message.
        extra_fields: Additional fields for structured logging (e.g., worker_id, queue_id, attempt).
    """
    now = datetime.now(timezone.utc)
    
    # 1. Write to DB
    job_log = JobLog(
        job_id=job_id,
        execution_id=execution_id,
        level=level.upper(),
        message=message,
        timestamp=now,
    )
    session.add(job_log)
    
    # 2. Emit structured log
    log_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    
    log_extras = {
        "job_id": str(job_id),
        **extra_fields
    }
    
    if execution_id:
        log_extras["execution_id"] = str(execution_id)
        
    logger.log(log_level, message, extra=log_extras)
