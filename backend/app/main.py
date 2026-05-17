"""FastAPI application main entry point.

Feature flag-based lazy import system.
Only enabled modules are imported at startup.
Disabled modules are skipped without errors.
"""

import importlib
import os
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.database import close_db, init_db
from app.redis_client import close_redis, get_redis_client
from app.exceptions import register_exception_handlers
from app.middleware.cors import setup_cors

logger = logging.getLogger(__name__)

# =============================================================================
# Feature Flags (from environment variables)
# =============================================================================

MODULE_FLAGS = {
    "health": os.environ.get("ENABLE_HEALTH", "true").lower() == "true",
    "auth": os.environ.get("ENABLE_AUTH", "true").lower() == "true",
    "followers": os.environ.get("ENABLE_FOLLOWERS", "true").lower() == "true",
    "companies": os.environ.get("ENABLE_COMPANIES", "true").lower() == "true",
    "branches": os.environ.get("ENABLE_BRANCHES", "true").lower() == "true",
    "dashboard": os.environ.get("ENABLE_DASHBOARD", "true").lower() == "true",
    "analytics": os.environ.get("ENABLE_ANALYTICS", "true").lower() == "true",
    "erp": os.environ.get("ENABLE_ERP", "true").lower() == "true",
    "notifications": os.environ.get("ENABLE_NOTIFICATIONS", "true").lower() == "true",
    "ai": os.environ.get("ENABLE_AI", "false").lower() == "true",
    "rag": os.environ.get("ENABLE_RAG", "false").lower() == "true",
    "social": os.environ.get("ENABLE_SOCIAL", "false").lower() == "true",
    "media": os.environ.get("ENABLE_MEDIA", "true").lower() == "true",
    "events": os.environ.get("ENABLE_EVENTS", "false").lower() == "true",
    "billing": os.environ.get("ENABLE_BILLING", "true").lower() == "true",
    "audit": os.environ.get("ENABLE_AUDIT", "false").lower() == "true",
    "ads": os.environ.get("ENABLE_ADS", "true").lower() == "true",
    "reports": os.environ.get("ENABLE_REPORTS", "true").lower() == "true",
    "support": os.environ.get("ENABLE_SUPPORT", "true").lower() == "true",
    "knowledge": os.environ.get("ENABLE_KNOWLEDGE", "false").lower() == "true",
    "governance": os.environ.get("ENABLE_GOVERNANCE", "true").lower() == "true",
    "localization": os.environ.get("ENABLE_LOCALIZATION", "false").lower() == "true",
    "realtime": os.environ.get("ENABLE_REALTIME", "true").lower() == "true",
    "revenue": os.environ.get("ENABLE_REVENUE", "false").lower() == "true",
}


# =============================================================================
# Safe Router Loader
# =============================================================================

def load_router(module_name: str, app: FastAPI, import_path: str, router_name: str, prefix: str, tags: list):
    """Safely load a router module. Skip if disabled or import fails.

    Uses importlib.import_module for reliable import resolution.
    Args:
        module_name: Feature flag key
        app: FastAPI app
        import_path: Python import path (e.g., "app.reports.router")
        router_name: Variable name in module (e.g., "router")
        prefix: URL prefix
        tags: OpenAPI tags
    """
    if not MODULE_FLAGS.get(module_name, False):
        logger.info(f"[FEATURE FLAG] {module_name}: DISABLED, skipping")
        return

    try:
        module = importlib.import_module(import_path)
        router = getattr(module, router_name)
        app.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"[FEATURE FLAG] {module_name}: ENABLED, router loaded at {prefix}")
    except Exception as e:
        logger.warning(f"[FEATURE FLAG] {module_name}: ENABLED but import failed: {type(e).__name__}: {e}")
        # Don't crash - just skip this module


def load_router_from_variable(module_name: str, router, prefix: str, tags: list):
    """Load router from already-imported variable.

    Args:
        module_name: Feature flag key
        router: Router object
        prefix: URL prefix
        tags: OpenAPI tags
    """
    if not MODULE_FLAGS.get(module_name, False):
        logger.info(f"[FEATURE FLAG] {module_name}: DISABLED, skipping")
        return

    try:
        app.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"[FEATURE FLAG] {module_name}: ENABLED, router loaded at {prefix}")
    except Exception as e:
        logger.warning(f"[FEATURE FLAG] {module_name}: ENABLED but registration failed: {e}")


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    try:
        from app.health.logging_config import configure_logging
        configure_logging()
    except Exception as e:
        logger.warning(f"Logging config failed: {e}")

    # Pre-register base models FIRST (companies, branches must be before ai)
    try:
        from app.companies import models as _companies_models
        from app.branches import models as _branches_models
        logger.info("[INIT] Base models registered: companies, branches")
    except Exception as e:
        logger.warning(f"[INIT] Base model registration failed: {e}")

    # Pre-register social_accounts model for followers FK reference
    try:
        from app.social import models as _social_models
        logger.info("[INIT] Social models registered")
    except Exception as e:
        logger.warning(f"[INIT] Social model registration failed: {e}")

    # Pre-register followers models
    try:
        from app.followers import models as _followers_models
        logger.info("[INIT] Followers models registered")
    except Exception as e:
        logger.warning(f"[INIT] Followers model registration failed: {e}")

    # Pre-register AI models LAST (after companies/branches are in metadata)
    try:
        from app.ai import models as _ai_models
        logger.info("[INIT] AI models registered")
    except Exception as e:
        logger.warning(f"[INIT] AI model registration failed: {e}")

    try:
        await init_db()
    except Exception as e:
        logger.warning(f"DB init failed: {e}")

    try:
        await get_redis_client()
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")

    try:
        from app.realtime.publisher import get_pubsub_bridge
        await get_pubsub_bridge()
    except Exception as e:
        logger.warning(f"Pub/sub bridge init failed (will retry): {e}")

    yield

    # Shutdown
    try:
        from app.realtime.publisher import close_pubsub_bridge
        await close_pubsub_bridge()
    except:
        pass
    try:
        await close_db()
    except:
        pass
    try:
        await close_redis()
    except:
        pass


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="AI Marketing Platform",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
)

# Serve frontend at root - via endpoint (not mount, to avoid API route conflicts)
static_dir = "/app/static"
_frontend_available = os.path.exists(static_dir) and os.path.exists(os.path.join(static_dir, "index.html"))

if _frontend_available:
    logger.info("[STATIC] Frontend available, serving at /")
else:
    logger.warning("[STATIC] Frontend not built yet, serving API only")

@app.get("/", include_in_schema=False)
async def root():
    """Serve frontend index.html if available, otherwise API info."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "AI Marketing Platform API",
        "version": "2.0.0",
        "status": "running",
        "health": "/api/v2/health/live",
    }

# Serve frontend assets at /assets
if _frontend_available:
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="frontend-assets")

# Redirect /api/docs to /docs
@app.get("/api/docs", include_in_schema=False)
async def redirect_docs():
    return RedirectResponse(url="/docs")

# Redirect /api/redoc to /redoc
@app.get("/api/redoc", include_in_schema=False)
async def redirect_redoc():
    return RedirectResponse(url="/redoc")

# CORS
setup_cors(app)

# Exception handlers
register_exception_handlers(app)


# =============================================================================
# Middleware Stack (applied in reverse order: last added = outermost)
# =============================================================================

# 1. Core middleware (always enabled)
try:
    from app.middleware.tenant import TenantMiddleware
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(TenantMiddleware)
    app.add_middleware(RateLimitMiddleware)
    logger.info("[MIDDLEWARE] Tenant + RateLimit: loaded")
except Exception as e:
    logger.warning(f"[MIDDLEWARE] Core middleware failed: {e}")

# 2. Security headers
try:
    from app.audit.middleware import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("[MIDDLEWARE] SecurityHeaders: loaded")
except Exception as e:
    logger.warning(f"[MIDDLEWARE] SecurityHeaders failed: {e}")

# 3. Logging middleware
try:
    from app.health.middleware import LoggingMiddleware
    app.add_middleware(LoggingMiddleware)
    logger.info("[MIDDLEWARE] Logging: loaded")
except Exception as e:
    logger.warning(f"[MIDDLEWARE] Logging failed: {e}")


# =============================================================================
# Router Registration - Phase 1: Core (always enabled)
# =============================================================================

# Health (no prefix) - ALWAYS ENABLED
logger.info("[ROUTER] Loading Phase 1: Core modules")
try:
    from app.companies.router import health_router
    app.include_router(health_router)
    logger.info("[ROUTER] health: loaded (no prefix)")
except Exception as e:
    logger.error(f"[ROUTER] health: FAILED: {e}")

# Auth
try:
    from app.auth.router import router as auth_router
    app.include_router(auth_router, prefix="/api/v2/auth", tags=["Authentication"])
    logger.info("[ROUTER] auth: loaded")
except Exception as e:
    logger.error(f"[ROUTER] auth: FAILED: {e}")

# Health v2
try:
    from app.health.router import router as health_router_v2
    app.include_router(health_router_v2, prefix="/api/v2/health", tags=["Health"])
    logger.info("[ROUTER] health v2: loaded")
except Exception as e:
    logger.error(f"[ROUTER] health v2: FAILED: {e}")


# =============================================================================
# Router Registration - Phase 2: Critical (feature flagged)
# =============================================================================

logger.info("[ROUTER] Loading Phase 2: Critical modules")

load_router("companies", app, "app.companies.router", "router", "/api/v2/companies", ["Companies"])
load_router("branches", app, "app.branches.router", "router", "/api/v2/branches", ["Branches"])
load_router("dashboard", app, "app.dashboard.router", "router", "/api/v2/dashboard", ["Dashboard"])
load_router("followers", app, "app.followers.router", "router", "/api/v2/followers", ["Follower Intelligence"])


# =============================================================================
# Router Registration - Phase 3: Advanced (feature flagged, default OFF)
# =============================================================================

logger.info("[ROUTER] Loading Phase 3: Advanced modules")

load_router("analytics", app, "app.analytics.router", "router", "/api/v2/analytics", ["Analytics"])
load_router("erp", app, "app.erp.router", "router", "/api/v2/erp", ["ERP Integration"])
load_router("notifications", app, "app.notifications.router", "router", "/api/v2/notifications", ["Notifications"])
load_router("ai", app, "app.ai.router", "router", "/api/v2/ai", ["AI Architecture"])
load_router("rag", app, "app.ai.rag_router", "router", "/api/v2/ai/rag", ["RAG & Vector Memory"])
load_router("social", app, "app.social.router", "router", "/api/v2/social", ["Social Media"])
load_router("media", app, "app.media.router", "router", "/api/v2/media", ["Creative Studio"])
load_router("events", app, "app.events.router", "router", "/api/v2/events", ["Events"])
load_router("billing", app, "app.billing.router", "router", "/api/v2/billing", ["Billing"])
load_router("audit", app, "app.audit.router", "router", "/api/v2/audit", ["Audit & Security"])
load_router("ads", app, "app.ads.router", "router", "/api/v2/ads", ["Ads Intelligence"])
load_router("reports", app, "app.reports.router", "router", "/api/v2/reports", ["Reports & Export"])
load_router("support", app, "app.support.router", "router", "/api/v2/support", ["AI Support"])
load_router("knowledge", app, "app.knowledge.router", "router", "/api/v2/knowledge", ["Knowledge Ingestion"])

# Governance sub-routers
try:
    if MODULE_FLAGS.get("governance"):
        from app.governance.router import router as governance_router
        app.include_router(governance_router, prefix="/api/v2/governance", tags=["Data Governance"])
        logger.info("[ROUTER] governance: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] governance: {e}")

# Localization
try:
    if MODULE_FLAGS.get("localization"):
        from app.branches.localization_router import router as localization_router
        app.include_router(localization_router, prefix="/api/v2/localization", tags=["Localization"])
        logger.info("[ROUTER] localization: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] localization: {e}")

# Revenue Intelligence
try:
    if MODULE_FLAGS.get("revenue"):
        from app.analytics.revenue_router import router as revenue_intelligence_router
        app.include_router(revenue_intelligence_router, prefix="/api/v2/revenue-intelligence", tags=["Revenue Intelligence"])
        logger.info("[ROUTER] revenue: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] revenue: {e}")

# Realtime (WebSocket)
try:
    if MODULE_FLAGS.get("realtime"):
        from app.realtime.gateway import websocket_endpoint
        from app.realtime.router import router as realtime_router
        # Use FastAPI websocket decorator instead of add_websocket_route
        app.websocket("/ws")(websocket_endpoint)
        app.include_router(realtime_router, prefix="/api/v2/realtime", tags=["Realtime"])
        logger.info("[ROUTER] realtime: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] realtime: {e}")

# AI sub-routers
try:
    if MODULE_FLAGS.get("ai"):
        from app.ai.safety_router import router as ai_safety_router
        from app.ai.cost_router import router as ai_cost_router
        from app.ai.explainability_router import router as ai_explain_router
        from app.ai.evaluation_router import router as ai_evaluation_router
        app.include_router(ai_safety_router, prefix="/api/v2/ai-safety", tags=["AI Safety"])
        app.include_router(ai_cost_router, prefix="/api/v2/ai-cost", tags=["AI Cost Governance"])
        app.include_router(ai_explain_router, prefix="/api/v2/ai-explain", tags=["AI Explainability"])
        app.include_router(ai_evaluation_router, prefix="/api/v2/ai-evaluation", tags=["AI Evaluation"])
        logger.info("[ROUTER] AI sub-routers: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] AI sub-routers: {e}")

# Governance sub-routers
try:
    if MODULE_FLAGS.get("governance"):
        from app.governance.admin_router import router as admin_router
        from app.governance.rollout_router import router as rollout_router
        from app.governance.incident_router import router as incident_router
        from app.governance.tenant_governance_router import router as tenant_governance_router
        from app.governance.compliance_router import router as compliance_router
        from app.governance.api_lifecycle_router import router as api_lifecycle_router
        from app.governance.api_deprecation_middleware import APIDeprecationMiddleware
        app.include_router(admin_router, prefix="/api/v2/admin", tags=["Admin & Ops"])
        app.include_router(rollout_router, prefix="/api/v2/rollout", tags=["Rollout Management"])
        app.include_router(incident_router, prefix="/api/v2/incidents", tags=["Incident Management"])
        app.include_router(tenant_governance_router, prefix="/api/v2/tenant-governance", tags=["Tenant Governance"])
        app.include_router(compliance_router, prefix="/api/v2/compliance", tags=["Enterprise Compliance"])
        app.include_router(api_lifecycle_router, prefix="/api/v2/api-lifecycle", tags=["API Lifecycle"])
        app.add_middleware(APIDeprecationMiddleware)
        logger.info("[ROUTER] Governance sub-routers: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] Governance sub-routers: {e}")

# Audit & Security sub-routers
try:
    if MODULE_FLAGS.get("audit"):
        from app.auth.permissions_router import router as permissions_router
        from app.health.observability_router import router as observability_router
        from app.support.operator_router import router as operator_router
        app.include_router(permissions_router, prefix="/api/v2/permissions", tags=["Permissions"])
        app.include_router(observability_router, prefix="/api/v2/observability", tags=["Observability"])
        app.include_router(operator_router, prefix="/api/v2/operators", tags=["Support Operators"])
        logger.info("[ROUTER] Audit sub-routers: loaded")
except Exception as e:
    logger.warning(f"[ROUTER] Audit sub-routers: {e}")

# Metrics middleware
try:
    from app.health.middleware import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)
    logger.info("[MIDDLEWARE] Metrics: loaded")
except Exception as e:
    logger.warning(f"[MIDDLEWARE] Metrics failed: {e}")

logger.info("[ROUTER] Router registration complete")
