"""Authentication endpoint tests.

Covers:
  - Registration (success + duplicate email)
  - Login (success + wrong password)
  - Get current user profile /me (success + no token)
  - Token refresh (success)
  - Logout (success)
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Registering a new user should return 201 with user data."""
    payload = {
        "email": "newuser@example.com",
        "password": "Password123!",
        "first_name": "New",
        "last_name": "User",
        "company_name": "Test Corp",
        "phone": "+994501234567",
    }
    resp = await client.post("/api/v2/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["first_name"] == "New"
    assert data["last_name"] == "User"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Registering with an email that already exists should return 409."""
    payload = {
        "email": "dup@example.com",
        "password": "Password123!",
        "first_name": "Dup",
        "last_name": "User",
    }
    # First registration succeeds
    resp1 = await client.post("/api/v2/auth/register", json=payload)
    assert resp1.status_code == 201

    # Second registration with same email fails
    resp2 = await client.post("/api/v2/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Registering with a weak password should return 422."""
    payload = {
        "email": "weak@example.com",
        "password": "weak",
        "first_name": "Weak",
        "last_name": "User",
    }
    resp = await client.post("/api/v2/auth/register", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Logging in with correct credentials should return 200 and tokens."""
    # Register first
    register_payload = {
        "email": "login@example.com",
        "password": "Password123!",
        "first_name": "Login",
        "last_name": "User",
    }
    r = await client.post("/api/v2/auth/register", json=register_payload)
    assert r.status_code == 201

    # Login
    login_payload = {
        "email": "login@example.com",
        "password": "Password123!",
    }
    resp = await client.post("/api/v2/auth/login", json=login_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert "refresh_expires_in" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Logging in with wrong password should return 401."""
    # Register first
    register_payload = {
        "email": "wrongpass@example.com",
        "password": "Password123!",
        "first_name": "Wrong",
        "last_name": "Pass",
    }
    await client.post("/api/v2/auth/register", json=register_payload)

    # Login with wrong password
    login_payload = {
        "email": "wrongpass@example.com",
        "password": "WrongPassword123!",
    }
    resp = await client.post("/api/v2/auth/login", json=login_payload)
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Logging in with a non-existent user should return 401."""
    login_payload = {
        "email": "nobody@example.com",
        "password": "Password123!",
    }
    resp = await client.post("/api/v2/auth/login", json=login_payload)
    assert resp.status_code == 401
    assert "Invalid" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_me_success(client: AsyncClient, test_user, auth_headers):
    """Fetching /me with a valid token should return 200 and user profile."""
    resp = await client.get("/api/v2/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_user["email"]
    assert data["first_name"] == test_user["first_name"]
    assert data["last_name"] == test_user["last_name"]
    assert data["id"] == test_user["id"]


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    """Fetching /me without a token should return 401."""
    resp = await client.get("/api/v2/auth/me")
    assert resp.status_code == 401
    assert "token" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    """Fetching /me with an invalid token should return 401."""
    headers = {"Authorization": "Bearer invalid-token"}
    resp = await client.get("/api/v2/auth/me", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_revoked_token(client: AsyncClient, test_user, user_tokens):
    """Fetching /me with a revoked token should return 401."""
    # Revoke the access token via the logout endpoint
    headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}
    # Logout to revoke the token
    await client.post("/api/v2/auth/logout", headers=headers)
    # Try to access /me with the revoked token
    resp = await client.get("/api/v2/auth/me", headers=headers)
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient, test_user, user_tokens):
    """Refreshing with a valid refresh token should return 200 and new tokens."""
    headers = {"Authorization": f"Bearer {user_tokens['refresh_token']}"}
    resp = await client.post("/api/v2/auth/refresh", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    # New tokens should be different from old ones
    assert data["access_token"] != user_tokens["access_token"]
    assert data["refresh_token"] != user_tokens["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    """Refreshing with an invalid token should return 401."""
    headers = {"Authorization": "Bearer invalid-token"}
    resp = await client.post("/api/v2/auth/refresh", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_header(client: AsyncClient):
    """Refreshing without Authorization header should return 401."""
    resp = await client.post("/api/v2/auth/refresh")
    assert resp.status_code == 401
    assert "Refresh token required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_with_access_token(client: AsyncClient, test_user, user_tokens):
    """Refreshing with an access token (wrong type) should return 401."""
    # Access token has type "access", not "refresh"
    headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}
    resp = await client.post("/api/v2/auth/refresh", headers=headers)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, test_user, user_tokens):
    """Logout should return 204 and revoke the token."""
    headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}
    resp = await client.post("/api/v2/auth/logout", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_with_refresh_token(client: AsyncClient, test_user, user_tokens):
    """Logout with refresh token in body should return 204."""
    headers = {"Authorization": f"Bearer {user_tokens['access_token']}"}
    payload = {"refresh_token": user_tokens["refresh_token"]}
    resp = await client.post("/api/v2/auth/logout", json=payload, headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_without_auth_header(client: AsyncClient):
    """Logout without Authorization header should still succeed (204)."""
    resp = await client.post("/api/v2/auth/logout")
    assert resp.status_code == 204
