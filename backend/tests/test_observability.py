import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job import Job, JobStatus
from app.models.job_execution import JobExecution, ExecutionStatus
from app.models.job_log import JobLog

from httpx import ASGITransport, AsyncClient
import pytest_asyncio
from app.main import app

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture()
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def create_user_project_queue(client, email: str, db: AsyncSession):
    # Signup
    res = await client.post("/auth/signup", json={
        "email": email,
        "password": "password123",
        "organization_name": f"Org_{email}",
    })
    token = res.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Project
    res = await client.post("/projects", json={"name": "Proj"}, headers=headers)
    project_id = res.json()["id"]
    
    # Queue
    res = await client.post(f"/projects/{project_id}/queues", json={"name": "Q"}, headers=headers)
    queue_id = res.json()["id"]
    
    # Get the Queue object for the ID to return it
    from app.models.queue import Queue
    from app.models.project import Project
    from app.models.organization import Organization
    
    r_q = await db.execute(select(Queue).where(Queue.id == uuid.UUID(queue_id)))
    q = r_q.scalar_one()
    
    r_p = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
    p = r_p.scalar_one()
    
    r_o = await db.execute(select(Organization).where(Organization.id == p.organization_id))
    o = r_o.scalar_one()
    
    return headers, o, p, q

@pytest_asyncio.fixture()
async def default_setup(async_client, setup_test_db):
    from app.core.database import async_session_factory
    async with async_session_factory() as db:
        uid = uuid.uuid4().hex[:8]
        headers, org, proj, queue = await create_user_project_queue(async_client, f"def_{uid}@test.com", db)
        return headers, org, proj, queue

@pytest_asyncio.fixture()
async def other_setup(async_client, setup_test_db):
    from app.core.database import async_session_factory
    async with async_session_factory() as db:
        uid = uuid.uuid4().hex[:8]
        headers, org, proj, queue = await create_user_project_queue(async_client, f"other_{uid}@test.com", db)
        return headers, org, proj, queue

@pytest_asyncio.fixture()
async def db():
    from app.core.database import async_session_factory
    async with async_session_factory() as session:
        yield session

from app.models.worker import Worker, WorkerStatus

async def create_completed_job_with_execution(
    db: AsyncSession, queue_id: uuid.UUID, duration: int = 2
) -> Job:
    """Helper to create a completed job with an execution and logs."""
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1)
    finished = started + timedelta(seconds=duration)
    
    # 0. Worker
    worker = Worker(
        name=f"test-worker-{uuid.uuid4().hex[:8]}",
        status=WorkerStatus.ONLINE,
        started_at=started - timedelta(hours=1),
        last_heartbeat_at=finished
    )
    db.add(worker)
    await db.flush()
    
    # 1. Job
    job = Job(
        queue_id=queue_id,
        status=JobStatus.COMPLETED,
        priority=0,
        attempt_count=1,
        scheduled_at=started - timedelta(seconds=5),
        created_at=started - timedelta(seconds=5),
        updated_at=finished,
    )
    db.add(job)
    await db.flush()
    
    # 2. Execution
    execution = JobExecution(
        job_id=job.id,
        worker_id=worker.id,
        attempt_number=1,
        status=ExecutionStatus.COMPLETED,
        started_at=started,
        finished_at=finished,
    )
    db.add(execution)
    await db.flush()
    
    # 3. Logs
    db.add(JobLog(job_id=job.id, execution_id=None, level="INFO", message=f"Job {job.id} claimed by worker {worker.id}", timestamp=started - timedelta(seconds=1)))
    db.add(JobLog(job_id=job.id, execution_id=execution.id, level="INFO", message="Started execution attempt 1", timestamp=started))
    db.add(JobLog(job_id=job.id, execution_id=execution.id, level="INFO", message="Job completed on attempt 1", timestamp=finished))
    
    await db.commit()
    return job

async def create_dlq_job_with_execution(
    db: AsyncSession, queue_id: uuid.UUID
) -> Job:
    """Helper to create a DLQ job with an execution."""
    now = datetime.now(timezone.utc)
    started = now - timedelta(hours=1)
    finished = started + timedelta(seconds=1)
    
    # 0. Worker
    worker = Worker(
        name=f"test-worker-{uuid.uuid4().hex[:8]}",
        status=WorkerStatus.ONLINE,
        started_at=started - timedelta(hours=1),
        last_heartbeat_at=finished
    )
    db.add(worker)
    await db.flush()
    
    # 1. Job
    job = Job(
        queue_id=queue_id,
        status=JobStatus.DEAD_LETTER,
        priority=0,
        attempt_count=1,
        scheduled_at=started - timedelta(seconds=5),
        created_at=started - timedelta(seconds=5),
        updated_at=finished,
    )
    db.add(job)
    await db.flush()
    
    # 2. Execution
    execution = JobExecution(
        job_id=job.id,
        worker_id=worker.id,
        attempt_number=1,
        status=ExecutionStatus.FAILED,
        started_at=started,
        finished_at=finished,
        error="Simulated failure",
    )
    db.add(execution)
    await db.flush()
    
    # 3. Logs
    db.add(JobLog(job_id=job.id, execution_id=execution.id, level="ERROR", message="Execution failed", timestamp=finished))
    
    await db.commit()
    return job

async def test_job_timeline_chronological(async_client: AsyncClient, default_setup, db: AsyncSession):
    auth_headers, org, proj, queue = default_setup
    job = await create_completed_job_with_execution(db, queue.id, 2)
    
    resp = await async_client.get(f"/jobs/{job.id}/timeline", headers=auth_headers)
    assert resp.status_code == 200
    
    data = resp.json()
    events = data["events"]
    assert len(events) == 4 # created, claimed, started, completed (added claimed to helper)
    
    assert events[0]["event_type"] == "created"
    assert events[1]["event_type"] == "claimed"
    assert events[2]["event_type"] == "started"
    assert events[3]["event_type"] == "completed"
    
    t0 = datetime.fromisoformat(events[0]["timestamp"].replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(events[1]["timestamp"].replace("Z", "+00:00"))
    t2 = datetime.fromisoformat(events[2]["timestamp"].replace("Z", "+00:00"))
    assert t0 <= t1 <= t2

async def test_job_timeline_cross_org(async_client: AsyncClient, default_setup, other_setup, db: AsyncSession):
    default_headers, d_org, d_proj, d_queue = default_setup
    other_headers, o_org, o_proj, o_queue = other_setup
    
    job = await create_completed_job_with_execution(db, d_queue.id, 2)
    
    resp = await async_client.get(f"/jobs/{job.id}/timeline", headers=other_headers)
    assert resp.status_code == 404

async def test_job_executions_pagination(async_client: AsyncClient, default_setup, db: AsyncSession):
    auth_headers, org, proj, queue = default_setup
    job = await create_completed_job_with_execution(db, queue.id, 2)
    
    resp = await async_client.get(f"/jobs/{job.id}/executions?page=1&page_size=1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == ExecutionStatus.COMPLETED.value
    assert data["items"][0]["duration_seconds"] == 2.0

async def test_queue_metrics_aggregation(async_client: AsyncClient, default_setup, db: AsyncSession):
    auth_headers, org, proj, queue = default_setup
    await create_completed_job_with_execution(db, queue.id, 2)
    await create_completed_job_with_execution(db, queue.id, 3)
    await create_completed_job_with_execution(db, queue.id, 4)
    await create_dlq_job_with_execution(db, queue.id)
    
    resp = await async_client.get(f"/queues/{queue.id}/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["counts"]["completed"] == 3
    assert data["counts"]["dead_letter"] == 1
    
    assert data["throughput_24h"] == 3
    assert data["success_rate_24h"] == 0.75
    assert data["avg_execution_duration_seconds_24h"] == 3.0

async def test_queue_metrics_isolation(async_client: AsyncClient, default_setup, db: AsyncSession):
    auth_headers, org, proj, queue = default_setup
    
    from app.models.queue import Queue, QueueStatus
    queue_b = Queue(
        project_id=proj.id,
        name="queue-b",
        concurrency_limit=10,
        status=QueueStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(queue_b)
    await db.commit()
    
    await create_completed_job_with_execution(db, queue_b.id, 10)
    await create_dlq_job_with_execution(db, queue_b.id)
    
    resp_a = await async_client.get(f"/queues/{queue.id}/metrics", headers=auth_headers)
    assert resp_a.status_code == 200
    
    resp_b = await async_client.get(f"/queues/{queue_b.id}/metrics", headers=auth_headers)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    
    assert data_b["counts"]["completed"] == 1
    assert data_b["counts"]["dead_letter"] == 1
    assert data_b["success_rate_24h"] == 0.5
    assert data_b["avg_execution_duration_seconds_24h"] == 10.0

@pytest.mark.asyncio
async def test_print_timeline_and_metrics_json(async_client: AsyncClient, default_setup, db: AsyncSession):
    import json
    from app.worker.claim import claim_jobs
    from app.worker.executor import _execute_single_job
    from app.models.worker import Worker, WorkerStatus
    
    auth_headers, org, proj, queue = default_setup
    queue_id = queue.id
    
    # Enable retry policy to allow a job to fail -> retrying -> claim again -> complete
    from app.models.retry_policy import RetryPolicy
    rp = RetryPolicy(
        queue_id=queue_id,
        max_retries=2,
        backoff_strategy="fixed",
        backoff_base_seconds=0
    )
    db.add(rp)
    
    # 0. Worker
    worker = Worker(
        name=f"test-worker-full",
        status=WorkerStatus.ONLINE,
        started_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc)
    )
    db.add(worker)
    
    # 1. Create a single job
    now = datetime.now(timezone.utc)
    job = Job(
        queue_id=queue_id,
        status=JobStatus.QUEUED,
        priority=0,
        payload={"simulate": "fail", "error": "first attempt fails"},
        scheduled_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    job_id = job.id
    worker_id = worker.id

    # -- ATTEMPT 1 --
    # Claim
    from app.core.database import async_session_factory
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        
    # Execute (fails -> retrying)
    await _execute_single_job(job_id, worker_id)
    
    # Move scheduled_at back so it's claimable again
    async with async_session_factory() as session:
        r = await session.execute(select(Job).where(Job.id == job_id))
        j = r.scalar_one()
        j.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        j.payload = {"simulate": "success"} # second attempt succeeds
        await session.commit()

    # -- ATTEMPT 2 --
    async with async_session_factory() as session:
        claimed = await claim_jobs(session, worker_id, queue_id)
        await session.commit()
        
    # Execute (succeeds -> completed)
    await _execute_single_job(job_id, worker_id)

    # 2. Fetch timeline JSON
    resp_timeline = await async_client.get(f"/jobs/{job_id}/timeline", headers=auth_headers)
    assert resp_timeline.status_code == 200
    timeline_json = json.dumps(resp_timeline.json(), indent=2)
    print("\n\n=== TIMELINE JSON ===")
    print(timeline_json)
    print("=====================\n\n")

    # 3. Fetch metrics JSON
    resp_metrics = await async_client.get(f"/queues/{queue_id}/metrics", headers=auth_headers)
    assert resp_metrics.status_code == 200
    metrics_json = json.dumps(resp_metrics.json(), indent=2)
    print("\n\n=== METRICS JSON ===")
    print(metrics_json)
    print("=====================\n\n")
