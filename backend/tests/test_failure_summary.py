import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.job import Job, JobStatus
from app.models.job_execution import JobExecution, ExecutionStatus
from app.models.worker import Worker, WorkerStatus
from app.main import app

pytestmark = pytest.mark.asyncio

@pytest.fixture()
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def create_user_project_queue(client, email: str, db: AsyncSession):
    res = await client.post("/auth/signup", json={
        "email": email,
        "password": "password123",
        "organization_name": f"Org_{email}",
    })
    token = res.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    res = await client.post("/projects", json={"name": "Proj"}, headers=headers)
    project_id = res.json()["id"]
    
    res = await client.post(f"/projects/{project_id}/queues", json={"name": "Q"}, headers=headers)
    queue_id = res.json()["id"]
    
    from app.models.queue import Queue
    from app.models.project import Project
    from sqlalchemy import select
    
    r_q = await db.execute(select(Queue).where(Queue.id == uuid.UUID(queue_id)))
    q = r_q.scalar_one()
    
    return headers, q

@pytest.fixture()
async def setup_data(async_client, setup_test_db):
    from app.core.database import async_session_factory
    async with async_session_factory() as db:
        uid = uuid.uuid4().hex[:8]
        headers, queue = await create_user_project_queue(async_client, f"test_fail_{uid}@test.com", db)
        return headers, queue

@pytest.fixture()
async def db():
    from app.core.database import async_session_factory
    async with async_session_factory() as session:
        yield session

async def create_failed_job(db: AsyncSession, queue_id: uuid.UUID) -> Job:
    now = datetime.now(timezone.utc)
    
    worker = Worker(
        name=f"test-worker-{uuid.uuid4().hex[:8]}",
        status=WorkerStatus.ONLINE,
        started_at=now,
        last_heartbeat_at=now
    )
    db.add(worker)
    await db.flush()
    
    job = Job(
        queue_id=queue_id,
        status=JobStatus.FAILED,
        priority=0,
        attempt_count=1,
        scheduled_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.flush()
    
    execution = JobExecution(
        job_id=job.id,
        worker_id=worker.id,
        attempt_number=1,
        status=ExecutionStatus.FAILED,
        started_at=now,
        finished_at=now,
        error="ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)",
    )
    db.add(execution)
    await db.commit()
    
    return job

async def create_queued_job(db: AsyncSession, queue_id: uuid.UUID) -> Job:
    now = datetime.now(timezone.utc)
    job = Job(
        queue_id=queue_id,
        status=JobStatus.QUEUED,
        priority=0,
        attempt_count=0,
        scheduled_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    return job

@patch("google.generativeai.GenerativeModel")
@patch("app.routers.jobs.settings")
async def test_failure_summary_success(mock_settings, mock_genai_model_class, async_client: AsyncClient, setup_data, db: AsyncSession):
    headers, queue = setup_data
    job = await create_failed_job(db, queue.id)
    
    mock_settings.GEMINI_API_KEY = "test-key"
    
    # Mock Gemini response
    mock_response = MagicMock()
    mock_response.text = "The connection to the database failed. Ensure the database is running."
    
    mock_model_instance = AsyncMock()
    mock_model_instance.generate_content_async.return_value = mock_response
    mock_genai_model_class.return_value = mock_model_instance
    
    # First call (generates summary)
    res = await async_client.get(f"/jobs/{job.id}/failure-summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"] == "The connection to the database failed. Ensure the database is running."
    assert data["cached"] is False
    assert mock_model_instance.generate_content_async.call_count == 1
    
    # Second call (uses cache)
    res2 = await async_client.get(f"/jobs/{job.id}/failure-summary", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["summary"] == "The connection to the database failed. Ensure the database is running."
    assert data2["cached"] is True
    assert mock_model_instance.generate_content_async.call_count == 1  # Should not increase

async def test_failure_summary_no_failed_executions(async_client: AsyncClient, setup_data, db: AsyncSession):
    headers, queue = setup_data
    job = await create_queued_job(db, queue.id)
    
    res = await async_client.get(f"/jobs/{job.id}/failure-summary", headers=headers)
    assert res.status_code == 404
    assert res.json()["error"]["message"] == "This job has no failed executions"

@patch("google.generativeai.GenerativeModel")
@patch("app.routers.jobs.settings")
async def test_failure_summary_graceful_degradation(mock_settings, mock_genai_model_class, async_client: AsyncClient, setup_data, db: AsyncSession):
    headers, queue = setup_data
    job = await create_failed_job(db, queue.id)
    
    mock_settings.GEMINI_API_KEY = "test-key"
    
    mock_model_instance = AsyncMock()
    mock_model_instance.generate_content_async.side_effect = Exception("Gemini API Error")
    mock_genai_model_class.return_value = mock_model_instance
    
    res = await async_client.get(f"/jobs/{job.id}/failure-summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["summary"] is None
    assert data["cached"] is False
    assert data["raw_error"] == "ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)"
    assert data["note"] == "AI summarization unavailable"
