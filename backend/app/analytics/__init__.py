"""Analytics router package.

Provides endpoints for aggregated analytics data sourced from real
database tables with SQLAlchemy 2.0 async aggregation queries.

All endpoints include:
- company_id tenant isolation
- branch_id optional filtering
- date range filtering
- Redis caching with 5-minute TTL
- empty dataset handling with informative messages
"""

from app.analytics.router import router

__all__ = ["router"]
