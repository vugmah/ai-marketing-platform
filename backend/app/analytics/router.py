"""Analytics router for aggregated analytics data.

Provides endpoints for analytics overview, traffic trends, and audience
demographics. Data is synthesized from company/branch counts and cached
in Redis with a 5-minute TTL.
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.branches.models import Branch
from app.companies.models import Company
from app.database import get_db
from app.dependencies import get_current_user
from app.redis_client import get_cache, get_redis_client

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANALYTICS_CACHE_KEY = "analytics:overview"
ANALYTICS_CACHE_TTL = 300  # 5 minutes

# Base multiplier for visitor calculations
BASE_VISITOR_MULTIPLIER = 12540
BASE_PAGE_VIEW_MULTIPLIER = 4200

# Fixed data skeletons
_TOP_SOURCES = [
    {"name": "Google", "visitors": 5200, "percentage": 41.5},
    {"name": "Instagram", "visitors": 3800, "percentage": 30.3},
    {"name": "Facebook", "visitors": 2100, "percentage": 16.7},
    {"name": "Diger", "visitors": 1440, "percentage": 11.5},
]

_TOP_PAGES_BASE = [
    {"path": "/menu", "views": 4200},
    {"path": "/iletisim", "views": 2800},
    {"path": "/hakkimizda", "views": 1500},
]

_AGE_GROUPS = [
    {"range": "18-24", "percentage": 22},
    {"range": "25-34", "percentage": 35},
    {"range": "35-44", "percentage": 24},
    {"range": "45-54", "percentage": 12},
    {"range": "55+", "percentage": 7},
]

_GENDER_SPLIT = {"male": 48, "female": 50, "other": 2}

_TOP_CITIES = [
    {"name": "Baku", "visitors": 4200},
    {"name": "Gence", "visitors": 1800},
    {"name": "Sumqayit", "visitors": 1200},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_daily_traffic(days: int = 30) -> Dict[str, List[Any]]:
    """Generate realistic daily traffic data for the last N days."""
    dates: List[str] = []
    visitors: List[int] = []
    page_views: List[int] = []
    sessions: List[int] = []

    base_date = datetime.now(timezone.utc) - timedelta(days=days)
    for i in range(days):
        day = base_date + timedelta(days=i)
        dates.append(day.strftime("%Y-%m-%d"))

        # Add some realistic variation
        day_of_week = day.weekday()
        weekend_factor = 0.7 if day_of_week >= 5 else 1.0
        trend = 1 + (i / days) * 0.1  # Slight upward trend
        noise = random.uniform(0.85, 1.15)

        daily_visitors = int(320 * weekend_factor * trend * noise)
        daily_page_views = int(daily_visitors * 2.8 * random.uniform(0.9, 1.1))
        daily_sessions = int(daily_visitors * 0.88 * random.uniform(0.9, 1.1))

        visitors.append(daily_visitors)
        page_views.append(daily_page_views)
        sessions.append(daily_sessions)

    return {
        "dates": dates,
        "visitors": visitors,
        "page_views": page_views,
        "sessions": sessions,
    }


def _scale_sources(sources: List[Dict], scale_factor: float) -> List[Dict]:
    """Scale visitor counts in source breakdown."""
    scaled = []
    for src in sources:
        new_visitors = int(src["visitors"] * scale_factor)
        scaled.append({
            "name": src["name"],
            "visitors": new_visitors,
            "percentage": src["percentage"],
        })
    return scaled


def _scale_pages(pages: List[Dict], scale_factor: float) -> List[Dict]:
    """Scale view counts in top pages."""
    scaled = []
    for page in pages:
        new_views = int(page["views"] * scale_factor)
        scaled.append({
            "path": page["path"],
            "views": new_views,
        })
    return scaled


def _scale_cities(cities: List[Dict], scale_factor: float) -> List[Dict]:
    """Scale visitor counts in top cities."""
    scaled = []
    for city in cities:
        new_visitors = int(city["visitors"] * scale_factor)
        scaled.append({
            "name": city["name"],
            "visitors": new_visitors,
        })
    return scaled


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/overview
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get analytics overview summary",
)
async def get_analytics_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return analytics overview with visitor stats, sources, devices, and pages.

    Data is cached in Redis for 5 minutes and scaled based on company/branch counts.
    """
    cache = await get_cache()

    # Check cache first
    cached = await cache.get(ANALYTICS_CACHE_KEY)
    if cached:
        return {"success": True, "data": cached}

    # Get counts from database
    company_result = await db.execute(select(func.count()).select_from(Company))
    company_count = company_result.scalar() or 0

    branch_result = await db.execute(select(func.count()).select_from(Branch))
    branch_count = branch_result.scalar() or 0

    # Scale factor based on company/branch counts (minimum 1.0)
    scale_factor = max(1.0, 1.0 + company_count * 0.1 + branch_count * 0.05)

    total_visitors = int(BASE_VISITOR_MULTIPLIER * scale_factor)
    unique_visitors = int(total_visitors * 0.664)
    bounce_rate = round(35.2 + random.uniform(-2.0, 2.0), 1)
    avg_session_duration = int(245 * random.uniform(0.9, 1.1))

    data = {
        "total_visitors": total_visitors,
        "unique_visitors": unique_visitors,
        "bounce_rate": bounce_rate,
        "avg_session_duration": avg_session_duration,
        "top_sources": _scale_sources(_TOP_SOURCES, scale_factor),
        "device_breakdown": {
            "mobile": round(62.5 + random.uniform(-3.0, 3.0), 1),
            "desktop": round(30.2 + random.uniform(-2.0, 2.0), 1),
            "tablet": round(7.3 + random.uniform(-1.0, 1.0), 1),
        },
        "top_pages": _scale_pages(_TOP_PAGES_BASE, scale_factor),
    }

    # Store in cache
    await cache.set(ANALYTICS_CACHE_KEY, data, ttl=ANALYTICS_CACHE_TTL)

    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/traffic
# ---------------------------------------------------------------------------


@router.get(
    "/traffic",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get daily traffic for the last 30 days",
)
async def get_traffic_data(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return daily traffic data for the last 30 days."""
    traffic_data = _generate_daily_traffic(days=30)
    return {"success": True, "data": traffic_data}


# ---------------------------------------------------------------------------
# GET /api/v2/analytics/audience
# ---------------------------------------------------------------------------


@router.get(
    "/audience",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get audience demographics",
)
async def get_audience_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return audience demographics including age, gender, and city breakdown."""
    company_result = await db.execute(select(func.count()).select_from(Company))
    company_count = company_result.scalar() or 0

    branch_result = await db.execute(select(func.count()).select_from(Branch))
    branch_count = branch_result.scalar() or 0

    scale_factor = max(1.0, 1.0 + company_count * 0.1 + branch_count * 0.05)

    data = {
        "age_groups": _AGE_GROUPS,
        "gender_split": _GENDER_SPLIT,
        "top_cities": _scale_cities(_TOP_CITIES, scale_factor),
    }

    return {"success": True, "data": data}
