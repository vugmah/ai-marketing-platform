"""Pytest configuration and shared fixtures for the test suite."""

import asyncio
from typing import AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.schemas import UserRegister
from app.auth.service import register_user
from app.auth.utils import create_access_token, create_refresh_token
from app.main import app
from app.database import engine, init_db, Base
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
# DB setup for tests
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_db():
    """Create all tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# In-memory user store for test helpers (email -> user dict)
# ---------------------------------------------------------------------------
_test_user_store: Dict[str, dict] = {}


async def _register_and_store(email: str, password: str = "Password123!",
                               first_name: str = "Test", last_name: str = "User",
                               role: str = "user", company_id: str = None,
                               branch_id: str = None) -> dict:
    """Register a user in the real DB and store a dict copy for tests."""
    user_data = UserRegister(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    try:
        resp = await register_user(user_data)
    except Exception:
        # Already exists - fetch from DB
        from sqlalchemy import select
        from app.auth.models import User
        from app.database import get_db_context
        async with get_db_context() as db:
            result = await db.execute(select(User).where(User.email == email))
            u = result.scalar_one()
            resp = type('obj', (object,), {
                'id': u.id, 'email': u.email, 'first_name': u.first_name,
                'last_name': u.last_name, 'role': u.role,
                'company_id': u.company_id, 'branch_id': u.branch_id,
                'is_active': u.is_active, 'created_at': u.created_at,
            })()
    user_dict = {
        "id": resp.id,
        "email": resp.email,
        "first_name": resp.first_name,
        "last_name": resp.last_name,
        "role": getattr(resp, 'role', role),
        "company_id": getattr(resp, 'company_id', None),
        "branch_id": getattr(resp, 'branch_id', None),
        "is_active": getattr(resp, 'is_active', True),
        "password": password,
    }
    _test_user_store[email] = user_dict
    return user_dict


# ---------------------------------------------------------------------------
# Fake Redis client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def redis_client():
    """Provide a fake Redis client for tests."""
    fake_redis = fakeredis.aioredis.FakeRedis()
    original_pool = app.redis_client._redis_pool
    app.redis_client._redis_pool = fake_redis
    yield fake_redis
    app.redis_client._redis_pool = original_pool
    await fake_redis.flushall()
    await fake_redis.close()


# ---------------------------------------------------------------------------
# Async HTTP client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(redis_client) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for making requests to the FastAPI app."""
    _test_user_store.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    _test_user_store.clear()


# ---------------------------------------------------------------------------
# Tenant header helper
# ---------------------------------------------------------------------------
def _tenant_headers(company_id: str = "test-tenant-123") -> Dict[str, str]:
    """Build headers with X-Company-ID for tenant middleware."""
    return {"X-Company-ID": company_id}


# ---------------------------------------------------------------------------
# Test user factories
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user() -> Dict:
    """Create a test user via the real auth service."""
    return await _register_and_store("test@example.com")


@pytest_asyncio.fixture
async def test_user_second() -> Dict:
    """Create a second test user."""
    return await _register_and_store("second@example.com")


# ---------------------------------------------------------------------------
# Role-based user fixtures
# ---------------------------------------------------------------------------

async def _create_test_user_with_role(
    email: str,
    role: str,
    company_id: str = "test-company-1",
    branch_id: str = "test-branch-1",
) -> Dict:
    """Helper to create a test user with a specific role."""
    user = await _register_and_store(email=email, role=role)
    user["role"] = role
    user["company_id"] = company_id
    user["branch_id"] = branch_id
    _test_user_store[email] = user
    return user


@pytest_asyncio.fixture
async def admin_user() -> Dict:
    """Create a super_admin user fixture."""
    return await _create_test_user_with_role(
        email="admin@example.com",
        role="super_admin",
        company_id=None,
        branch_id=None,
    )


@pytest_asyncio.fixture
async def company_admin_user() -> Dict:
    """Create a company_admin user fixture."""
    return await _create_test_user_with_role(
        email="companyadmin@example.com",
        role="company_admin",
        company_id="company-1",
        branch_id=None,
    )


@pytest_asyncio.fixture
async def branch_manager_user() -> Dict:
    """Create a branch_manager user fixture."""
    return await _create_test_user_with_role(
        email="branchmanager@example.com",
        role="branch_manager",
        company_id="company-1",
        branch_id="branch-1",
    )


@pytest_asyncio.fixture
async def marketer_user() -> Dict:
    """Create a marketing_manager user fixture."""
    return await _create_test_user_with_role(
        email="marketer@example.com",
        role="marketing_manager",
        company_id="company-1",
        branch_id="branch-1",
    )


@pytest_asyncio.fixture
async def analyst_user() -> Dict:
    """Create an analyst user fixture."""
    return await _create_test_user_with_role(
        email="analyst@example.com",
        role="analyst",
        company_id="company-1",
        branch_id="branch-1",
    )


@pytest_asyncio.fixture
async def support_agent_user() -> Dict:
    """Create a support_agent user fixture."""
    return await _create_test_user_with_role(
        email="support@example.com",
        role="support_agent",
        company_id="company-1",
        branch_id="branch-1",
    )


@pytest_asyncio.fixture
async def viewer_user() -> Dict:
    """Create a viewer (regular user) fixture."""
    return await _create_test_user_with_role(
        email="viewer@example.com",
        role="user",
        company_id="company-1",
        branch_id="branch-1",
    )


@pytest_asyncio.fixture
async def regular_user() -> Dict:
    """Create a regular user fixture (alias for viewer)."""
    return await _create_test_user_with_role(
        email="regular@example.com",
        role="user",
        company_id="company-1",
        branch_id="branch-1",
    )


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def auth_headers(test_user) -> Dict[str, str]:
    """Return authorization headers with a valid Bearer token for the test user."""
    token_payload = {
        "sub": str(test_user["id"]),
        "email": test_user["email"],
        "role": test_user.get("role", "user"),
        "company_id": test_user.get("company_id"),
        "branch_id": test_user.get("branch_id"),
    }
    access_token = create_access_token(token_payload)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": str(test_user.get("company_id", "test-tenant-123")),
    }


@pytest_asyncio.fixture
async def auth_headers_second(test_user_second) -> Dict[str, str]:
    """Return authorization headers for the second test user."""
    token_payload = {
        "sub": str(test_user_second["id"]),
        "email": test_user_second["email"],
        "role": test_user_second.get("role", "user"),
    }
    access_token = create_access_token(token_payload)
    return {"Authorization": f"Bearer {access_token}", "X-Company-ID": "test-tenant-456"}


# ---------------------------------------------------------------------------
# Role-based auth headers
# ---------------------------------------------------------------------------

async def _make_auth_headers(user: Dict, company_id: str = "test-tenant-123") -> Dict[str, str]:
    """Build auth headers for a user with tenant header."""
    token_payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user.get("role", "user"),
        "company_id": user.get("company_id"),
        "branch_id": user.get("branch_id"),
    }
    access_token = create_access_token(token_payload)
    cid = user.get("company_id") or company_id
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Company-ID": str(cid),
    }


@pytest_asyncio.fixture
async def admin_headers(admin_user) -> Dict[str, str]:
    """Auth headers for super_admin user."""
    return await _make_auth_headers(admin_user, "admin-tenant")


@pytest_asyncio.fixture
async def company_admin_headers(company_admin_user) -> Dict[str, str]:
    """Auth headers for company_admin user."""
    return await _make_auth_headers(company_admin_user, "company-1")


@pytest_asyncio.fixture
async def branch_manager_headers(branch_manager_user) -> Dict[str, str]:
    """Auth headers for branch_manager user."""
    return await _make_auth_headers(branch_manager_user, "company-1")


@pytest_asyncio.fixture
async def marketer_headers(marketer_user) -> Dict[str, str]:
    """Auth headers for marketing_manager user."""
    return await _make_auth_headers(marketer_user, "company-1")


@pytest_asyncio.fixture
async def analyst_headers(analyst_user) -> Dict[str, str]:
    """Auth headers for analyst user."""
    return await _make_auth_headers(analyst_user, "company-1")


@pytest_asyncio.fixture
async def viewer_headers(viewer_user) -> Dict[str, str]:
    """Auth headers for viewer user."""
    return await _make_auth_headers(viewer_user, "company-1")


@pytest_asyncio.fixture
async def support_headers(support_agent_user) -> Dict[str, str]:
    """Auth headers for support_agent user."""
    return await _make_auth_headers(support_agent_user, "company-1")


# ---------------------------------------------------------------------------
# Tokens fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def user_tokens(test_user) -> Dict[str, str]:
    """Return both access and refresh tokens for the test user."""
    token_payload = {
        "sub": str(test_user["id"]),
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


# ---------------------------------------------------------------------------
# Test company and branch fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_company(client: AsyncClient, company_data: Dict, auth_headers: Dict[str, str]) -> Dict:
    """Create a test company and return it."""
    resp = await client.post("/api/v2/companies/", json=company_data, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def test_branch(client: AsyncClient, auth_headers: Dict[str, str]) -> Dict:
    """Create a test branch and return it."""
    payload = {
        "name": "Test Branch",
        "company_id": "test-company-id",
        "address": "123 Branch St",
        "phone": "+994501111111",
        "email": "branch@test.com",
        "manager_name": "Branch Manager",
        "is_active": True,
    }
    resp = await client.post("/api/v2/branches/", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Mock OpenAI
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_openai(monkeypatch):
    """Monkeypatch OpenAI API calls."""
    async def _mock_chat_completion(*args, **kwargs):
        return {
            "content": "This is a mocked AI response.",
            "model": kwargs.get("model", "gpt-4o-mini"),
            "total_tokens": 150,
            "tokens_input": 50,
            "tokens_output": 100,
            "cost_estimate": 0.00225,
            "latency_ms": 250,
            "finish_reason": "stop",
        }

    async def _mock_suggestions(*args, **kwargs):
        from app.ai.models import AISuggestion
        return [
            AISuggestion(
                id=1,
                company_id=kwargs.get("company_id", 1),
                trigger_type="dashboard_view",
                title="Mock Suggestion",
                description="This is a mocked suggestion.",
                confidence=0.95,
                status="pending",
            )
        ]

    with patch("app.ai.service.OpenAIService.create_chat_completion", new=_mock_chat_completion):
        with patch("app.ai.service.AISuggestionService.generate_suggestions", new=_mock_suggestions):
            yield


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    fake = fakeredis.aioredis.FakeRedis()
    yield fake
    asyncio.run(fake.close())


# ---------------------------------------------------------------------------
# Mock email service
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_email(monkeypatch):
    """Mock email service calls."""
    mock_send = AsyncMock(return_value={"success": True, "message_id": "mock-msg-id"})
    monkeypatch.setattr("app.notifications.service.send_email", mock_send)
    yield mock_send


# ---------------------------------------------------------------------------
# Mock social media APIs
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_social_apis(monkeypatch):
    """Mock external social media API calls."""
    mock_post = AsyncMock(return_value={"id": "mock_post_123", "success": True})
    mock_fetch = AsyncMock(return_value={"likes": 100, "comments": 50, "shares": 25})
    monkeypatch.setattr("app.social.service.SocialAccountService._post_to_platform", mock_post)
    monkeypatch.setattr("app.social.service.SocialAccountService._fetch_analytics", mock_fetch)
    yield {"post": mock_post, "fetch": mock_fetch}


# ---------------------------------------------------------------------------
# Mock storage service
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_storage(monkeypatch):
    """Mock storage service for media uploads."""
    mock_upload = AsyncMock(return_value={
        "storage_key": "mock-key-123",
        "url": "https://mock-cdn.example.com/mock-key-123",
        "provider": "mock",
    })
    monkeypatch.setattr("app.media.service.StorageService.upload_file", mock_upload)
    yield mock_upload


# ---------------------------------------------------------------------------
# Mock ERP connector
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_erp_connector(monkeypatch):
    """Mock ERP connector for sync operations."""
    mock_sync = AsyncMock(return_value={
        "success": True,
        "synced": 42,
        "errors": 0,
        "duration_ms": 1250,
    })
    mock_health = AsyncMock(return_value={
        "status": "healthy",
        "last_sync": "2024-01-01T00:00:00Z",
        "pending_changes": 0,
    })
    monkeypatch.setattr("app.erp.service.ERPSyncService.sync_data", mock_sync)
    monkeypatch.setattr("app.erp.service.ERPHealthService.check_health", mock_health)
    yield {"sync": mock_sync, "health": mock_health}
