"""FastAPI application main entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.branches.router import router as branches_router
from app.companies.router import health_router, router as companies_router
from app.analytics.router import router as analytics_router
from app.dashboard.router import router as dashboard_router
from app.database import close_db, init_db
from app.notifications.router import router as notifications_router
from app.erp.router import router as erp_router
from app.exceptions import register_exception_handlers
from app.middleware.cors import setup_cors
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.tenant import TenantMiddleware
from app.redis_client import close_redis, get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    await init_db()
    await get_redis_client()
    yield
    # Shutdown
    await close_db()
    await close_redis()


app = FastAPI(
    title="AI Marketing Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS
setup_cors(app)

# Exception handlers
register_exception_handlers(app)

# Middleware
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)

# Routers
app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v2/auth", tags=["Authentication"])
app.include_router(companies_router, prefix="/api/v2/companies", tags=["Companies"])
app.include_router(branches_router, prefix="/api/v2/branches", tags=["Branches"])
app.include_router(dashboard_router, prefix="/api/v2/dashboard", tags=["Dashboard"])
app.include_router(analytics_router, prefix="/api/v2/analytics", tags=["Analytics"])
app.include_router(notifications_router, prefix="/api/v2/notifications", tags=["Notifications"])
app.include_router(erp_router, prefix="/api/v2/erp", tags=["ERP Integration"])
