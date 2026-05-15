"""Companies router with health check endpoints and company CRUD operations."""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Request, status
from sqlalchemy import text

from app.database import engine
from app.exceptions import NotFoundError
from app.redis_client import get_redis_client

router = APIRouter()

# Separate health router (mounted without prefix in main.py)
health_router = APIRouter()

# ---------------------------------------------------------------------------
# Mock in-memory company store
# ---------------------------------------------------------------------------
_mock_companies: Dict[str, Dict] = {}


def _generate_company_id() -> str:
    """Generate a unique company ID."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Health check endpoints
# ---------------------------------------------------------------------------

@health_router.get(
    "/api/health",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="General health check",
    tags=["Health"],
)
async def health_check() -> dict:
    """Return general application health status."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "AI Marketing Platform API",
    }


@health_router.get(
    "/api/health/db",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Database health check",
    tags=["Health"],
)
async def health_db() -> dict:
    """Check database connectivity with real connection test."""
    start_time = time.time()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.scalar()
            if row == 1:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                return {
                    "status": "healthy",
                    "database": "connected",
                    "response_time_ms": elapsed_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "status": "unhealthy",
                    "database": "unexpected response",
                    "error": "Database returned unexpected result",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": f"Database connection failed: {str(exc)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@health_router.get(
    "/api/health/redis",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Redis health check",
    tags=["Health"],
)
async def health_redis() -> dict:
    """Check Redis connectivity with real ping test."""
    start_time = time.time()
    try:
        redis = await get_redis_client()
        pong = await redis.ping()
        if pong:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "healthy",
                "redis": "connected",
                "response_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "status": "unhealthy",
                "redis": "unexpected response",
                "error": "Redis ping returned unexpected result",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": f"Redis connection failed: {str(exc)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# Company CRUD endpoints (mock)
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="List all companies",
)
async def list_companies(request: Request) -> List[dict]:
    """List all companies (mock)."""
    return list(_mock_companies.values())


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company",
)
async def create_company(request: Request, data: dict) -> dict:
    """Create a new company (mock)."""
    company_id = _generate_company_id()
    now = datetime.now(timezone.utc).isoformat()

    company = {
        "id": company_id,
        "name": data.get("name", "Unnamed Company"),
        "slug": data.get("slug", ""),
        "description": data.get("description", ""),
        "website": data.get("website", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "tax_number": data.get("tax_number", ""),
        "is_active": data.get("is_active", True),
        "created_at": now,
        "updated_at": now,
    }

    _mock_companies[company_id] = company
    return company


@router.get(
    "/{company_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get a company by ID",
)
async def get_company(company_id: str) -> dict:
    """Get a company by ID (mock)."""
    company = _mock_companies.get(company_id)
    if not company:
        raise NotFoundError(detail=f"Company with ID '{company_id}' not found")
    return company


@router.put(
    "/{company_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Update a company",
)
async def update_company(company_id: str, data: dict) -> dict:
    """Update a company by ID (mock)."""
    company = _mock_companies.get(company_id)
    if not company:
        raise NotFoundError(detail=f"Company with ID '{company_id}' not found")

    updatable_fields = [
        "name", "slug", "description", "website",
        "phone", "email", "address", "tax_number", "is_active",
    ]
    for field in updatable_fields:
        if field in data:
            company[field] = data[field]

    company["updated_at"] = datetime.now(timezone.utc).isoformat()
    _mock_companies[company_id] = company

    return company


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company",
)
async def delete_company(company_id: str) -> None:
    """Delete a company by ID (mock)."""
    if company_id not in _mock_companies:
        raise NotFoundError(detail=f"Company with ID '{company_id}' not found")
    del _mock_companies[company_id]
