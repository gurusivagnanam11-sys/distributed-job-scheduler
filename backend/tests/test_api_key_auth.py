"""
test_api_key_auth.py — Verifies API key authentication for job-submission endpoints.

Covered cases:
  1. Valid API key successfully submits a job.
  2. Revoked API key is rejected (401).
  3. Invalid/nonexistent key is rejected (401).
  4. API key for Project A cannot submit to a queue under Project B (same org — 403).
  5. JWT still works unchanged on the same endpoint (regression check).
  6. A request with neither JWT nor API key is rejected (401).

Header convention: X-API-Key (not Authorization: Bearer).
Documented in docs/DESIGN_DECISIONS.md §6.
"""
import pytest
import pytest_asyncio


@pytest_asyncio.fixture()
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: bootstrap a full user → org → project → queue → api_key chain
# ---------------------------------------------------------------------------

async def _bootstrap(client, email: str, project_name: str = "ProjA") -> dict:
    """Sign up, create a project, create a queue, and create one API key.

    Returns a dict with:
        jwt_headers       – Authorization: Bearer <token>
        project_id        – UUID str
        queue_id          – UUID str
        raw_api_key       – the one-time raw key value
        api_key_id        – UUID str (for revocation tests)
    """
    res = await client.post("/auth/signup", json={
        "email": email,
        "password": "password123",
        "organization_name": f"Org_{email}",
    })
    assert res.status_code == 201, res.text
    token = res.json()["token"]["access_token"]
    jwt_headers = {"Authorization": f"Bearer {token}"}

    # Project
    res = await client.post("/projects", json={"name": project_name}, headers=jwt_headers)
    assert res.status_code == 201, res.text
    project_id = res.json()["id"]

    # Queue
    res = await client.post(f"/projects/{project_id}/queues", json={"name": "Q"}, headers=jwt_headers)
    assert res.status_code == 201, res.text
    queue_id = res.json()["id"]

    # API key
    res = await client.post(f"/projects/{project_id}/api-keys", json={"label": "test-key"}, headers=jwt_headers)
    assert res.status_code == 201, res.text
    raw_api_key = res.json()["raw_key"]
    api_key_id = res.json()["id"]

    return {
        "jwt_headers": jwt_headers,
        "project_id": project_id,
        "queue_id": queue_id,
        "raw_api_key": raw_api_key,
        "api_key_id": api_key_id,
    }


# ---------------------------------------------------------------------------
# Test 1: Valid API key successfully submits a job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_api_key_submits_job(client):
    ctx = await _bootstrap(client, "apikey_valid@test.com")
    queue_id = ctx["queue_id"]
    raw_key = ctx["raw_api_key"]

    res = await client.post(
        f"/queues/{queue_id}/jobs",
        json={"payload": {"source": "api_key_test"}},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["status"] == "queued"
    assert data["queue_id"] == queue_id


# ---------------------------------------------------------------------------
# Test 2: Revoked API key is rejected (401)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_revoked_api_key_rejected(client):
    ctx = await _bootstrap(client, "apikey_revoke@test.com")
    queue_id = ctx["queue_id"]
    raw_key = ctx["raw_api_key"]
    project_id = ctx["project_id"]
    api_key_id = ctx["api_key_id"]
    jwt_headers = ctx["jwt_headers"]

    # Revoke the key
    rev = await client.delete(f"/projects/{project_id}/api-keys/{api_key_id}", headers=jwt_headers)
    assert rev.status_code == 204, rev.text

    # Now try to use the revoked key
    res = await client.post(
        f"/queues/{queue_id}/jobs",
        json={"payload": {"source": "revoked_key"}},
        headers={"X-API-Key": raw_key},
    )
    assert res.status_code == 401, f"Expected 401 for revoked key, got {res.status_code}: {res.text}"


# ---------------------------------------------------------------------------
# Test 3: Invalid / nonexistent key is rejected (401)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client):
    ctx = await _bootstrap(client, "apikey_invalid@test.com")
    queue_id = ctx["queue_id"]

    fake_key = "jsk_0000000000000000000000000000000000000000000000000000000000000000000000"

    res = await client.post(
        f"/queues/{queue_id}/jobs",
        json={"payload": {}},
        headers={"X-API-Key": fake_key},
    )
    assert res.status_code == 401, f"Expected 401 for invalid key, got {res.status_code}: {res.text}"


# ---------------------------------------------------------------------------
# Test 4: API key for Project A cannot submit to a queue under Project B
#         (same org — API keys are PROJECT-scoped, stricter than JWT)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_key_cross_project_rejected(client):
    """Key from Project A must not be usable against Project B's queue,
    even though both projects live in the same organization."""
    # Set up org with two projects
    res = await client.post("/auth/signup", json={
        "email": "apikey_xproj@test.com",
        "password": "password123",
        "organization_name": "Org_apikey_xproj@test.com",
    })
    assert res.status_code == 201
    token = res.json()["token"]["access_token"]
    jwt_headers = {"Authorization": f"Bearer {token}"}

    # Project A + queue A
    res = await client.post("/projects", json={"name": "ProjA_xp"}, headers=jwt_headers)
    proj_a_id = res.json()["id"]
    res = await client.post(f"/projects/{proj_a_id}/queues", json={"name": "QA"}, headers=jwt_headers)
    queue_a_id = res.json()["id"]

    # Project B + queue B  (same org, different project)
    res = await client.post("/projects", json={"name": "ProjB_xp"}, headers=jwt_headers)
    proj_b_id = res.json()["id"]
    res = await client.post(f"/projects/{proj_b_id}/queues", json={"name": "QB"}, headers=jwt_headers)
    queue_b_id = res.json()["id"]

    # API key scoped to Project A
    res = await client.post(f"/projects/{proj_a_id}/api-keys", json={"label": "key-a"}, headers=jwt_headers)
    assert res.status_code == 201
    key_a = res.json()["raw_key"]

    # Key A → queue A: should succeed
    res = await client.post(
        f"/queues/{queue_a_id}/jobs",
        json={"payload": {"ok": True}},
        headers={"X-API-Key": key_a},
    )
    assert res.status_code == 201, f"Key A → queue A should succeed: {res.text}"

    # Key A → queue B: must be rejected (403 project scope violation)
    res = await client.post(
        f"/queues/{queue_b_id}/jobs",
        json={"payload": {"ok": True}},
        headers={"X-API-Key": key_a},
    )
    assert res.status_code == 403, (
        f"Key A should be rejected for queue B (different project). Got {res.status_code}: {res.text}"
    )


# ---------------------------------------------------------------------------
# Test 5: JWT still works unchanged on these endpoints (regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jwt_still_works_on_submission_endpoint(client):
    ctx = await _bootstrap(client, "apikey_jwt_regression@test.com")
    queue_id = ctx["queue_id"]
    jwt_headers = ctx["jwt_headers"]

    res = await client.post(
        f"/queues/{queue_id}/jobs",
        json={"payload": {"source": "jwt_regression"}},
        headers=jwt_headers,
    )
    assert res.status_code == 201, f"JWT should still work, got {res.status_code}: {res.text}"
    assert res.json()["status"] == "queued"


# ---------------------------------------------------------------------------
# Test 6: No credentials → 401
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_credentials_rejected(client):
    ctx = await _bootstrap(client, "apikey_nocreds@test.com")
    queue_id = ctx["queue_id"]

    res = await client.post(
        f"/queues/{queue_id}/jobs",
        json={"payload": {}},
        # Neither Authorization nor X-API-Key header
    )
    assert res.status_code == 401, f"Expected 401 with no credentials, got {res.status_code}: {res.text}"
