from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.worker import Worker, WorkerStatus
from app.schemas.worker import WorkerListResponse

router = APIRouter(prefix="/workers", tags=["workers"])

@router.get("", response_model=WorkerListResponse)
async def list_workers(
    status: Optional[WorkerStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all workers (platform-wide).
    """
    base_query = select(Worker)
    if status:
        base_query = base_query.where(Worker.status == status)
        
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Worker.last_heartbeat_at.desc().nulls_last(), Worker.created_at.desc())
        .offset(offset).limit(page_size)
    )
    items = result.scalars().all()
    
    return WorkerListResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size
    )
