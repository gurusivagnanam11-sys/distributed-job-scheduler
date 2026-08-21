import asyncio
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from app.models.job import JobStatus

@pytest_asyncio.fixture()
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def create_user_project_queue(client, email: str):
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
    
    return headers, queue_id


@pytest.mark.asyncio
async def test_job_submission_types(client):
    headers, q_id = await create_user_project_queue(client, "jobs1@test.com")
    
    # 1. Immediate
    res = await client.post(f"/queues/{q_id}/jobs", json={"payload": {"type": "immediate"}}, headers=headers)
    assert res.status_code == 201
    assert res.json()["status"] == JobStatus.QUEUED
    
    # 2. Delayed
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    res = await client.post(f"/queues/{q_id}/jobs", json={"scheduled_at": future}, headers=headers)
    assert res.status_code == 201
    assert res.json()["status"] == JobStatus.SCHEDULED
    
    # 3. Recurring
    res = await client.post(f"/queues/{q_id}/jobs", json={"cron_expression": "*/5 * * * *"}, headers=headers)
    assert res.status_code == 201
    assert "cron_expression" in res.json()
    assert res.json()["is_active"] is True
    
    # 4. Batch
    res = await client.post(f"/queues/{q_id}/jobs", json={
        "batch": [
            {"payload": {"n": 1}},
            {"payload": {"n": 2}, "scheduled_at": future},
        ]
    }, headers=headers)
    assert res.status_code == 201
    batch_res = res.json()
    assert len(batch_res) == 2
    assert batch_res[0]["batch_id"] == batch_res[1]["batch_id"]
    assert batch_res[0]["status"] == JobStatus.QUEUED
    assert batch_res[1]["status"] == JobStatus.SCHEDULED


@pytest.mark.asyncio
async def test_dedupe_behavior(client):
    headers, q_id = await create_user_project_queue(client, "dedupe@test.com")
    
    # 1. Create first job with dedupe key
    res1 = await client.post(f"/queues/{q_id}/jobs", json={"dedupe_key": "sync_123"}, headers=headers)
    assert res1.status_code == 201
    job_id = res1.json()["id"]
    
    # 2. Submit same dedupe key -> should return 200 and SAME job_id
    res2 = await client.post(f"/queues/{q_id}/jobs", json={"dedupe_key": "sync_123"}, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["id"] == job_id


@pytest.mark.asyncio
async def test_cross_org_dependency(client):
    headers_a, q_a = await create_user_project_queue(client, "org_a@test.com")
    headers_b, q_b = await create_user_project_queue(client, "org_b@test.com")
    
    # User A creates a job
    res = await client.post(f"/queues/{q_a}/jobs", json={}, headers=headers_a)
    job_a_id = res.json()["id"]
    
    # User B tries to depend on it
    res = await client.post(f"/queues/{q_b}/jobs", json={"depends_on_job_id": job_a_id}, headers=headers_b)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_batch_failure_rolls_back(client):
    headers_a, q_a = await create_user_project_queue(client, "batch_fail@test.com")
    headers_b, q_b = await create_user_project_queue(client, "batch_other@test.com")
    
    res = await client.post(f"/queues/{q_b}/jobs", json={}, headers=headers_b)
    job_b_id = res.json()["id"]
    
    # Submit batch of 3, where #2 has an invalid dependency cross-org
    res = await client.post(f"/queues/{q_a}/jobs", json={
        "batch": [
            {"payload": {"n": 1}},
            {"depends_on_job_id": job_b_id}, # Cross org! Fails validation
            {"payload": {"n": 3}},
        ]
    }, headers=headers_a)
    assert res.status_code == 422
    
    # Verify no jobs created in q_a
    list_res = await client.get(f"/queues/{q_a}/jobs", headers=headers_a)
    assert list_res.json()["total"] == 0


@pytest.mark.asyncio
async def test_cron_validation(client):
    headers, q_id = await create_user_project_queue(client, "cron@test.com")
    
    res = await client.post(f"/queues/{q_id}/jobs", json={"cron_expression": "invalid string"}, headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_pagination_and_filtering(client):
    headers, q_id = await create_user_project_queue(client, "filter@test.com")
    
    # Create 3 jobs
    res1 = await client.post(f"/queues/{q_id}/jobs", json={"payload": {"n": 1}}, headers=headers)
    res2 = await client.post(f"/queues/{q_id}/jobs", json={"payload": {"n": 2}}, headers=headers)
    res3 = await client.post(f"/queues/{q_id}/jobs", json={"payload": {"n": 3}}, headers=headers)
    
    res = await client.get(f"/queues/{q_id}/jobs?status=queued&page=1&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_dedupe_race_condition(client):
    headers, q_id = await create_user_project_queue(client, "dedupe_race@test.com")
    
    # Send 5 requests concurrently with the same dedupe_key
    async def submit():
        return await client.post(
            f"/queues/{q_id}/jobs", 
            json={"dedupe_key": "race_123", "priority": 1, "payload": {"k": "v"}}, 
            headers=headers
        )

    results = await asyncio.gather(*[submit() for _ in range(5)])
    
    # They should all succeed (either 201 or 200)
    for res in results:
        assert res.status_code in (201, 200), f"Unexpected status: {res.status_code}, {res.text}"
        
    # Ensure exactly one 201 was returned, and the rest 200
    statuses = [res.status_code for res in results]
    assert statuses.count(201) == 1, f"Expected exactly one 201 Created, got {statuses.count(201)}"
    assert statuses.count(200) == 4, f"Expected exactly four 200 OK, got {statuses.count(200)}"
    
    # They should all return the same job ID
    job_ids = [res.json()["id"] for res in results]
    assert len(set(job_ids)) == 1, "Concurrent dedupe submissions returned different job IDs!"
