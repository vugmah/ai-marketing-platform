"""Dashboard API module for aggregated statistics and analytics.

Provides endpoints for:
    - Executive summary (company-wide KPIs)
    - Branch-scoped dashboard KPIs
    - Branch-to-branch comparison
    - Branch growth analytics (month-over-month)
    - KPI threshold alert widgets
    - 30-day trend charts
    - System alerts

All KPIs are sourced from real database tables using SQLAlchemy async
aggregation queries with Redis caching (5-minute TTL).
"""

from app.dashboard.router import router
from app.dashboard.service import invalidate_dashboard_cache

__all__ = ["router", "invalidate_dashboard_cache"]
