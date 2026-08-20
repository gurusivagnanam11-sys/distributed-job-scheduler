import pytest
import pytest_asyncio

# We reuse test_auth_and_projects logic to sign up a user and create a project
# But it's better to just implement a helper in the test.

@pytest_asyncio.fixture()
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def create_user_and_project(client, email: str, org_name: str, project_name: str):
    # 1. Signup
    res = await client.post("/auth/signup", json={
        "email": email,
        "password": "password123",
        "organization_name": org_name,
    })
    token = res.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Create Project
    res = await client.post("/projects", json={"name": project_name}, headers=headers)
    project_id = res.json()["id"]
    return headers, project_id

@pytest.mark.asyncio
async def test_queue_crud_and_cross_org_isolation(client):
    headers_a, proj_a = await create_user_and_project(client, "a_queue@example.com", "Org A", "Proj A")
    headers_b, proj_b = await create_user_and_project(client, "b_queue@example.com", "Org B", "Proj B")
    
    # User A creates a queue
    res = await client.post(f"/projects/{proj_a}/queues", json={"name": "Queue A"}, headers=headers_a)
    assert res.status_code == 201
    queue_a_id = res.json()["id"]
    
    # User B tries to get User A's queue -> 404
    res = await client.get(f"/queues/{queue_a_id}", headers=headers_b)
    assert res.status_code == 404
    
    # User B tries to patch User A's queue -> 404
    res = await client.patch(f"/queues/{queue_a_id}", json={"name": "Hacked"}, headers=headers_b)
    assert res.status_code == 404

    # User B tries to delete User A's queue -> 404
    res = await client.delete(f"/queues/{queue_a_id}", headers=headers_b)
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_queue_pause_resume(client):
    headers, proj = await create_user_and_project(client, "pause@example.com", "Org P", "Proj P")
    
    # Create queue
    res = await client.post(f"/projects/{proj}/queues", json={"name": "Q1"}, headers=headers)
    q_id = res.json()["id"]
    assert res.json()["status"] == "active"
    
    # Pause
    res = await client.post(f"/queues/{q_id}/pause", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "paused"
    
    # Get to confirm
    res = await client.get(f"/queues/{q_id}", headers=headers)
    assert res.json()["status"] == "paused"
    
    # Resume
    res = await client.post(f"/queues/{q_id}/resume", headers=headers)
    assert res.json()["status"] == "active"

@pytest.mark.asyncio
async def test_retry_policy_duplicate_conflict(client):
    headers, proj = await create_user_and_project(client, "retry@example.com", "Org R", "Proj R")
    
    res = await client.post(f"/projects/{proj}/queues", json={"name": "Q2"}, headers=headers)
    q_id = res.json()["id"]
    
    # Create first policy
    res = await client.post(f"/queues/{q_id}/retry-policy", json={
        "max_retries": 3,
        "backoff_strategy": "linear",
        "backoff_base_seconds": 2.0,
        "backoff_max_seconds": 10.0
    }, headers=headers)
    assert res.status_code == 201
    
    # Try to create second policy
    res = await client.post(f"/queues/{q_id}/retry-policy", json={
        "max_retries": 5,
        "backoff_strategy": "fixed",
        "backoff_base_seconds": 5.0,
        "backoff_max_seconds": 5.0
    }, headers=headers)
    assert res.status_code == 409
    
    # Patch works though
    res = await client.patch(f"/queues/{q_id}/retry-policy", json={"max_retries": 10}, headers=headers)
    assert res.status_code == 200
    assert res.json()["max_retries"] == 10

@pytest.mark.asyncio
async def test_retry_policy_validation(client):
    headers, proj = await create_user_and_project(client, "retry2@example.com", "Org R2", "Proj R2")
    res = await client.post(f"/projects/{proj}/queues", json={"name": "Q3"}, headers=headers)
    q_id = res.json()["id"]

    # Max < Base
    res = await client.post(f"/queues/{q_id}/retry-policy", json={
        "max_retries": 3,
        "backoff_strategy": "linear",
        "backoff_base_seconds": 10.0,
        "backoff_max_seconds": 2.0
    }, headers=headers)
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_queue_stats_empty(client):
    headers, proj = await create_user_and_project(client, "stats@example.com", "Org S", "Proj S")
    res = await client.post(f"/projects/{proj}/queues", json={"name": "Q4"}, headers=headers)
    q_id = res.json()["id"]
    
    res = await client.get(f"/queues/{q_id}/stats", headers=headers)
    assert res.status_code == 200
    stats = res.json()
    assert stats["queued"] == 0
    assert stats["running"] == 0
    assert stats["completed"] == 0
    assert stats["dead_letter"] == 0
