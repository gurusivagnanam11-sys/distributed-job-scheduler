"""Phase 1 smoke tests: auth, org scoping, project CRUD, API keys.

These tests use httpx.AsyncClient against the FastAPI app with a real
(test) PostgreSQL database. They verify the critical invariant that a
user from org A cannot access org B's projects.
"""
import pytest
import httpx
import asyncio
from app.main import app


BASE_URL = "http://test"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


import pytest_asyncio

@pytest_asyncio.fixture(scope="module")
async def client():
    """Async HTTP client for testing."""
    from httpx import ASGITransport
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url=BASE_URL
    ) as c:
        yield c


# --- Helper ---

async def signup_user(client: httpx.AsyncClient, email: str, org_name: str, password: str = "testpass123"):
    resp = await client.post("/auth/signup", json={
        "email": email,
        "password": password,
        "organization_name": org_name,
    })
    return resp


async def login_user(client: httpx.AsyncClient, email: str, password: str = "testpass123"):
    resp = await client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    return resp


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Tests ---

@pytest.mark.asyncio
async def test_signup_creates_user_and_org(client):
    resp = await signup_user(client, "alice@example.com", "Alice Corp")
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "alice@example.com"
    assert data["token"]["access_token"]
    assert data["token"]["token_type"] == "bearer"
    assert data["token"]["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_returns_token(client):
    resp = await login_user(client, "alice@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_duplicate_signup_fails(client):
    resp = await signup_user(client, "alice@example.com", "Alice Corp 2")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/auth/login", json={
        "email": "alice@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_project_crud_and_org_scoping(client):
    # Login as Alice
    login_a = await login_user(client, "alice@example.com")
    token_a = login_a.json()["access_token"]

    # Create project as Alice
    resp = await client.post(
        "/projects",
        json={"name": "Alice Project", "description": "Test project"},
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 201
    project_a = resp.json()
    project_a_id = project_a["id"]

    # Signup Bob in a different org
    await signup_user(client, "bob@example.com", "Bob Corp")
    login_b = await login_user(client, "bob@example.com")
    token_b = login_b.json()["access_token"]

    # Bob tries to read Alice's project → 404 (not 403, to avoid leaking existence)
    resp = await client.get(
        f"/projects/{project_a_id}",
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 404

    # Bob tries to update Alice's project → 404
    resp = await client.patch(
        f"/projects/{project_a_id}",
        json={"name": "Hacked!"},
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 404

    # Bob tries to delete Alice's project → 404
    resp = await client.delete(
        f"/projects/{project_a_id}",
        headers=auth_headers(token_b),
    )
    assert resp.status_code == 404

    # Alice can still access her own project
    resp = await client.get(
        f"/projects/{project_a_id}",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice Project"


@pytest.mark.asyncio
async def test_project_list_pagination(client):
    login_a = await login_user(client, "alice@example.com")
    token_a = login_a.json()["access_token"]

    resp = await client.get(
        "/projects?page=1&page_size=10",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


@pytest.mark.asyncio
async def test_api_key_lifecycle(client):
    login_a = await login_user(client, "alice@example.com")
    token_a = login_a.json()["access_token"]

    # Get Alice's project
    resp = await client.get("/projects?page=1&page_size=1", headers=auth_headers(token_a))
    project_id = resp.json()["items"][0]["id"]

    # Create API key
    resp = await client.post(
        f"/projects/{project_id}/api-keys",
        json={"label": "Test Key"},
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 201
    key_data = resp.json()
    assert "raw_key" in key_data
    assert key_data["raw_key"].startswith("jsk_")
    assert key_data["label"] == "Test Key"
    key_id = key_data["id"]

    # List API keys — raw_key and key_hash must NOT be present
    resp = await client.get(
        f"/projects/{project_id}/api-keys",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200
    keys = resp.json()["items"]
    assert len(keys) >= 1
    for k in keys:
        assert "raw_key" not in k
        assert "key_hash" not in k
        assert "key_prefix" in k
        assert "label" in k

    # Revoke the key
    resp = await client.delete(
        f"/projects/{project_id}/api-keys/{key_id}",
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 204

    # Verify revoked_at is set
    resp = await client.get(
        f"/projects/{project_id}/api-keys",
        headers=auth_headers(token_a),
    )
    keys = resp.json()["items"]
    revoked_key = [k for k in keys if k["id"] == key_id][0]
    assert revoked_key["revoked_at"] is not None


@pytest.mark.asyncio
async def test_validation_error_shape(client):
    """Invalid signup payload should return structured error, not raw 422 array."""
    resp = await client.post("/auth/signup", json={
        "email": "not-an-email",
        "password": "short",
        "organization_name": "",
    })
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    # Must NOT be the default FastAPI shape
    assert "detail" not in data
