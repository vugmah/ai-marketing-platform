"""Ads Intelligence API services.

Provides production-ready service implementations for:
- Google Ads API integration (httpx async client, token refresh, rate limiting)
- Meta Marketing API integration (async client, token refresh)
- ROAS/CPA/CPC/CTR engine (real API data calculations)
- Budget recommendations (DB + API data, no auto-change)
- Audience analysis (real implementation)
- Creative fatigue detection (CTR decline detection)
- Local campaign recommendations
- Data synchronization from ad platforms
"""

import asyncio
import json
import logging
import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ads.constants import (
    GOOGLE_ADS_BENCHMARKS,
    GoogleAdsConfig,
    INDUSTRY_BENCHMARKS,
    META_ADS_BENCHMARKS,
    MetaAdsConfig,
    SyncConfig,
)
from app.ads.models import (
    AdAudience,
    AdBudgetRecommendation,
    AdCampaign,
    AdCreative,
    AdCreativeAnalysis,
    AdMetric,
    AdPlatform,
    AdPlatformAccount,
    AnalysisType,
    AudienceType,
    CampaignStatus,
    CreativeType,
    PlatformStatus,
)
from app.ads.schemas import DateRangeFilter
from app.exceptions import APIError, NotFoundError, ValidationError
from app.utils.encryption import decrypt_api_credentials

logger = logging.getLogger(__name__)


# =============================================================================
# Utility: Retry with exponential backoff
# =============================================================================


async def _exponential_backoff_retry(
    func,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    retryable_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504),
    *args,
    **kwargs,
) -> Any:
    """Execute an async function with exponential backoff retry.

    Args:
        func: Async function to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.
        retryable_statuses: HTTP status codes that trigger retry.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.

    Returns:
        Function result.

    Raises:
        APIError: If all retries are exhausted.
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in retryable_statuses or attempt >= max_retries:
                raise APIError(
                    detail=f"HTTP {status}: {exc.response.text[:500]}",
                    status_code=status,
                )
            delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
            logger.warning(
                "Retry %d/%d for %s: HTTP %d, waiting %.2fs",
                attempt + 1,
                max_retries,
                func.__name__,
                status,
                delay,
            )
            await asyncio.sleep(delay)
            last_exception = exc
        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            if attempt >= max_retries:
                raise APIError(detail=f"Network error: {str(exc)}", status_code=503)
            delay = min(base_delay * (2**attempt) + random.uniform(0, 1), max_delay)
            logger.warning(
                "Retry %d/%d for %s: %s, waiting %.2fs",
                attempt + 1,
                max_retries,
                func.__name__,
                str(exc),
                delay,
            )
            await asyncio.sleep(delay)
            last_exception = exc
    raise APIError(detail=f"All retries exhausted: {str(last_exception)}")


# =============================================================================
# Utility: Token Refresh
# =============================================================================


async def _refresh_google_token(refresh_token: str, client_id: str = None, client_secret: str = None) -> str:
    """Refresh a Google OAuth access token.

    Args:
        refresh_token: The refresh token.
        client_id: Google OAuth client ID (from settings or env).
        client_secret: Google OAuth client secret.

    Returns:
        New access token.

    Raises:
        APIError: If token refresh fails.
    """
    # client_id and client_secret MUST come from settings (never hardcode)
    from app.config import settings
    if not client_id:
        client_id = getattr(settings, "GOOGLE_ADS_CLIENT_ID", "")
    if not client_secret:
        client_secret = getattr(settings, "GOOGLE_ADS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise APIError(
            detail="Google Ads client_id and client_secret must be configured "
                   "via GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET settings."
        )

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        try:
            resp = await client.post(GoogleAdsConfig.AUTH_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise APIError(detail="Google token refresh: no access_token in response")
            return access_token
        except httpx.HTTPStatusError as exc:
            raise APIError(
                detail=f"Google token refresh failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            )
        except httpx.HTTPError as exc:
            raise APIError(detail=f"Google token refresh failed: {str(exc)}")


async def _refresh_meta_token(refresh_token: str, client_id: str = None, client_secret: str = None) -> str:
    """Refresh a Meta OAuth access token using the long-lived token exchange.

    Args:
        refresh_token: The refresh token.
        client_id: Meta app ID.
        client_secret: Meta app secret.

    Returns:
        New access token.

    Raises:
        APIError: If token refresh fails.
    """
    # client_id and client_secret MUST come from settings (never hardcode)
    from app.config import settings
    if not client_id:
        client_id = getattr(settings, "META_APP_ID", "")
    if not client_secret:
        client_secret = getattr(settings, "META_APP_SECRET", "")
    if not client_id or not client_secret:
        raise APIError(
            detail="Meta client_id and client_secret must be configured "
                   "via META_APP_ID and META_APP_SECRET settings."
        )

    url = f"{MetaAdsConfig.BASE_URL}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "fb_exchange_token": refresh_token,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            access_token = data.get("access_token")
            if not access_token:
                raise APIError(detail="Meta token refresh: no access_token in response")
            return access_token
        except httpx.HTTPStatusError as exc:
            raise APIError(
                detail=f"Meta token refresh failed: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            )
        except httpx.HTTPError as exc:
            raise APIError(detail=f"Meta token refresh failed: {str(exc)}")


# =============================================================================
# Google Ads Service
# =============================================================================


class GoogleAdsService:
    """Google Ads API service with async httpx client.

    Handles campaign retrieval, metrics fetching, token refresh,
    rate limiting, and exponential backoff for resilient API calls.
    """

    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        """Get or create a shared async HTTP client."""
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        """Close the shared HTTP client."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None

    @staticmethod
    def _decrypt_credentials(platform_account: AdPlatformAccount) -> Dict[str, str]:
        """Decrypt platform account credentials.

        Args:
            platform_account: The encrypted platform account.

        Returns:
            Decrypted credentials dictionary.
        """
        creds = {}
        try:
            access = decrypt_api_credentials(platform_account.access_token_encrypted)
            creds["access_token"] = access.get("access_token", "")
        except Exception:
            creds["access_token"] = ""
        try:
            refresh = decrypt_api_credentials(platform_account.refresh_token_encrypted)
            creds["refresh_token"] = refresh.get("refresh_token", "")
        except Exception:
            creds["refresh_token"] = ""
        if platform_account.developer_token_encrypted:
            try:
                dev = decrypt_api_credentials(platform_account.developer_token_encrypted)
                creds["developer_token"] = dev.get("developer_token", "")
            except Exception:
                creds["developer_token"] = ""
        return creds

    @staticmethod
    async def _api_request(
        platform_account: AdPlatformAccount,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request to Google Ads with token refresh.

        Args:
            platform_account: The platform account for credentials.
            method: HTTP method.
            url: Request URL.
            headers: Additional headers.
            json_data: JSON request body.
            params: Query parameters.

        Returns:
            Parsed JSON response.
        """
        creds = GoogleAdsService._decrypt_credentials(platform_account)
        access_token = creds.get("access_token", "")
        developer_token = creds.get("developer_token", "")

        request_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "developer-token": developer_token,
            "login-customer-id": str(platform_account.account_id).replace("-", "").strip(),
        }
        if headers:
            request_headers.update(headers)

        client = GoogleAdsService._get_client()

        async def _do_request():
            if method.upper() == "POST":
                resp = await client.post(url, headers=request_headers, json=json_data, params=params)
            elif method.upper() == "GET":
                resp = await client.get(url, headers=request_headers, params=params)
            else:
                resp = await client.request(method, url, headers=request_headers, json=json_data, params=params)

            # Handle token expiry (401)
            if resp.status_code == 401 and creds.get("refresh_token"):
                logger.info("Google access token expired, refreshing...")
                new_token = await _refresh_google_token(creds["refresh_token"])
                request_headers["Authorization"] = f"Bearer {new_token}"
                if method.upper() == "POST":
                    resp = await client.post(url, headers=request_headers, json=json_data, params=params)
                elif method.upper() == "GET":
                    resp = await client.get(url, headers=request_headers, params=params)
                else:
                    resp = await client.request(method, url, headers=request_headers, json=json_data, params=params)

            resp.raise_for_status()
            if resp.text:
                return resp.json()
            return {}

        return await _exponential_backoff_retry(
            _do_request,
            max_retries=GoogleAdsConfig.MAX_RETRIES,
            base_delay=GoogleAdsConfig.BASE_BACKOFF_SECONDS,
        )

    @staticmethod
    async def get_campaigns(platform_account: AdPlatformAccount) -> List[Dict[str, Any]]:
        """Fetch campaigns from Google Ads API.

        Args:
            platform_account: The connected Google Ads account.

        Returns:
            List of campaign dictionaries.
        """
        customer_id = str(platform_account.account_id).replace("-", "").strip()
        url = f"{GoogleAdsConfig.BASE_URL}/customers/{customer_id}/googleAds:searchStream"

        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign.start_date,
                campaign.end_date,
                campaign_budget.amount_micros,
                campaign.bidding_strategy_type,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.ctr,
                metrics.average_cpc,
                metrics.conversions_value
            FROM campaign
            WHERE campaign.status != 'REMOVED'
        """

        payload = {"query": query}

        try:
            response = await GoogleAdsService._api_request(
                platform_account, "POST", url, json_data=payload
            )
        except APIError as exc:
            logger.error("Google Ads campaign fetch failed: %s", exc.detail)
            # Return empty list on failure - upstream will handle
            return []

        campaigns = []
        for result in response if isinstance(response, list) else [response]:
            if not isinstance(result, dict):
                continue
            results_list = result.get("results", [])
            for row in results_list:
                campaign_data = {}
                campaign = row.get("campaign", {})
                budget = row.get("campaignBudget", {})
                metrics = row.get("metrics", {})

                campaign_data["platform_campaign_id"] = str(campaign.get("id", ""))
                campaign_data["name"] = campaign.get("name", "Unnamed")
                campaign_data["status"] = campaign.get("status", "PAUSED")
                campaign_data["objective"] = campaign.get("advertisingChannelType", "")

                # Budget in micros -> standard currency
                budget_micros = budget.get("amountMicros", "0")
                campaign_data["budget"] = Decimal(str(budget_micros)) / Decimal("1_000_000")

                # Dates (YYYYMMDD -> date)
                start = campaign.get("startDate", "")
                end = campaign.get("endDate", "")
                if start and len(start) == 8:
                    campaign_data["start_date"] = date(int(start[:4]), int(start[4:6]), int(start[6:]))
                else:
                    campaign_data["start_date"] = None
                if end and len(end) == 8:
                    campaign_data["end_date"] = date(int(end[:4]), int(end[4:6]), int(end[6:]))
                else:
                    campaign_data["end_date"] = None

                campaign_data["bid_strategy"] = campaign.get("biddingStrategyType", "")
                campaign_data["targeting"] = {}

                # Metrics
                cost_micros = metrics.get("costMicros", "0")
                conversions_value = metrics.get("conversionsValue", "0")
                campaign_data["metrics"] = {
                    "impressions": int(metrics.get("impressions", 0) or 0),
                    "clicks": int(metrics.get("clicks", 0) or 0),
                    "conversions": float(metrics.get("conversions", 0) or 0),
                    "cost": Decimal(str(cost_micros)) / Decimal("1_000_000"),
                    "ctr": Decimal(str(metrics.get("ctr", 0) or 0)),
                    "cpc": Decimal(str(metrics.get("averageCpc", 0) or 0)),
                    "conversion_value": Decimal(str(conversions_value)),
                }

                campaigns.append(campaign_data)

        logger.info("Fetched %d campaigns from Google Ads account %s", len(campaigns), customer_id)
        return campaigns

    @staticmethod
    async def get_metrics(
        platform_account: AdPlatformAccount,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Fetch campaign metrics from Google Ads API.

        Args:
            platform_account: The connected Google Ads account.
            start_date: Start date.
            end_date: End date.

        Returns:
            List of daily metric records.
        """
        customer_id = str(platform_account.account_id).replace("-", "").strip()
        url = f"{GoogleAdsConfig.BASE_URL}/customers/{customer_id}/googleAds:searchStream"

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        query = f"""
            SELECT
                campaign.id,
                segments.date,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.ctr,
                metrics.average_cpc,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date >= '{start_str}'
            AND segments.date <= '{end_str}'
            AND campaign.status != 'REMOVED'
        """

        payload = {"query": query}

        try:
            response = await GoogleAdsService._api_request(
                platform_account, "POST", url, json_data=payload
            )
        except APIError as exc:
            logger.error("Google Ads metrics fetch failed: %s", exc.detail)
            return []

        metrics_list = []
        for result in response if isinstance(response, list) else [response]:
            if not isinstance(result, dict):
                continue
            for row in result.get("results", []):
                campaign = row.get("campaign", {})
                segments = row.get("segments", {})
                metrics = row.get("metrics", {})

                date_str = segments.get("date", "")
                if not date_str:
                    continue

                try:
                    metric_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue

                impressions = int(metrics.get("impressions", 0) or 0)
                clicks = int(metrics.get("clicks", 0) or 0)
                conversions = float(metrics.get("conversions", 0) or 0)
                cost_micros = Decimal(str(metrics.get("costMicros", "0")))
                cost = cost_micros / Decimal("1_000_000")
                conversions_value = Decimal(str(metrics.get("conversionsValue", "0")))

                # Calculate derived metrics
                ctr = (Decimal(str(clicks)) / Decimal(str(impressions)) * Decimal("100")) if impressions > 0 else Decimal("0")
                cpc = cost / Decimal(str(clicks)) if clicks > 0 else Decimal("0")
                cpa = cost / Decimal(str(conversions)) if conversions > 0 else Decimal("0")
                roas = conversions_value / cost if cost > 0 else Decimal("0")

                metrics_list.append({
                    "platform_campaign_id": str(campaign.get("id", "")),
                    "date": metric_date,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "cost": cost,
                    "ctr": round(ctr, 4),
                    "cpc": round(cpc, 4),
                    "cpa": round(cpa, 4),
                    "roas": round(roas, 4),
                    "conversion_value": conversions_value,
                    "raw_data": row,
                })

        logger.info(
            "Fetched %d metric rows from Google Ads for %s to %s",
            len(metrics_list),
            start_str,
            end_str,
        )
        return metrics_list


# =============================================================================
# Meta Ads Service
# =============================================================================


class MetaAdsService:
    """Meta Marketing API service with async httpx client.

    Handles campaign retrieval, insights fetching, audience sync,
    token refresh, rate limiting, and exponential backoff.
    """

    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        """Get or create a shared async HTTP client."""
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return cls._client

    @classmethod
    async def close_client(cls) -> None:
        """Close the shared HTTP client."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None

    @staticmethod
    def _decrypt_credentials(platform_account: AdPlatformAccount) -> Dict[str, str]:
        """Decrypt platform account credentials."""
        creds = {}
        try:
            access = decrypt_api_credentials(platform_account.access_token_encrypted)
            creds["access_token"] = access.get("access_token", "")
        except Exception:
            creds["access_token"] = ""
        try:
            refresh = decrypt_api_credentials(platform_account.refresh_token_encrypted)
            creds["refresh_token"] = refresh.get("refresh_token", "")
        except Exception:
            creds["refresh_token"] = ""
        return creds

    @staticmethod
    async def _api_request(
        platform_account: AdPlatformAccount,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request to Meta with token refresh."""
        creds = MetaAdsService._decrypt_credentials(platform_account)
        access_token = creds.get("access_token", "")

        request_params = {"access_token": access_token}
        if params:
            request_params.update(params)

        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)

        client = MetaAdsService._get_client()

        async def _do_request():
            if method.upper() == "POST":
                resp = await client.post(url, headers=request_headers, json=json_data, params=request_params)
            elif method.upper() == "GET":
                resp = await client.get(url, headers=request_headers, params=request_params)
            else:
                resp = await client.request(method, url, headers=request_headers, json=json_data, params=request_params)

            # Handle token expiry (code 190 in Meta API, or 401)
            if resp.status_code == 401 and creds.get("refresh_token"):
                logger.info("Meta access token expired, refreshing...")
                new_token = await _refresh_meta_token(creds["refresh_token"])
                request_params["access_token"] = new_token
                if method.upper() == "POST":
                    resp = await client.post(url, headers=request_headers, json=json_data, params=request_params)
                elif method.upper() == "GET":
                    resp = await client.get(url, headers=request_headers, params=request_params)
                else:
                    resp = await client.request(method, url, headers=request_headers, json=json_data, params=request_params)

            # Check for Meta-specific errors (200 OK with error body)
            if resp.status_code == 200:
                try:
                    body = resp.json()
                    error_data = body.get("error", {})
                    if error_data:
                        error_code = error_data.get("code", 0)
                        if error_code == 190 and creds.get("refresh_token"):
                            logger.info("Meta token expired (code 190), refreshing...")
                            new_token = await _refresh_meta_token(creds["refresh_token"])
                            request_params["access_token"] = new_token
                            resp = await client.get(url, headers=request_headers, params=request_params)
                            body = resp.json()
                            error_data = body.get("error", {})
                        if error_data:
                            raise APIError(
                                detail=f"Meta API error {error_code}: {error_data.get('message', 'Unknown')}",
                                status_code=400,
                            )
                    return body
                except (json.JSONDecodeError, ValueError):
                    return {"data": resp.text}
            resp.raise_for_status()
            if resp.text:
                return resp.json()
            return {}

        return await _exponential_backoff_retry(
            _do_request,
            max_retries=MetaAdsConfig.MAX_RETRIES,
            base_delay=MetaAdsConfig.BASE_BACKOFF_SECONDS,
        )

    @staticmethod
    async def get_campaigns(platform_account: AdPlatformAccount) -> List[Dict[str, Any]]:
        """Fetch campaigns from Meta Marketing API.

        Args:
            platform_account: The connected Meta Ads account.

        Returns:
            List of campaign dictionaries.
        """
        account_id = platform_account.account_id
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"

        url = f"{MetaAdsConfig.BASE_URL}/{account_id}/campaigns"
        params = {
            "fields": ",".join(MetaAdsConfig.CAMPAIGN_FIELDS),
            "effective_status": "['ACTIVE','PAUSED','PENDING_REVIEW','DISAPPROVED']",
        }

        campaigns = []
        try:
            response = await MetaAdsService._api_request(
                platform_account, "GET", url, params=params
            )
            data = response.get("data", [])
            for campaign in data:
                start_time = campaign.get("start_time", "")
                stop_time = campaign.get("stop_time", "")

                start_date = None
                end_date = None
                if start_time:
                    try:
                        start_date = datetime.strptime(start_time[:10], "%Y-%m-%d").date()
                    except ValueError:
                        start_date = None
                if stop_time:
                    try:
                        end_date = datetime.strptime(stop_time[:10], "%Y-%m-%d").date()
                    except ValueError:
                        end_date = None

                # Budget: daily or lifetime
                daily_budget = campaign.get("daily_budget", "0")
                lifetime_budget = campaign.get("lifetime_budget", "0")
                budget = Decimal(str(int(daily_budget or 0))) / Decimal("100")
                budget_type = "daily"
                if not budget and lifetime_budget:
                    budget = Decimal(str(int(lifetime_budget))) / Decimal("100")
                    budget_type = "lifetime"

                campaigns.append({
                    "platform_campaign_id": str(campaign.get("id", "")),
                    "name": campaign.get("name", "Unnamed"),
                    "status": campaign.get("status", "PAUSED"),
                    "objective": campaign.get("objective", ""),
                    "budget": budget,
                    "budget_type": budget_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "bid_strategy": campaign.get("bid_strategy", ""),
                    "targeting": {},
                })

        except APIError as exc:
            logger.error("Meta Ads campaign fetch failed: %s", exc.detail)
            return []

        logger.info("Fetched %d campaigns from Meta Ads account %s", len(campaigns), account_id)
        return campaigns

    @staticmethod
    async def get_insights(
        platform_account: AdPlatformAccount,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Fetch campaign insights from Meta Marketing API.

        Args:
            platform_account: The connected Meta Ads account.
            campaign_id: Campaign ID.
            start_date: Start date.
            end_date: End date.

        Returns:
            List of insight dictionaries.
        """
        url = f"{MetaAdsConfig.BASE_URL}/{campaign_id}/insights"
        params = {
            "fields": ",".join(MetaAdsConfig.INSIGHT_FIELDS),
            "time_range": json.dumps({
                "since": start_date.strftime("%Y-%m-%d"),
                "until": end_date.strftime("%Y-%m-%d"),
            }),
            "time_increment": 1,
        }

        try:
            response = await MetaAdsService._api_request(
                platform_account, "GET", url, params=params
            )
            data = response.get("data", [])
            insights = []
            for row in data:
                spend = Decimal(str(row.get("spend", "0")))
                impressions = int(row.get("impressions", 0) or 0)
                clicks = int(row.get("clicks", 0) or 0)
                conversions = float(row.get("conversions", [{}])[0].get("value", 0) if isinstance(row.get("conversions"), list) else row.get("conversions", 0) or 0)
                conversion_values = row.get("conversion_values", [{}])
                conv_value = Decimal(str(conversion_values[0].get("value", "0")) if isinstance(conversion_values, list) and conversion_values else "0")

                ctr_raw = row.get("ctr")
                cpc_raw = row.get("cpc")
                cost_per_conversion = row.get("cost_per_conversion")
                purchase_roas = row.get("purchase_roas", [{}])
                roas_raw = Decimal(str(purchase_roas[0].get("value", "0")) if isinstance(purchase_roas, list) and purchase_roas else "0")

                # Calculate if API doesn't provide
                ctr = Decimal(str(ctr_raw)) if ctr_raw else (Decimal(str(clicks)) / Decimal(str(impressions)) * Decimal("100") if impressions > 0 else Decimal("0"))
                cpc = Decimal(str(cpc_raw)) if cpc_raw else (spend / Decimal(str(clicks)) if clicks > 0 else Decimal("0"))
                cpa = Decimal(str(cost_per_conversion)) if cost_per_conversion else (spend / Decimal(str(conversions)) if conversions > 0 else Decimal("0"))
                roas = roas_raw if roas_raw > 0 else (conv_value / spend if spend > 0 else Decimal("0"))

                insights.append({
                    "date": datetime.strptime(row.get("date_start", end_date.strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "spend": spend,
                    "cost": spend,
                    "ctr": round(ctr, 4),
                    "cpc": round(cpc, 4),
                    "cost_per_conversion": round(cpa, 4),
                    "conversion_value": conv_value,
                    "roas": round(roas, 4),
                    "reach": int(row.get("reach", 0) or 0),
                    "frequency": Decimal(str(row.get("frequency", "0") or "0")),
                    "raw_data": row,
                })
            return insights
        except APIError as exc:
            logger.error(
                "Meta Ads insights fetch failed for campaign %s: %s",
                campaign_id,
                exc.detail,
            )
            return []

    @staticmethod
    async def get_custom_audiences(platform_account: AdPlatformAccount) -> List[Dict[str, Any]]:
        """Fetch custom audiences from Meta Marketing API.

        Args:
            platform_account: The connected Meta Ads account.

        Returns:
            List of audience dictionaries.
        """
        account_id = platform_account.account_id
        if not account_id.startswith("act_"):
            account_id = f"act_{account_id}"

        url = f"{MetaAdsConfig.BASE_URL}/{account_id}/customaudiences"
        params = {"fields": "id,name,approximate_count,delivery_status,lookalike_spec"}

        try:
            response = await MetaAdsService._api_request(
                platform_account, "GET", url, params=params
            )
            data = response.get("data", [])
            audiences = []
            for audience in data:
                audiences.append({
                    "platform_audience_id": str(audience.get("id", "")),
                    "name": audience.get("name", "Unnamed"),
                    "size_estimate": int(audience.get("approximate_count", 0) or 0),
                    "delivery_status": audience.get("delivery_status", {}),
                    "lookalike_spec": audience.get("lookalike_spec", {}),
                })
            return audiences
        except APIError as exc:
            logger.error("Meta Ads audience fetch failed: %s", exc.detail)
            return []


# =============================================================================
# ROAS Service
# =============================================================================


class ROASService:
    """ROAS (Return on Ad Spend) calculation engine.

    Calculates ROAS from real API data with benchmark comparisons,
    trend analysis, and scoring.
    """

    @staticmethod
    async def calculate_campaign_roas(
        db: AsyncSession,
        campaign_id: int,
        date_range: Optional[DateRangeFilter] = None,
    ) -> Optional[Decimal]:
        """Calculate ROAS for a specific campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Optional date range.

        Returns:
            ROAS as Decimal, or None if no data.
        """
        query = select(
            func.sum(AdMetric.conversion_value).label("total_value"),
            func.sum(AdMetric.cost).label("total_cost"),
        ).where(AdMetric.campaign_id == campaign_id)

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row:
            return None

        total_value = Decimal(str(row.total_value or 0))
        total_cost = Decimal(str(row.total_cost or 0))

        if total_cost <= 0:
            return None

        roas = total_value / total_cost
        return round(roas, 4)

    @staticmethod
    async def calculate_company_roas(
        db: AsyncSession,
        company_id: int,
        date_range: Optional[DateRangeFilter] = None,
        platform: Optional[AdPlatform] = None,
    ) -> Optional[Decimal]:
        """Calculate overall ROAS for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            date_range: Optional date range.
            platform: Filter by platform.

        Returns:
            ROAS as Decimal, or None if no data.
        """
        query = (
            select(
                func.sum(AdMetric.conversion_value).label("total_value"),
                func.sum(AdMetric.cost).label("total_cost"),
            )
            .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
            .where(AdCampaign.company_id == company_id)
        )

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)
        if platform:
            query = query.where(AdCampaign.platform == platform)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row.total_cost or row.total_cost <= 0:
            return None

        roas = Decimal(str(row.total_value or 0)) / Decimal(str(row.total_cost))
        return round(roas, 4)

    @staticmethod
    async def get_roas_trend(
        db: AsyncSession,
        campaign_id: int,
        date_range: DateRangeFilter,
    ) -> List[Dict[str, Any]]:
        """Get daily ROAS trend for a campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Date range.

        Returns:
            List of daily ROAS records.
        """
        query = (
            select(
                AdMetric.date,
                AdMetric.conversion_value,
                AdMetric.cost,
            )
            .where(
                and_(
                    AdMetric.campaign_id == campaign_id,
                    AdMetric.date >= date_range.start_date,
                    AdMetric.date <= date_range.end_date,
                )
            )
            .order_by(AdMetric.date)
        )

        result = await db.execute(query)
        trend = []
        for row in result.all():
            cost = Decimal(str(row.cost or 0))
            value = Decimal(str(row.conversion_value or 0))
            roas = value / cost if cost > 0 else Decimal("0")
            trend.append({
                "date": row.date.isoformat(),
                "roas": round(roas, 4),
                "cost": float(cost),
                "conversion_value": float(value),
            })
        return trend

    @staticmethod
    async def score_roas(roas: Decimal, industry: str = "general") -> Dict[str, Any]:
        """Score ROAS against industry benchmarks.

        Args:
            roas: The ROAS value.
            industry: Industry for benchmark comparison.

        Returns:
            Scoring result with label and color.
        """
        benchmark = Decimal(str(INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])["roas"]))

        if roas >= benchmark * Decimal("1.5"):
            label = "excellent"
            color = "green"
        elif roas >= benchmark:
            label = "good"
            color = "lightgreen"
        elif roas >= Decimal("1.5"):
            label = "acceptable"
            color = "yellow"
        elif roas >= Decimal("1.0"):
            label = "poor"
            color = "orange"
        else:
            label = "critical"
            color = "red"

        return {
            "roas": round(roas, 4),
            "benchmark": float(benchmark),
            "label": label,
            "color": color,
            "vs_benchmark_pct": round(float((roas - benchmark) / benchmark * 100), 2),
        }


# =============================================================================
# CPA Service
# =============================================================================


class CPAService:
    """CPA (Cost Per Acquisition) calculation engine.

    Calculates CPA from real API data with benchmark comparisons,
    trend analysis, and scoring.
    """

    @staticmethod
    async def calculate_campaign_cpa(
        db: AsyncSession,
        campaign_id: int,
        date_range: Optional[DateRangeFilter] = None,
    ) -> Optional[Decimal]:
        """Calculate CPA for a specific campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Optional date range.

        Returns:
            CPA as Decimal, or None if no data.
        """
        query = select(
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversions).label("total_conversions"),
        ).where(AdMetric.campaign_id == campaign_id)

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row:
            return None

        total_cost = Decimal(str(row.total_cost or 0))
        total_conversions = Decimal(str(row.total_conversions or 0))

        if total_conversions <= 0:
            return None

        cpa = total_cost / total_conversions
        return round(cpa, 4)

    @staticmethod
    async def calculate_company_cpa(
        db: AsyncSession,
        company_id: int,
        date_range: Optional[DateRangeFilter] = None,
        platform: Optional[AdPlatform] = None,
    ) -> Optional[Decimal]:
        """Calculate overall CPA for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            date_range: Optional date range.
            platform: Filter by platform.

        Returns:
            CPA as Decimal, or None if no data.
        """
        query = (
            select(
                func.sum(AdMetric.cost).label("total_cost"),
                func.sum(AdMetric.conversions).label("total_conversions"),
            )
            .join(AdCampaign, AdMetric.campaign_id == AdCampaign.id)
            .where(AdCampaign.company_id == company_id)
        )

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)
        if platform:
            query = query.where(AdCampaign.platform == platform)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row.total_conversions or row.total_conversions <= 0:
            return None

        cpa = Decimal(str(row.total_cost or 0)) / Decimal(str(row.total_conversions))
        return round(cpa, 4)

    @staticmethod
    async def get_cpa_trend(
        db: AsyncSession,
        campaign_id: int,
        date_range: DateRangeFilter,
    ) -> List[Dict[str, Any]]:
        """Get daily CPA trend for a campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Date range.

        Returns:
            List of daily CPA records.
        """
        query = (
            select(
                AdMetric.date,
                AdMetric.cost,
                AdMetric.conversions,
            )
            .where(
                and_(
                    AdMetric.campaign_id == campaign_id,
                    AdMetric.date >= date_range.start_date,
                    AdMetric.date <= date_range.end_date,
                )
            )
            .order_by(AdMetric.date)
        )

        result = await db.execute(query)
        trend = []
        for row in result.all():
            cost = Decimal(str(row.cost or 0))
            conversions = Decimal(str(row.conversions or 0))
            cpa = cost / conversions if conversions > 0 else Decimal("0")
            trend.append({
                "date": row.date.isoformat(),
                "cpa": round(cpa, 4),
                "cost": float(cost),
                "conversions": float(conversions),
            })
        return trend

    @staticmethod
    async def score_cpa(cpa: Decimal, industry: str = "general") -> Dict[str, Any]:
        """Score CPA against industry benchmarks.

        Args:
            cpa: The CPA value.
            industry: Industry for benchmark comparison.

        Returns:
            Scoring result with label and color.
        """
        benchmark = Decimal(str(INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])["cpa"]))

        if cpa <= benchmark * Decimal("0.5"):
            label = "excellent"
            color = "green"
        elif cpa <= benchmark * Decimal("0.75"):
            label = "good"
            color = "lightgreen"
        elif cpa <= benchmark:
            label = "acceptable"
            color = "yellow"
        elif cpa <= benchmark * Decimal("1.5"):
            label = "poor"
            color = "orange"
        else:
            label = "critical"
            color = "red"

        return {
            "cpa": round(cpa, 4),
            "benchmark": float(benchmark),
            "label": label,
            "color": color,
            "vs_benchmark_pct": round(float((cpa - benchmark) / benchmark * 100), 2),
        }


# =============================================================================
# CPC/CTR Engine
# =============================================================================


class CPCCTREngine:
    """CPC (Cost Per Click) and CTR (Click-Through Rate) engine.

    Calculates CPC and CTR from real API data with platform-specific
    benchmarks and trend detection.
    """

    @staticmethod
    async def calculate_campaign_ctr(
        db: AsyncSession,
        campaign_id: int,
        date_range: Optional[DateRangeFilter] = None,
    ) -> Optional[Decimal]:
        """Calculate CTR for a specific campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Optional date range.

        Returns:
            CTR as Decimal (%), or None if no data.
        """
        query = select(
            func.sum(AdMetric.impressions).label("total_impressions"),
            func.sum(AdMetric.clicks).label("total_clicks"),
        ).where(AdMetric.campaign_id == campaign_id)

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row.total_impressions or row.total_impressions <= 0:
            return None

        ctr = Decimal(str(row.total_clicks or 0)) / Decimal(str(row.total_impressions)) * Decimal("100")
        return round(ctr, 4)

    @staticmethod
    async def calculate_campaign_cpc(
        db: AsyncSession,
        campaign_id: int,
        date_range: Optional[DateRangeFilter] = None,
    ) -> Optional[Decimal]:
        """Calculate CPC for a specific campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            date_range: Optional date range.

        Returns:
            CPC as Decimal, or None if no data.
        """
        query = select(
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.clicks).label("total_clicks"),
        ).where(AdMetric.campaign_id == campaign_id)

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)

        result = await db.execute(query)
        row = result.one_or_none()

        if not row or not row.total_clicks or row.total_clicks <= 0:
            return None

        cpc = Decimal(str(row.total_cost or 0)) / Decimal(str(row.total_clicks))
        return round(cpc, 4)

    @staticmethod
    async def get_platform_benchmarks(
        platform: AdPlatform,
        industry: str = "general",
    ) -> Dict[str, Any]:
        """Get platform-specific benchmarks for CPC/CTR.

        Args:
            platform: Ad platform.
            industry: Industry for benchmarks.

        Returns:
            Benchmark data dictionary.
        """
        if platform == AdPlatform.GOOGLE_ADS:
            benchmarks = GOOGLE_ADS_BENCHMARKS.get(industry, GOOGLE_ADS_BENCHMARKS["general"])
            return {
                "platform": "google_ads",
                "search_ctr": benchmarks.get("search_ctr", 4.5),
                "display_ctr": benchmarks.get("display_ctr", 0.5),
                "search_cpc": benchmarks.get("search_cpc", 1.25),
                "display_cpc": benchmarks.get("display_cpc", 0.60),
                "quality_score_avg": benchmarks.get("quality_score", 7.3),
            }
        elif platform == AdPlatform.META_ADS:
            benchmarks = META_ADS_BENCHMARKS.get(industry, META_ADS_BENCHMARKS["general"])
            return {
                "platform": "meta_ads",
                "feed_ctr": benchmarks.get("feed_ctr", 1.55),
                "stories_ctr": benchmarks.get("stories_ctr", 0.95),
                "reels_ctr": benchmarks.get("reels_ctr", 0.75),
                "feed_cpc": benchmarks.get("feed_cpc", 0.48),
                "stories_cpc": benchmarks.get("stories_cpc", 0.40),
                "reels_cpc": benchmarks.get("reels_cpc", 0.32),
            }
        return {}

    @staticmethod
    async def detect_ctr_decline(
        db: AsyncSession,
        campaign_id: int,
        lookback_days: int = 14,
    ) -> Dict[str, Any]:
        """Detect CTR decline trend for a campaign.

        Args:
            db: Async database session.
            campaign_id: Campaign ID.
            lookback_days: Days to look back.

        Returns:
            Decline analysis result.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        query = (
            select(AdMetric)
            .where(
                and_(
                    AdMetric.campaign_id == campaign_id,
                    AdMetric.date >= start_date,
                    AdMetric.date <= end_date,
                )
            )
            .order_by(AdMetric.date)
        )

        result = await db.execute(query)
        metrics = result.scalars().all()

        if len(metrics) < 7:
            return {
                "decline_detected": False,
                "reason": "insufficient_data",
                "message": f"Need at least 7 days of data, got {len(metrics)}",
            }

        # Split into early and recent periods
        mid = len(metrics) // 2
        early_metrics = metrics[:mid]
        recent_metrics = metrics[mid:]

        early_impressions = sum(m.impressions for m in early_metrics)
        early_clicks = sum(m.clicks for m in early_metrics)
        recent_impressions = sum(m.impressions for m in recent_metrics)
        recent_clicks = sum(m.clicks for m in recent_metrics)

        early_ctr = (Decimal(str(early_clicks)) / Decimal(str(early_impressions)) * Decimal("100")) if early_impressions > 0 else Decimal("0")
        recent_ctr = (Decimal(str(recent_clicks)) / Decimal(str(recent_impressions)) * Decimal("100")) if recent_impressions > 0 else Decimal("0")

        if early_ctr <= 0:
            return {
                "decline_detected": False,
                "reason": "zero_early_ctr",
                "early_ctr": float(early_ctr),
                "recent_ctr": float(recent_ctr),
            }

        decline_pct = (early_ctr - recent_ctr) / early_ctr

        if decline_pct >= Decimal("0.35"):
            severity = "severe"
        elif decline_pct >= Decimal("0.20"):
            severity = "moderate"
        elif decline_pct >= Decimal("0.10"):
            severity = "mild"
        else:
            return {
                "decline_detected": False,
                "decline_pct": round(float(decline_pct * 100), 2),
                "early_ctr": round(float(early_ctr), 4),
                "recent_ctr": round(float(recent_ctr), 4),
            }

        return {
            "decline_detected": True,
            "severity": severity,
            "decline_pct": round(float(decline_pct * 100), 2),
            "early_ctr": round(float(early_ctr), 4),
            "recent_ctr": round(float(recent_ctr), 4),
            "recommendation": (
                f"CTR declined by {round(float(decline_pct * 100), 1)}%. "
                f"Consider refreshing creative or adjusting targeting."
            ),
        }



# =============================================================================
# Audience Analysis Service
# =============================================================================


class AudienceAnalysisService:
    """Service for audience performance analysis, overlap detection,
    and lookalike audience suggestions.

    Analyzes audience performance metrics, detects targeting overlap
    between audiences, and generates lookalike recommendations.
    """

    @staticmethod
    async def analyze_audience_performance(
        db: AsyncSession,
        audience_id: int,
        date_range: Optional[DateRangeFilter] = None,
    ) -> Dict[str, Any]:
        """Analyze performance metrics for a specific audience.

        Args:
            db: Async database session.
            audience_id: Audience ID.
            date_range: Optional date range filter.

        Returns:
            Performance analysis data.
        """
        audience = await db.get(AdAudience, audience_id)
        if not audience:
            raise NotFoundError(detail=f"Audience {audience_id} not found")

        # Get campaigns using this audience's targeting
        campaigns_query = select(AdCampaign).where(
            and_(
                AdCampaign.company_id == audience.company_id,
                AdCampaign.targeting.contains({"audience_id": audience_id}),
            )
        )
        result = await db.execute(campaigns_query)
        campaigns = result.scalars().all()

        if not campaigns:
            return {
                "audience_id": audience_id,
                "audience_name": audience.name,
                "status": "no_data",
                "message": "No campaigns found using this audience",
            }

        campaign_ids = [c.id for c in campaigns]

        query = select(
            func.sum(AdMetric.impressions).label("total_impressions"),
            func.sum(AdMetric.clicks).label("total_clicks"),
            func.sum(AdMetric.conversions).label("total_conversions"),
            func.sum(AdMetric.cost).label("total_cost"),
            func.sum(AdMetric.conversion_value).label("total_value"),
        ).where(AdMetric.campaign_id.in_(campaign_ids))

        if date_range and date_range.start_date:
            query = query.where(AdMetric.date >= date_range.start_date)
        if date_range and date_range.end_date:
            query = query.where(AdMetric.date <= date_range.end_date)

        result = await db.execute(query)
        row = result.one_or_none()

        impressions = int(row.total_impressions or 0) if row else 0
        clicks = int(row.total_clicks or 0) if row else 0
        conversions = float(row.total_conversions or 0) if row else 0
        cost = Decimal(str(row.total_cost or 0)) if row else Decimal("0")
        value = Decimal(str(row.total_value or 0)) if row else Decimal("0")

        ctr = (Decimal(str(clicks)) / Decimal(str(impressions)) * Decimal("100")) if impressions > 0 else None
        cpa = cost / Decimal(str(conversions)) if conversions > 0 else None
        roas = value / cost if cost > 0 else None

        return {
            "audience_id": audience_id,
            "audience_name": audience.name,
            "audience_type": audience.audience_type.value,
            "platform": audience.platform.value,
            "size_estimate": audience.size_estimate,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "cost": float(cost),
            "ctr": round(ctr, 4) if ctr else None,
            "cpa": round(cpa, 4) if cpa else None,
            "roas": round(roas, 4) if roas else None,
            "performance_score": round(audience.performance_score, 2) if audience.performance_score else None,
        }

    @staticmethod
    async def detect_audience_overlap(
        db: AsyncSession,
        company_id: int,
    ) -> List[Dict[str, Any]]:
        """Detect overlap between audiences for a company.

        Analyzes audience targeting specs to identify potential overlap
        and provides recommendations for deduplication.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            List of overlap detection results.
        """
        query = select(AdAudience).where(AdAudience.company_id == company_id)
        result = await db.execute(query)
        audiences = result.scalars().all()

        if len(audiences) < 2:
            return []

        overlaps = []
        audience_list = list(audiences)

        for i in range(len(audience_list)):
            for j in range(i + 1, len(audience_list)):
                a1 = audience_list[i]
                a2 = audience_list[j]

                overlap_pct = await AudienceAnalysisService._calculate_overlap(
                    a1.targeting_spec or {},
                    a2.targeting_spec or {},
                )

                if overlap_pct > Decimal("0.15"):  # Only report >15% overlap
                    if overlap_pct > Decimal("0.50"):
                        recommendation = (
                            f"High overlap detected ({round(overlap_pct * 100, 1)}%). "
                            f"Consider merging audiences or using exclusion targeting."
                        )
                    elif overlap_pct > Decimal("0.30"):
                        recommendation = (
                            f"Moderate overlap ({round(overlap_pct * 100, 1)}%). "
                            f"Consider differentiating targeting criteria."
                        )
                    else:
                        recommendation = (
                            f"Mild overlap ({round(overlap_pct * 100, 1)}%). "
                            f"Monitor performance to avoid audience fatigue."
                        )

                    overlaps.append({
                        "audience_id_1": a1.id,
                        "audience_name_1": a1.name,
                        "audience_id_2": a2.id,
                        "audience_name_2": a2.name,
                        "overlap_percentage": round(overlap_pct * 100, 2),
                        "recommendation": recommendation,
                    })

        # Sort by overlap percentage descending
        overlaps.sort(key=lambda x: x["overlap_percentage"], reverse=True)
        return overlaps

    @staticmethod
    async def _calculate_overlap(
        spec1: Dict[str, Any],
        spec2: Dict[str, Any],
    ) -> Decimal:
        """Calculate overlap percentage between two targeting specs.

        Uses Jaccard similarity on targeting criteria to estimate overlap.

        Args:
            spec1: First targeting spec.
            spec2: Second targeting spec.

        Returns:
            Overlap percentage as Decimal (0-1).
        """
        # Extract targeting dimensions
        dims1 = AudienceAnalysisService._extract_targeting_dimensions(spec1)
        dims2 = AudienceAnalysisService._extract_targeting_dimensions(spec2)

        if not dims1 or not dims2:
            return Decimal("0")

        # Calculate Jaccard similarity for each dimension
        total_similarity = Decimal("0")
        dimension_count = 0

        all_keys = set(dims1.keys()) | set(dims2.keys())
        for key in all_keys:
            vals1 = set(dims1.get(key, []))
            vals2 = set(dims2.get(key, []))

            if vals1 and vals2:
                intersection = len(vals1 & vals2)
                union = len(vals1 | vals2)
                if union > 0:
                    total_similarity += Decimal(str(intersection)) / Decimal(str(union))
                    dimension_count += 1

        if dimension_count == 0:
            return Decimal("0")

        return total_similarity / Decimal(str(dimension_count))

    @staticmethod
    def _extract_targeting_dimensions(spec: Dict[str, Any]) -> Dict[str, List[str]]:
        """Extract targeting dimensions from a spec for comparison.

        Args:
            spec: Targeting specification.

        Returns:
            Dictionary of dimension names to values.
        """
        dimensions = {}

        if "geo_locations" in spec:
            locations = spec["geo_locations"]
            cities = locations.get("cities", [])
            countries = locations.get("countries", [])
            dimensions["location"] = [
                c.get("key", str(c)) for c in cities + countries
            ]

        if "age_min" in spec and "age_max" in spec:
            age_min = spec["age_min"]
            age_max = spec["age_max"]
            dimensions["age"] = [f"{age_min}-{age_max}"]

        if "genders" in spec:
            dimensions["gender"] = [str(g) for g in spec["genders"]]

        if "interests" in spec:
            dimensions["interests"] = [
                i.get("id", str(i)) for i in spec["interests"]
            ]

        if "behaviors" in spec:
            dimensions["behaviors"] = [
                b.get("id", str(b)) for b in spec["behaviors"]
            ]

        if "custom_audiences" in spec:
            dimensions["custom_audiences"] = [
                ca.get("id", str(ca)) for ca in spec["custom_audiences"]
            ]

        if "income" in spec:
            dimensions["income"] = spec["income"]

        return dimensions

    @staticmethod
    async def suggest_lookalike_audiences(
        db: AsyncSession,
        company_id: int,
    ) -> List[Dict[str, Any]]:
        """Suggest lookalike audiences based on high-performing custom audiences.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            List of lookalike suggestions.
        """
        # Find high-performing custom audiences
        query = select(AdAudience).where(
            and_(
                AdAudience.company_id == company_id,
                AdAudience.audience_type.in_([
                    AudienceType.CUSTOM,
                    AudienceType.ENGAGEMENT,
                ]),
                AdAudience.size_estimate != None,
            )
        )
        result = await db.execute(query)
        audiences = result.scalars().all()

        suggestions = []
        for audience in audiences:
            if not audience.size_estimate or audience.size_estimate < 100:
                continue

            # Determine suggested lookalike size tier based on source size
            if audience.size_estimate < 1000:
                size_tier = "1%"
                estimated_reach = audience.size_estimate * 20
            elif audience.size_estimate < 10000:
                size_tier = "1-3%"
                estimated_reach = audience.size_estimate * 15
            else:
                size_tier = "1-5%"
                estimated_reach = audience.size_estimate * 10

            confidence = Decimal("0.75")
            if audience.performance_score and audience.performance_score >= 70:
                confidence = Decimal("0.90")
            elif audience.performance_score and audience.performance_score >= 50:
                confidence = Decimal("0.80")

            suggestions.append({
                "source_audience_id": audience.id,
                "source_audience_name": audience.name,
                "suggested_platform": audience.platform.value,
                "suggested_size": size_tier,
                "estimated_reach": estimated_reach,
                "confidence": round(confidence, 3),
            })

        # Sort by confidence descending
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions


# =============================================================================
# Budget Recommendation Service
# =============================================================================


class BudgetRecommendationService:
    """Service for AI-powered budget recommendations.

    Analyzes campaign performance data and generates intelligent
    budget increase/decrease recommendations with expected outcomes.
    NO auto-change: recommendations are advisory only.
    """

    @staticmethod
    async def generate_recommendations(
        db: AsyncSession,
        company_id: int,
        industry: str = "general",
    ) -> List[AdBudgetRecommendation]:
        """Generate budget recommendations for all campaigns of a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            industry: Industry for benchmark comparison.

        Returns:
            List of budget recommendation model instances.
        """
        from datetime import timedelta
        from app.ads.constants import BudgetConfig

        end = date.today()
        start = end - timedelta(days=BudgetConfig.MIN_PERFORMANCE_DAYS)
        date_range = DateRangeFilter(start_date=start, end_date=end)

        # Get all campaigns for the company
        query = select(AdCampaign).where(AdCampaign.company_id == company_id)
        result = await db.execute(query)
        campaigns = result.scalars().all()

        recommendations = []
        for campaign in campaigns:
            rec = await BudgetRecommendationService._analyze_campaign(
                db, campaign, date_range, industry
            )
            if rec:
                recommendations.append(rec)

        # Persist recommendations to database
        if recommendations:
            db.add_all(recommendations)
            await db.commit()

        return recommendations

    @staticmethod
    async def _analyze_campaign(
        db: AsyncSession,
        campaign: AdCampaign,
        date_range: DateRangeFilter,
        industry: str,
    ) -> Optional[AdBudgetRecommendation]:
        """Analyze a single campaign and generate budget recommendation.

        Args:
            db: Async database session.
            campaign: Campaign to analyze.
            date_range: Date range for analysis.
            industry: Industry for benchmarks.

        Returns:
            Budget recommendation or None if no recommendation.
        """
        from app.ads.constants import BudgetConfig

        roas = await ROASService.calculate_campaign_roas(db, campaign.id, date_range)
        cpa = await CPAService.calculate_campaign_cpa(db, campaign.id, date_range)
        current_budget = Decimal(str(campaign.budget or 0))

        if current_budget < Decimal(str(BudgetConfig.MIN_BUDGET)):
            return None

        benchmark = INDUSTRY_BENCHMARKS.get(industry, INDUSTRY_BENCHMARKS["general"])
        benchmark_roas = Decimal(str(benchmark["roas"]))
        benchmark_cpa = Decimal(str(benchmark["cpa"]))

        # Decision logic
        recommended_budget = current_budget
        reason = ""
        expected_improvement = None
        confidence = Decimal("0.5")

        if roas and roas >= Decimal(str(BudgetConfig.ROAS_INCREASE)):
            # High ROAS - recommend budget increase
            multiplier = min(
                Decimal(str(BudgetConfig.MAX_INCREASE_MULTIPLIER)),
                Decimal("1.5") + (roas - benchmark_roas) * Decimal("0.1"),
            )
            recommended_budget = current_budget * min(
                multiplier, Decimal("2.0")
            )
            reason = (
                f"Campaign ROAS ({round(roas, 2)}x) is significantly above "
                f"benchmark ({benchmark_roas}x). Increasing budget should "
                f"scale positive results while maintaining efficiency."
            )
            expected_improvement = Decimal(str(BudgetConfig.EXPECTED_HIGH))
            confidence = Decimal("0.85") if roas > benchmark_roas * Decimal("1.5") else Decimal("0.70")

        elif roas and roas < Decimal(str(BudgetConfig.ROAS_DECREASE)):
            # Low ROAS - recommend budget decrease
            multiplier = max(
                Decimal(str(BudgetConfig.MAX_DECREASE_MULTIPLIER)),
                Decimal("0.5"),
            )
            recommended_budget = current_budget * multiplier
            reason = (
                f"Campaign ROAS ({round(roas, 2)}x) is below break-even. "
                f"Reducing budget to optimize before further investment."
            )
            expected_improvement = Decimal(str(BudgetConfig.EXPECTED_LOW))
            confidence = Decimal("0.70")

        elif cpa and cpa > benchmark_cpa * Decimal(str(BudgetConfig.CPA_INCREASE_MULTIPLIER)):
            # High CPA - recommend budget decrease
            recommended_budget = current_budget * Decimal("0.75")
            reason = (
                f"CPA ({round(cpa, 2)}) is {round((cpa / benchmark_cpa - 1) * 100, 1)}% above "
                f"industry benchmark ({benchmark_cpa}). Reducing budget to optimize targeting."
            )
            expected_improvement = Decimal(str(BudgetConfig.EXPECTED_LOW))
            confidence = Decimal("0.65")

        elif cpa and cpa < benchmark_cpa * Decimal(str(BudgetConfig.CPA_DECREASE_MULTIPLIER)):
            # Low CPA - recommend budget increase
            recommended_budget = current_budget * Decimal("1.25")
            reason = (
                f"CPA ({round(cpa, 2)}) is {round((1 - cpa / benchmark_cpa) * 100, 1)}% below "
                f"industry benchmark ({benchmark_cpa}). Opportunity to scale efficiently."
            )
            expected_improvement = Decimal(str(BudgetConfig.EXPECTED_MEDIUM))
            confidence = Decimal("0.75")

        elif roas and Decimal(str(BudgetConfig.ROAS_MAINTAIN_LOW)) <= roas <= Decimal(str(BudgetConfig.ROAS_MAINTAIN_HIGH)):
            # Moderate ROAS - maintain budget
            return None

        if recommended_budget == current_budget:
            return None

        # Round budget to 2 decimal places
        recommended_budget = round(recommended_budget, 2)

        recommendation = AdBudgetRecommendation(
            company_id=campaign.company_id,
            branch_id=campaign.branch_id,
            platform=campaign.platform,
            campaign_id=campaign.id,
            current_budget=current_budget,
            recommended_budget=recommended_budget,
            reason=reason,
            expected_improvement=expected_improvement,
            confidence_score=min(Decimal("1.0"), max(Decimal("0.1"), confidence)),
            applied=False,
        )

        return recommendation

    @staticmethod
    async def list_recommendations(
        db: AsyncSession,
        company_id: int,
        applied: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdBudgetRecommendation]:
        """List budget recommendations for a company.

        Args:
            db: Async database session.
            company_id: Company ID.
            applied: Filter by applied status.
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of budget recommendations.
        """
        query = select(AdBudgetRecommendation).where(
            AdBudgetRecommendation.company_id == company_id
        ).order_by(desc(AdBudgetRecommendation.created_at))

        if applied is not None:
            query = query.where(AdBudgetRecommendation.applied == applied)

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def apply_recommendation(
        db: AsyncSession,
        recommendation_id: int,
        company_id: int,
    ) -> AdBudgetRecommendation:
        """Mark a budget recommendation as applied.

        Note: This only marks the recommendation as applied in the DB.
        It does NOT automatically change the actual campaign budget.
        The user must manually apply changes through the platform.

        Args:
            db: Async database session.
            recommendation_id: Recommendation ID.
            company_id: Company ID.

        Returns:
            Updated recommendation.
        """
        query = select(AdBudgetRecommendation).where(
            and_(
                AdBudgetRecommendation.id == recommendation_id,
                AdBudgetRecommendation.company_id == company_id,
            )
        )
        result = await db.execute(query)
        recommendation = result.scalar_one_or_none()

        if not recommendation:
            raise NotFoundError(detail=f"Recommendation {recommendation_id} not found")

        recommendation.applied = True
        await db.commit()
        await db.refresh(recommendation)

        return recommendation


# =============================================================================
# Creative Fatigue Service
# =============================================================================


class CreativeFatigueService:
    """Service for detecting creative fatigue and suggesting refresh timing.

    Analyzes creative performance trends to detect declining CTR,
    increasing frequency, and overall fatigue indicators.
    """

    @staticmethod
    async def analyze_creative_fatigue(
        db: AsyncSession,
        creative_id: int,
    ) -> Dict[str, Any]:
        """Analyze a creative for fatigue indicators.

        Args:
            db: Async database session.
            creative_id: Creative ID.

        Returns:
            Fatigue analysis results.
        """
        from app.ads.constants import FatigueConfig

        creative = await db.get(AdCreative, creative_id)
        if not creative:
            raise NotFoundError(detail=f"Creative {creative_id} not found")

        # Get metrics for the creative
        query = (
            select(AdMetric)
            .where(AdMetric.creative_id == creative_id)
            .order_by(AdMetric.date)
        )
        result = await db.execute(query)
        metrics = result.scalars().all()

        if not metrics:
            return {
                "creative_id": creative_id,
                "creative_name": creative.name,
                "fatigue_score": Decimal("100"),
                "fatigue_level": "fresh",
                "message": "No metrics data available for analysis",
            }

        total_impressions = sum(m.impressions for m in metrics)
        total_clicks = sum(m.clicks for m in metrics)

        # Check minimum data thresholds
        if total_impressions < FatigueConfig.MIN_IMPRESSIONS:
            return {
                "creative_id": creative_id,
                "creative_name": creative.name,
                "fatigue_score": Decimal("100"),
                "fatigue_level": "fresh",
                "message": f"Insufficient impressions ({total_impressions}) for fatigue analysis. "
                           f"Minimum required: {FatigueConfig.MIN_IMPRESSIONS}",
            }

        days_active = (metrics[-1].date - metrics[0].date).days + 1
        if days_active < FatigueConfig.MIN_DAYS:
            return {
                "creative_id": creative_id,
                "creative_name": creative.name,
                "fatigue_score": Decimal("100"),
                "fatigue_level": "fresh",
                "message": f"Insufficient data history ({days_active} days). "
                           f"Minimum required: {FatigueConfig.MIN_DAYS} days",
            }

        # Calculate fatigue score components
        ctr_drop = await CreativeFatigueService._calculate_ctr_drop(metrics)
        frequency = await CreativeFatigueService._calculate_frequency(metrics)
        age_score = await CreativeFatigueService._calculate_age_score(days_active, creative.creative_type)
        conversion_drop = await CreativeFatigueService._calculate_conversion_drop(metrics)

        # Weighted fatigue score (100 = fresh, 0 = exhausted)
        fatigue_score = (
            Decimal("100")
            - ctr_drop * Decimal(str(FatigueConfig.WEIGHT_CTR_DROP))
            - frequency * Decimal(str(FatigueConfig.WEIGHT_FREQUENCY))
            - age_score * Decimal(str(FatigueConfig.WEIGHT_AGE_DAYS))
            - conversion_drop * Decimal(str(FatigueConfig.WEIGHT_CONVERSION_DROP))
        )

        fatigue_score = max(Decimal("0"), min(Decimal("100"), fatigue_score))

        # Determine fatigue level
        if fatigue_score >= FatigueConfig.SCORE_FRESH:
            level = "fresh"
            recommendation = "Creative is performing well. Continue monitoring."
        elif fatigue_score >= FatigueConfig.SCORE_MILD_FATIGUE:
            level = "mild"
            recommendation = (
                f"Mild fatigue detected. Consider refreshing creative elements "
                f"within the next 7-14 days."
            )
        elif fatigue_score >= FatigueConfig.SCORE_MODERATE_FATIGUE:
            level = "moderate"
            recommendation = (
                f"Moderate fatigue detected. Schedule creative refresh "
                f"within the next 3-7 days."
            )
        else:
            level = "severe"
            recommendation = (
                f"Severe creative fatigue. Immediate refresh recommended "
                f"to maintain performance."
            )

        # Calculate refresh date
        refresh_interval = FatigueConfig.REFRESH_INTERVAL_IMAGE
        if creative.creative_type == CreativeType.VIDEO:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_VIDEO
        elif creative.creative_type == CreativeType.CAROUSEL:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_CAROUSEL
        elif creative.creative_type == CreativeType.STORIES:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_STORIES

        launch_date = metrics[0].date
        recommended_refresh_date = launch_date + timedelta(days=refresh_interval)

        # Adjust based on fatigue
        if level == "mild":
            recommended_refresh_date = date.today() + timedelta(days=14)
        elif level == "moderate":
            recommended_refresh_date = date.today() + timedelta(days=7)
        elif level == "severe":
            recommended_refresh_date = date.today() + timedelta(days=3)

        return {
            "creative_id": creative_id,
            "creative_name": creative.name,
            "fatigue_score": round(fatigue_score, 2),
            "fatigue_level": level,
            "days_since_launch": days_active,
            "total_impressions": total_impressions,
            "frequency": round(frequency, 2),
            "ctr_trend": round(-ctr_drop / Decimal(str(FatigueConfig.WEIGHT_CTR_DROP)) * 100, 2) if ctr_drop > 0 else None,
            "conversion_trend": round(-conversion_drop / Decimal(str(FatigueConfig.WEIGHT_CONVERSION_DROP)) * 100, 2) if conversion_drop > 0 else None,
            "recommendation": recommendation,
            "recommended_refresh_date": recommended_refresh_date,
        }

    @staticmethod
    async def _calculate_ctr_drop(metrics: List[AdMetric]) -> Decimal:
        """Calculate CTR decline percentage.

        Compares early period CTR to recent period CTR.

        Args:
            metrics: List of daily metrics.

        Returns:
            CTR drop weighted score (0-100).
        """
        from app.ads.constants import FatigueConfig

        if len(metrics) < FatigueConfig.MIN_DAYS * 2:
            return Decimal("0")

        mid = len(metrics) // 2
        early_metrics = metrics[:mid]
        recent_metrics = metrics[mid:]

        early_impressions = sum(m.impressions for m in early_metrics)
        early_clicks = sum(m.clicks for m in early_metrics)
        recent_impressions = sum(m.impressions for m in recent_metrics)
        recent_clicks = sum(m.clicks for m in recent_metrics)

        if early_impressions == 0 or recent_impressions == 0:
            return Decimal("0")

        early_ctr = Decimal(str(early_clicks)) / Decimal(str(early_impressions))
        recent_ctr = Decimal(str(recent_clicks)) / Decimal(str(recent_impressions))

        if early_ctr == 0:
            return Decimal("0")

        drop = (early_ctr - recent_ctr) / early_ctr
        drop = max(Decimal("0"), drop)

        # Scale to 0-100
        return min(Decimal("100"), drop * Decimal("100"))

    @staticmethod
    async def _calculate_frequency(metrics: List[AdMetric]) -> Decimal:
        """Calculate frequency score based on impressions.

        Args:
            metrics: List of daily metrics.

        Returns:
            Frequency score (0-100).
        """
        from app.ads.constants import FatigueConfig

        total_impressions = sum(m.impressions for m in metrics)

        if total_impressions < FatigueConfig.MIN_IMPRESSIONS:
            return Decimal("0")

        # Estimate frequency (impressions / estimated unique reach)
        # Using a simplified model
        avg_daily_impressions = total_impressions / max(len(metrics), 1)

        if avg_daily_impressions < 500:
            return Decimal("0")
        elif avg_daily_impressions < 1000:
            return Decimal("15")
        elif avg_daily_impressions < 5000:
            return Decimal("30")
        elif avg_daily_impressions < 10000:
            return Decimal("50")
        else:
            return Decimal("75")

    @staticmethod
    async def _calculate_age_score(days_active: int, creative_type: CreativeType) -> Decimal:
        """Calculate age-based fatigue score.

        Args:
            days_active: Number of days the creative has been active.
            creative_type: Type of creative.

        Returns:
            Age score (0-100).
        """
        from app.ads.constants import FatigueConfig

        refresh_interval = FatigueConfig.REFRESH_INTERVAL_IMAGE
        if creative_type == CreativeType.VIDEO:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_VIDEO
        elif creative_type == CreativeType.CAROUSEL:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_CAROUSEL
        elif creative_type == CreativeType.STORIES:
            refresh_interval = FatigueConfig.REFRESH_INTERVAL_STORIES

        if days_active <= refresh_interval // 2:
            return Decimal("0")
        elif days_active <= refresh_interval:
            return Decimal("20")
        elif days_active <= refresh_interval * 2:
            return Decimal("50")
        elif days_active <= refresh_interval * 3:
            return Decimal("75")
        else:
            return Decimal("100")

    @staticmethod
    async def _calculate_conversion_drop(metrics: List[AdMetric]) -> Decimal:
        """Calculate conversion rate decline.

        Args:
            metrics: List of daily metrics.

        Returns:
            Conversion drop score (0-100).
        """
        from app.ads.constants import FatigueConfig

        if len(metrics) < FatigueConfig.MIN_DAYS * 2:
            return Decimal("0")

        mid = len(metrics) // 2
        early_metrics = metrics[:mid]
        recent_metrics = metrics[mid:]

        early_clicks = sum(m.clicks for m in early_metrics)
        early_conversions = sum(m.conversions for m in early_metrics)
        recent_clicks = sum(m.clicks for m in recent_metrics)
        recent_conversions = sum(m.conversions for m in recent_metrics)

        if early_clicks == 0 or recent_clicks == 0:
            return Decimal("0")

        early_cvr = Decimal(str(early_conversions)) / Decimal(str(early_clicks))
        recent_cvr = Decimal(str(recent_conversions)) / Decimal(str(recent_clicks))

        if early_cvr == 0:
            return Decimal("0")

        drop = (early_cvr - recent_cvr) / early_cvr
        drop = max(Decimal("0"), drop)

        return min(Decimal("100"), drop * Decimal("100"))

    @staticmethod
    async def get_fatigue_alerts(
        db: AsyncSession,
        company_id: int,
    ) -> List[Dict[str, Any]]:
        """Get fatigue alerts for all creatives of a company.

        Args:
            db: Async database session.
            company_id: Company ID.

        Returns:
            List of creatives needing attention.
        """
        query = select(AdCreative).where(AdCreative.company_id == company_id)
        result = await db.execute(query)
        creatives = result.scalars().all()

        alerts = []
        for creative in creatives:
            analysis = await CreativeFatigueService.analyze_creative_fatigue(db, creative.id)
            if analysis["fatigue_level"] in ("moderate", "severe"):
                alerts.append({
                    "creative_id": creative.id,
                    "creative_name": creative.name,
                    "campaign_id": creative.campaign_id,
                    "fatigue_level": analysis["fatigue_level"],
                    "fatigue_score": analysis["fatigue_score"],
                    "recommended_action": analysis["recommendation"],
                    "refresh_by": analysis.get("recommended_refresh_date"),
                })

        # Sort by fatigue score ascending (most fatigued first)
        alerts.sort(key=lambda x: x["fatigue_score"])
        return alerts


# =============================================================================
# Local Campaign Service
# =============================================================================


class LocalCampaignService:
    """Service for geo-targeted local campaign recommendations.

    Generates location-specific campaign recommendations for
    restaurants, franchises, and multi-location businesses.
    """

    @staticmethod
    async def generate_local_recommendations(
        db: AsyncSession,
        company_id: int,
        industry: str = "restaurants",
    ) -> Dict[str, Any]:
        """Generate local campaign recommendations for all branches.

        Args:
            db: Async database session.
            company_id: Company ID.
            industry: Industry type for recommendations.

        Returns:
            Recommendations grouped by branch.
        """
        from app.branches.models import Branch
        from app.ads.constants import LocalCampaignConfig

        query = select(Branch).where(Branch.company_id == company_id)
        result = await db.execute(query)
        branches = result.scalars().all()

        if not branches:
            return {
                "company_id": company_id,
                "industry": industry,
                "recommendations": [],
                "message": "No branches found for this company",
            }

        recommendations = []
        for branch in branches:
            rec = await LocalCampaignService._generate_branch_recommendation(
                branch, industry
            )
            if rec:
                recommendations.append(rec)

        return {
            "company_id": company_id,
            "industry": industry,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def _generate_branch_recommendation(
        branch,
        industry: str,
    ) -> Optional[Dict[str, Any]]:
        """Generate recommendation for a single branch.

        Args:
            branch: Branch model instance.
            industry: Industry type.

        Returns:
            Recommendation dictionary or None.
        """
        from app.ads.constants import LocalCampaignConfig

        # Build location data
        location = {
            "address": getattr(branch, "address", None),
            "city": getattr(branch, "city", None),
            "state": getattr(branch, "state", None),
            "zip_code": getattr(branch, "zip_code", None),
            "latitude": getattr(branch, "latitude", None),
            "longitude": getattr(branch, "longitude", None),
            "country": getattr(branch, "country", "US"),
        }

        # Determine radius and budget based on industry and location
        radius = LocalCampaignConfig.DEFAULT_RADIUS_MILES
        if industry == "restaurants":
            radius = 5.0
            daily_budget = Decimal("30.00")
        elif industry == "franchise":
            radius = 10.0
            daily_budget = Decimal("50.00")
        elif industry == "retail":
            radius = 8.0
            daily_budget = Decimal("40.00")
        else:
            radius = 5.0
            daily_budget = Decimal("25.00")

        # Generate bid modifiers based on industry
        bid_modifiers = {}
        if industry == "restaurants":
            bid_modifiers = {
                "early_morning": Decimal(str(LocalCampaignConfig.BID_MODIFIER_EARLY_MORNING)),
                "morning": Decimal(str(LocalCampaignConfig.BID_MODIFIER_MORNING)),
                "lunch": Decimal(str(LocalCampaignConfig.BID_MODIFIER_LUNCH)),
                "afternoon": Decimal(str(LocalCampaignConfig.BID_MODIFIER_AFTERNOON)),
                "dinner": Decimal(str(LocalCampaignConfig.BID_MODIFIER_DINNER)),
                "evening": Decimal(str(LocalCampaignConfig.BID_MODIFIER_EVENING)),
                "night": Decimal(str(LocalCampaignConfig.BID_MODIFIER_NIGHT)),
            }
        elif industry == "franchise":
            bid_modifiers = {
                "early_morning": Decimal("0.6"),
                "morning": Decimal("0.9"),
                "lunch": Decimal("1.1"),
                "afternoon": Decimal("1.0"),
                "dinner": Decimal("1.15"),
                "evening": Decimal("0.8"),
                "night": Decimal("0.4"),
            }
        else:
            bid_modifiers = {
                "early_morning": Decimal(str(LocalCampaignConfig.BID_MODIFIER_EARLY_MORNING)),
                "morning": Decimal(str(LocalCampaignConfig.BID_MODIFIER_MORNING)),
                "lunch": Decimal(str(LocalCampaignConfig.BID_MODIFIER_LUNCH)),
                "afternoon": Decimal(str(LocalCampaignConfig.BID_MODIFIER_AFTERNOON)),
                "dinner": Decimal(str(LocalCampaignConfig.BID_MODIFIER_DINNER)),
                "evening": Decimal(str(LocalCampaignConfig.BID_MODIFIER_EVENING)),
                "night": Decimal(str(LocalCampaignConfig.BID_MODIFIER_NIGHT)),
            }

        # Generate keywords
        if industry == "restaurants":
            keywords = LocalCampaignConfig.RESTAURANT_KEYWORDS.copy()
            branch_name = getattr(branch, "name", "")
            if branch_name:
                keywords.extend([
                    f"{branch_name} near me",
                    f"{branch_name} hours",
                    f"{branch_name} menu",
                ])
        elif industry == "franchise":
            keywords = LocalCampaignConfig.FRANCHISE_KEYWORDS.copy()
            branch_name = getattr(branch, "name", "")
            if branch_name:
                keywords.extend([
                    f"{branch_name} near me",
                    f"{branch_name} store",
                    f"{branch_name} deals",
                ])
        else:
            keywords = ["near me", "local", "open now"]
            branch_name = getattr(branch, "name", "")
            if branch_name:
                keywords.append(f"{branch_name} near me")

        # Estimate reach based on radius and location
        estimated_reach = int(5000 * radius * radius * 3.14 / 78.5)

        return {
            "branch_id": branch.id,
            "branch_name": getattr(branch, "name", f"Branch {branch.id}"),
            "location": {k: v for k, v in location.items() if v is not None},
            "radius_miles": radius,
            "daily_budget": daily_budget,
            "bid_modifiers": {k: float(v) for k, v in bid_modifiers.items()},
            "suggested_keywords": keywords,
            "expected_reach": estimated_reach,
            "confidence_score": Decimal("0.78"),
        }


# =============================================================================
# Data Sync Service
# =============================================================================


class DataSyncService:
    """Service for synchronizing data from ad platforms.

    Handles campaign sync, metrics sync, and audience sync
    for connected ad platform accounts.
    """

    @staticmethod
    async def sync_platform(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
        date_range_days: int = SyncConfig.MAX_SYNC_LOOKBACK_DAYS,
        sync_campaigns: bool = True,
        sync_metrics: bool = True,
        sync_audiences: bool = False,
    ) -> Dict[str, Any]:
        """Sync data from an ad platform account.

        Args:
            db: Async database session.
            platform_account: The connected platform account.
            date_range_days: Days of data to sync.
            sync_campaigns: Whether to sync campaigns.
            sync_metrics: Whether to sync metrics.
            sync_audiences: Whether to sync audiences.

        Returns:
            Sync results summary.
        """
        started_at = datetime.utcnow()
        campaigns_synced = 0
        metrics_synced = 0
        audiences_synced = 0
        errors = []

        try:
            if platform_account.platform == AdPlatform.GOOGLE_ADS:
                if sync_campaigns:
                    campaigns_synced = await DataSyncService._sync_google_campaigns(
                        db, platform_account
                    )
                if sync_metrics:
                    metrics_synced = await DataSyncService._sync_google_metrics(
                        db, platform_account, date_range_days
                    )
                if sync_audiences:
                    audiences_synced = await DataSyncService._sync_google_audiences(
                        db, platform_account
                    )

            elif platform_account.platform == AdPlatform.META_ADS:
                if sync_campaigns:
                    campaigns_synced = await DataSyncService._sync_meta_campaigns(
                        db, platform_account
                    )
                if sync_metrics:
                    metrics_synced = await DataSyncService._sync_meta_metrics(
                        db, platform_account, date_range_days
                    )
                if sync_audiences:
                    audiences_synced = await DataSyncService._sync_meta_audiences(
                        db, platform_account
                    )

            # Update last sync timestamp
            platform_account.last_sync_at = datetime.utcnow()
            platform_account.status = PlatformStatus.ACTIVE
            await db.commit()

            status = "success"

        except Exception as exc:
            logger.error(
                "Platform sync failed for account %s: %s",
                platform_account.id,
                str(exc),
            )
            platform_account.status = PlatformStatus.ERROR
            await db.commit()
            status = "failed"
            errors.append(str(exc))

        return {
            "platform": platform_account.platform.value,
            "status": status,
            "campaigns_synced": campaigns_synced,
            "metrics_synced": metrics_synced,
            "audiences_synced": audiences_synced,
            "errors": errors,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def _sync_google_campaigns(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
    ) -> int:
        """Sync Google Ads campaigns.

        Args:
            db: Async database session.
            platform_account: Google Ads account.

        Returns:
            Number of campaigns synced.
        """
        campaigns = await GoogleAdsService.get_campaigns(platform_account)
        synced = 0

        for campaign_data in campaigns:
            # Check if campaign exists
            query = select(AdCampaign).where(
                and_(
                    AdCampaign.company_id == platform_account.company_id,
                    AdCampaign.platform == AdPlatform.GOOGLE_ADS,
                    AdCampaign.platform_campaign_id == campaign_data["platform_campaign_id"],
                )
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.name = campaign_data["name"]
                existing.status = CampaignStatus(campaign_data["status"])
                existing.budget = campaign_data["budget"]
                existing.start_date = campaign_data.get("start_date")
                existing.end_date = campaign_data.get("end_date")
                existing.bid_strategy = campaign_data.get("bid_strategy")
                existing.updated_at = datetime.utcnow()
            else:
                new_campaign = AdCampaign(
                    company_id=platform_account.company_id,
                    branch_id=platform_account.branch_id,
                    platform=AdPlatform.GOOGLE_ADS,
                    platform_campaign_id=campaign_data["platform_campaign_id"],
                    name=campaign_data["name"],
                    objective=campaign_data.get("objective"),
                    status=CampaignStatus(campaign_data["status"]),
                    budget=campaign_data["budget"],
                    budget_type=campaign_data.get("budget_type", "daily"),
                    start_date=campaign_data.get("start_date"),
                    end_date=campaign_data.get("end_date"),
                    targeting=campaign_data.get("targeting", {}),
                    bid_strategy=campaign_data.get("bid_strategy"),
                    ai_optimized=False,
                )
                db.add(new_campaign)

            synced += 1

        await db.commit()
        return synced

    @staticmethod
    async def _sync_google_metrics(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
        days: int,
    ) -> int:
        """Sync Google Ads metrics.

        Args:
            db: Async database session.
            platform_account: Google Ads account.
            days: Days of data to sync.

        Returns:
            Number of metric records synced.
        """
        end = date.today()
        start = end - timedelta(days=days)

        metrics = await GoogleAdsService.get_metrics(
            platform_account, start, end
        )
        synced = 0

        for metric_data in metrics:
            # Find campaign ID
            query = select(AdCampaign.id).where(
                and_(
                    AdCampaign.company_id == platform_account.company_id,
                    AdCampaign.platform == AdPlatform.GOOGLE_ADS,
                    AdCampaign.platform_campaign_id == metric_data["platform_campaign_id"],
                )
            )
            result = await db.execute(query)
            campaign_id = result.scalar_one_or_none()

            if not campaign_id:
                continue

            # Upsert metric record
            existing_query = select(AdMetric).where(
                and_(
                    AdMetric.campaign_id == campaign_id,
                    AdMetric.adset_id.is_(None),
                    AdMetric.creative_id.is_(None),
                    AdMetric.date == metric_data["date"],
                )
            )
            result = await db.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.impressions = metric_data["impressions"]
                existing.clicks = metric_data["clicks"]
                existing.conversions = metric_data["conversions"]
                existing.cost = metric_data["cost"]
                existing.ctr = metric_data.get("ctr")
                existing.cpc = metric_data.get("cpc")
                existing.cpa = metric_data.get("cpa")
                existing.roas = metric_data.get("roas")
                existing.conversion_value = metric_data.get("conversion_value", Decimal("0"))
            else:
                new_metric = AdMetric(
                    campaign_id=campaign_id,
                    adset_id=None,
                    creative_id=None,
                    date=metric_data["date"],
                    impressions=metric_data["impressions"],
                    clicks=metric_data["clicks"],
                    conversions=metric_data["conversions"],
                    cost=metric_data["cost"],
                    ctr=metric_data.get("ctr"),
                    cpc=metric_data.get("cpc"),
                    cpa=metric_data.get("cpa"),
                    roas=metric_data.get("roas"),
                    conversion_value=metric_data.get("conversion_value", Decimal("0")),
                    raw_data=metric_data.get("raw_data"),
                )
                db.add(new_metric)

            synced += 1

        await db.commit()
        return synced

    @staticmethod
    async def _sync_google_audiences(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
    ) -> int:
        """Sync Google Ads audiences (placeholder - requires Audience API).

        Google Ads audience sync requires the Audience API which
        requires additional OAuth scopes. Returns 501 to indicate
        this feature is not yet implemented.

        Args:
            db: Async database session.
            platform_account: Google Ads account.

        Returns:
            0 (not implemented).

        Raises:
            APIError: 501 Not Implemented.
        """
        raise APIError(
            detail="Google Ads audience sync requires additional OAuth scopes. "
                   "This feature is planned for a future release.",
            status_code=501,
        )

    @staticmethod
    async def _sync_meta_campaigns(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
    ) -> int:
        """Sync Meta Ads campaigns.

        Args:
            db: Async database session.
            platform_account: Meta Ads account.

        Returns:
            Number of campaigns synced.
        """
        campaigns = await MetaAdsService.get_campaigns(platform_account)
        synced = 0

        for campaign_data in campaigns:
            status = campaign_data.get("status", "ACTIVE")
            if status in ("ARCHIVED", "DELETED"):
                status = "REMOVED"

            query = select(AdCampaign).where(
                and_(
                    AdCampaign.company_id == platform_account.company_id,
                    AdCampaign.platform == AdPlatform.META_ADS,
                    AdCampaign.platform_campaign_id == campaign_data["platform_campaign_id"],
                )
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.name = campaign_data["name"]
                existing.status = CampaignStatus(status)
                existing.budget = campaign_data["budget"]
                existing.budget_type = campaign_data.get("budget_type", "daily")
                existing.start_date = campaign_data.get("start_date")
                existing.end_date = campaign_data.get("end_date")
                existing.bid_strategy = campaign_data.get("bid_strategy")
                existing.updated_at = datetime.utcnow()
            else:
                new_campaign = AdCampaign(
                    company_id=platform_account.company_id,
                    branch_id=platform_account.branch_id,
                    platform=AdPlatform.META_ADS,
                    platform_campaign_id=campaign_data["platform_campaign_id"],
                    name=campaign_data["name"],
                    objective=campaign_data.get("objective"),
                    status=CampaignStatus(status),
                    budget=campaign_data["budget"],
                    budget_type=campaign_data.get("budget_type", "daily"),
                    start_date=campaign_data.get("start_date"),
                    end_date=campaign_data.get("end_date"),
                    targeting=campaign_data.get("targeting", {}),
                    bid_strategy=campaign_data.get("bid_strategy"),
                    ai_optimized=False,
                )
                db.add(new_campaign)

            synced += 1

        await db.commit()
        return synced

    @staticmethod
    async def _sync_meta_metrics(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
        days: int,
    ) -> int:
        """Sync Meta Ads metrics.

        Args:
            db: Async database session.
            platform_account: Meta Ads account.
            days: Days of data to sync.

        Returns:
            Number of metric records synced.
        """
        end = date.today()
        start = end - timedelta(days=days)

        synced = 0

        # Get all campaigns for this account
        query = select(AdCampaign).where(
            and_(
                AdCampaign.company_id == platform_account.company_id,
                AdCampaign.platform == AdPlatform.META_ADS,
            )
        )
        result = await db.execute(query)
        campaigns = result.scalars().all()

        for campaign in campaigns:
            try:
                insights = await MetaAdsService.get_insights(
                    platform_account,
                    campaign.platform_campaign_id,
                    start,
                    end,
                )

                for insight in insights:
                    # Upsert metric
                    existing_query = select(AdMetric).where(
                        and_(
                            AdMetric.campaign_id == campaign.id,
                            AdMetric.adset_id.is_(None),
                            AdMetric.creative_id.is_(None),
                            AdMetric.date == insight["date"],
                        )
                    )
                    result = await db.execute(existing_query)
                    existing = result.scalar_one_or_none()

                    impressions = int(insight.get("impressions", 0))
                    clicks = int(insight.get("clicks", 0))
                    cost = Decimal(str(insight.get("cost", 0)))
                    conv_value = Decimal(str(insight.get("conversion_value", 0)))

                    if existing:
                        existing.impressions = impressions
                        existing.clicks = clicks
                        existing.cost = cost
                        existing.ctr = insight.get("ctr")
                        existing.cpc = insight.get("cpc")
                        existing.conversion_value = conv_value
                        existing.roas = conv_value / cost if cost > 0 else Decimal("0")
                    else:
                        new_metric = AdMetric(
                            campaign_id=campaign.id,
                            date=insight["date"],
                            impressions=impressions,
                            clicks=clicks,
                            conversions=0,
                            cost=cost,
                            ctr=insight.get("ctr"),
                            cpc=insight.get("cpc"),
                            conversion_value=conv_value,
                            roas=conv_value / cost if cost > 0 else Decimal("0"),
                        )
                        db.add(new_metric)

                    synced += 1

            except Exception as exc:
                logger.warning(
                    "Failed to sync metrics for campaign %s: %s",
                    campaign.id,
                    str(exc),
                )

        await db.commit()
        return synced

    @staticmethod
    async def _sync_meta_audiences(
        db: AsyncSession,
        platform_account: AdPlatformAccount,
    ) -> int:
        """Sync Meta Ads audiences.

        Args:
            db: Async database session.
            platform_account: Meta Ads account.

        Returns:
            Number of audiences synced.
        """
        audiences = await MetaAdsService.get_custom_audiences(platform_account)
        synced = 0

        for audience_data in audiences:
            query = select(AdAudience).where(
                and_(
                    AdAudience.company_id == platform_account.company_id,
                    AdAudience.platform == AdPlatform.META_ADS,
                    AdAudience.platform_audience_id == audience_data["platform_audience_id"],
                )
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.name = audience_data["name"]
                existing.size_estimate = audience_data.get("size_estimate")
                existing.updated_at = datetime.utcnow()
            else:
                new_audience = AdAudience(
                    company_id=platform_account.company_id,
                    branch_id=platform_account.branch_id,
                    platform=AdPlatform.META_ADS,
                    name=audience_data["name"],
                    audience_type=AudienceType.CUSTOM,
                    size_estimate=audience_data.get("size_estimate"),
                    targeting_spec={},
                    platform_audience_id=audience_data["platform_audience_id"],
                )
                db.add(new_audience)

            synced += 1

        await db.commit()
        return synced
