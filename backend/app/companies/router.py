"""Companies router with health check endpoints and company CRUD operations."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import NotFoundError
from app.redis_client import get_redis_client

from .models import Company
from .schemas import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter()

# Separate health router (mounted without prefix in main.py)
health_router = APIRouter()


# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------

def _apply_company_scope(
    query,
    user: User,
    model,
    company_id_field: str = "company_id",
):
    """Restrict a SQLAlchemy query to the companies the user may access.

    * super_admin  -> no restriction
    * company_admin / manager / user -> only their own company
    """
    if user.role == "super_admin":
        return query
    return query.where(getattr(model, company_id_field) == user.company_id)


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
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    """Check database connectivity with real connection test."""
    start_time = time.time()
    try:
        result = await db.execute(select(1))
        row = result.scalar()
        if row == 1:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "healthy",
                "database": "connected",
                "response_time_ms": elapsed_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
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
# Company CRUD endpoints (real DB)
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=list[CompanyResponse],
    status_code=status.HTTP_200_OK,
    summary="List all companies",
)
async def list_companies(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Company]:
    """List companies with tenant isolation.

    * super_admin  -> all companies
    * other roles  -> only own company
    """
    query = _apply_company_scope(select(Company), current_user, Company, "id")
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company",
)
async def create_company(
    request: Request,
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin"])),
) -> Company:
    """Create a new company (super_admin only)."""
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a company by ID",
)
async def get_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Company:
    """Get a single company with tenant isolation."""
    query = _apply_company_scope(
        select(Company).where(Company.id == company_id),
        current_user,
        Company,
        "id",
    )

    result = await db.execute(query)
    company = result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")
    return company


@router.put(
    "/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a company",
)
async def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Company:
    """Update a company with tenant isolation.

    * super_admin can update any company
    * company_admin can update their own company
    """
    # Fetch with tenant scope
    query = _apply_company_scope(
        select(Company).where(Company.id == company_id),
        current_user,
        Company,
        "id",
    )

    result = await db.execute(query)
    company = result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    # Apply updates for non-None fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a company",
)
async def delete_company(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin"])),
) -> None:
    """Delete a company (super_admin only)."""
    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    await db.delete(company)
    await db.commit()


# ---------------------------------------------------------------------------
# Company stats endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/{company_id}/stats",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get company statistics",
)
async def get_company_stats(
    company_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return aggregated stats for a company (branch count, user count)."""
    # Tenant isolation
    if current_user.role != "super_admin" and current_user.company_id != company_id:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    # Import here to avoid circular imports
    from app.branches.models import Branch

    branch_count_result = await db.execute(
        select(func.count(Branch.id)).where(Branch.company_id == company_id)
    )
    branch_count = branch_count_result.scalar_one()

    from app.auth.models import User

    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.company_id == company_id)
    )
    user_count = user_count_result.scalar_one()

    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    if company is None:
        raise NotFoundError(detail=f"Company with ID {company_id} not found")

    return {
        "company_id": company_id,
        "company_name": company.name,
        "plan": company.plan.value if company.plan else None,
        "subscription_status": (
            company.subscription_status.value if company.subscription_status else None
        ),
        "branch_count": branch_count,
        "user_count": user_count,
        "max_branches": company.max_branches,
        "max_users": company.max_users,
    }
