"""Pytest configuration and shared fixtures for the test suite."""

import asyncio
from typing import AsyncGenerator, Dict

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.schemas import UserRegister
from app.auth.service import _mock_users, _revoked_tokens, register_user
from app.auth.utils import create_access_token
from app.companies.router import _mock_companies
from app.main import app
import app.redis_client


# ---------------------------------------------------------------------------
# Event loop policy for async tests
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock store reset
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True)
async def reset_mock_stores():
    """Clear all mock in-memory stores before each test."""
    _mock_users.clear()
    _mock_companies.clear()
    _revoked_tokens.clear()
    yield
    _mock_users.clear()
    _mock_companies.clear()
    _revoked_tokens.clear()


# ---------------------------------------------------------------------------
# Fake Redis client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def redis_client():
    """Provide a fake Redis client for tests."""
    fake_redis = fakeredis.aioredis.FakeRedis()
    # Patch the global redis pool
    original_pool = app.redis_client._redis_pool
    app.redis_client._redis_pool = fake_redis
    yield fake_redis
    # Restore original
    app.redis_client._redis_pool = original_pool
    await fake_redis.flushall()
    await fake_redis.close()


# ---------------------------------------------------------------------------
# Async HTTP client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(redis_client) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for making requests to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Test user factories
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user() -> Dict:
    """Create a test user via the mock auth service."""
    user_data = UserRegister(
        email="test@example.com",
        password="Password123!",
        first_name="Test",
        last_name="User",
    )
    user_response = await register_user(user_data)
    # Return the full user data from mock store
    return _mock_users.get("test@example.com")


@pytest_asyncio.fixture
async def test_user_second() -> Dict:
    """Create a second test user."""
    user_data = UserRegister(
        email="second@example.com",
        password="Password123!",
        first_name="Second",
        last_name="User",
    )
    await register_user(user_data)
    return _mock_users.get("second@example.com")


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def auth_headers(test_user) -> Dict[str, str]:
    """Return authorization headers with a valid Bearer token for the test user."""
    token_payload = {
        "sub": test_user["id"],
        "email": test_user["email"],
        "role": test_user.get("role", "user"),
        "company_id": test_user.get("company_id"),
        "branch_id": test_user.get("branch_id"),
    }
    access_token = create_access_token(token_payload)
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def auth_headers_second(test_user_second) -> Dict[str, str]:
    """Return authorization headers for the second test user."""
    token_payload = {
        "sub": test_user_second["id"],
        "email": test_user_second["email"],
        "role": test_user_second.get("role", "user"),
    }
    access_token = create_access_token(token_payload)
    return {"Authorization": f"Bearer {access_token}"}


# ---------------------------------------------------------------------------
# Tokens fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def user_tokens(test_user) -> Dict[str, str]:
    """Return both access and refresh tokens for the test user."""
    from app.auth.utils import create_access_token, create_refresh_token
    token_payload = {
        "sub": test_user["id"],
        "email": test_user["email"],
        "role": test_user.get("role", "user"),
        "company_id": test_user.get("company_id"),
        "branch_id": test_user.get("branch_id"),
    }
    return {
        "access_token": create_access_token(token_payload),
        "refresh_token": create_refresh_token(token_payload),
    }


# ---------------------------------------------------------------------------
# Company factory
# ---------------------------------------------------------------------------
@pytest.fixture
def company_data() -> Dict:
    """Return a sample company payload for creation tests."""
    return {
        "name": "Test Company",
        "slug": "test-company",
        "description": "A test company for unit tests",
        "website": "https://testcompany.com",
        "phone": "+994501234567",
        "email": "info@testcompany.com",
        "address": "123 Test St, Baku",
        "tax_number": "Tax123456",
        "is_active": True,
    }
