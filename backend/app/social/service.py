"""Service layer and API clients for the social media integration module.

Provides:
- SocialAccountService: CRUD and credential management for connected accounts
- PostService: Content creation, scheduling, and publishing
- CommentService: Comment sync, sentiment analysis, reply management
- MessageService: DM/conversation sync and replies
- AnalyticsService: Metrics aggregation and trend analysis
- CompetitorService: Competitor tracking and comparison
- WebhookService: Webhook reception and processing
- Platform API Clients: Instagram, Meta/Facebook, TikTok, WhatsApp, Telegram, Google Maps

All API clients use async httpx with exponential backoff retry, rate limiting,
and automatic token refresh. Credentials are encrypted at rest using AES-256-GCM.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar, Union, cast

import httpx
from fastapi import Request
from sqlalchemy import and_, asc, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import NotFoundError, ValidationError
from app.utils.encryption import decrypt_api_credentials, encrypt_api_credentials

from .models import (
    AccountStatus,
    CommentSentiment,
    CommentStatus,
    PublishingQueue as ConversationQueue,
    HashtagIntelligence,
    MessageDirection,
    MessageSentiment,
    MessageStatus,
    PostStatus,
    PublishingQueue,
    SocialAccount,
    SocialAnalytic,
    SocialComment,
    SocialCompetitor,
    SocialListening,
    SocialMessage,
    SocialPlatform,
    SocialPost,
    SocialWebhook,
)
from .schemas import (
    AnalyticsDashboard,
    CommentReplyRequest,
    MessageReplyRequest,
    SocialAccountCreate,
    SocialAccountUpdate,
    SocialAnalyticsCreate,
    SocialCommentCreate,
    SocialCommentUpdate,
    SocialCompetitorCreate,
    SocialCompetitorUpdate,
    SocialMessageCreate,
    SocialPostCreate,
    SocialPostUpdate,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """Token bucket rate limiter for API calls per platform.

    Uses in-memory token buckets with configurable rates per platform.
    """

    _instance: Optional[RateLimiter] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> RateLimiter:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._buckets: Dict[str, Dict[str, Any]] = {}
            cls._instance._default_rates = {
                "instagram": {"requests": 200, "window": 3600},  # 200/hour
                "facebook": {"requests": 200, "window": 3600},  # 200/hour
                "tiktok": {"requests": 100, "window": 3600},  # 100/hour
                "whatsapp": {"requests": 80, "window": 3600},  # 80/hour
                "telegram": {"requests": 30, "window": 1},  # 30/sec
                "google_maps": {"requests": 100, "window": 86400},  # 100/day
            }
        return cls._instance

    def _get_bucket_key(self, platform: str, account_id: str) -> str:
        return f"{platform}:{account_id}"

    def _get_rate(self, platform: str) -> Dict[str, Any]:
        return self._default_rates.get(platform, {"requests": 100, "window": 3600})

    async def acquire(self, platform: str, account_id: str = "default") -> bool:
        """Acquire a rate limit token. Returns True if allowed, False if rate limited."""
        key = self._get_bucket_key(platform, account_id)
        now = time.monotonic()
        rate = self._get_rate(platform)
        requests_per_window = rate["requests"]
        window_seconds = rate["window"]

        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": float(requests_per_window - 1),
                "last_update": now,
            }
            return True

        bucket = self._buckets[key]
        elapsed = now - bucket["last_update"]
        tokens_to_add = elapsed * (requests_per_window / window_seconds)
        bucket["tokens"] = min(requests_per_window, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False

    async def wait_for_token(self, platform: str, account_id: str = "default") -> None:
        """Block until a rate limit token is available."""
        while not await self.acquire(platform, account_id):
            rate = self._get_rate(platform)
            wait_time = rate["window"] / rate["requests"]
            await asyncio.sleep(min(wait_time, 1.0))


# =============================================================================
# Retry Decorator
# =============================================================================


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException),
):
    """Decorator that adds exponential backoff retry to async functions.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exceptions: Tuple of exception types to catch and retry.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        break
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs: %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
            raise last_exception

        return wrapper

    return decorator


# =============================================================================
# Credential Manager
# =============================================================================


class CredentialManager:
    """Encrypts and decrypts social media API credentials.

    All tokens are encrypted at rest using AES-256-GCM.
    """

    @staticmethod
    def encrypt_tokens(access_token: str, refresh_token: Optional[str] = None) -> Dict[str, str]:
        """Encrypt access and refresh tokens.

        Args:
            access_token: Plaintext access token.
            refresh_token: Optional plaintext refresh token.

        Returns:
            Dictionary with encrypted token strings.
        """
        result: Dict[str, str] = {}
        result["access_token"] = encrypt_api_credentials({"token": access_token})
        if refresh_token:
            result["refresh_token"] = encrypt_api_credentials({"token": refresh_token})
        return result

    @staticmethod
    def decrypt_access_token(encrypted: str) -> str:
        """Decrypt an access token.

        Args:
            encrypted: Encrypted token string.

        Returns:
            Plaintext access token.
        """
        decrypted = decrypt_api_credentials(encrypted)
        return decrypted.get("token", "")

    @staticmethod
    def decrypt_refresh_token(encrypted: str) -> str:
        """Decrypt a refresh token.

        Args:
            encrypted: Encrypted token string.

        Returns:
            Plaintext refresh token.
        """
        decrypted = decrypt_api_credentials(encrypted)
        return decrypted.get("token", "")


# =============================================================================
# Base API Client
# =============================================================================


class BaseAPIClient(ABC):
    """Abstract base class for all social media API clients.

    Provides common functionality: HTTP client management, rate limiting,
    retry logic, request signing, and token handling.
    """

    def __init__(
        self,
        platform: str,
        base_url: str,
        access_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.platform = platform
        self.base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def set_access_token(self, token: str) -> None:
        """Update the access token."""
        self._access_token = token

    def _get_auth_header(self) -> Dict[str, str]:
        """Get the authorization header."""
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        account_id: str = "default",
    ) -> Dict[str, Any]:
        """Make an HTTP request with rate limiting and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API endpoint path.
            params: Query parameters.
            json_data: JSON request body.
            headers: Additional headers.
            files: Multipart files.
            account_id: Account identifier for rate limiting.

        Returns:
            Parsed JSON response.

        Raises:
            httpx.HTTPStatusError: On HTTP error responses.
            httpx.ConnectError: On connection failures.
        """
        await self._rate_limiter.wait_for_token(self.platform, account_id)
        client = await self._get_client()

        request_headers = self._get_auth_header()
        if headers:
            request_headers.update(headers)

        try:
            response = await client.request(
                method=method.upper(),
                url=path,
                params=params,
                json=json_data,
                headers=request_headers,
                files=files,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %d from %s %s: %s",
                exc.response.status_code,
                method.upper(),
                path,
                exc.response.text[:500],
            )
            raise

    async def get(self, path: str, *, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for GET requests."""
        return await self._request("GET", path, params=params, **kwargs)

    async def post(self, path: str, *, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for POST requests."""
        return await self._request("POST", path, json_data=json_data, **kwargs)

    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch current account information. Must be implemented by subclasses."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh the access token. Must be implemented by subclasses."""
        pass


# =============================================================================
# Instagram Client (Basic Display + Graph API)
# =============================================================================


class InstagramClient(BaseAPIClient):
    """Async client for Instagram Basic Display API and Instagram Graph API.

    Supports: account info, media posting, comment management, insights.
    Uses Graph API for business/creator accounts, Basic Display for personal.

    References:
        https://developers.facebook.com/docs/instagram-api
        https://developers.facebook.com/docs/instagram-basic-display-api
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        instagram_account_id: Optional[str] = None,
    ):
        super().__init__(
            platform="instagram",
            base_url="https://graph.instagram.com",
            access_token=access_token,
        )
        self._graph_base = "https://graph.facebook.com/v18.0"
        self.instagram_account_id = instagram_account_id
        self._graph_client: Optional[httpx.AsyncClient] = None

    async def _get_graph_client(self) -> httpx.AsyncClient:
        """Get or create the Facebook Graph API HTTP client."""
        if self._graph_client is None or self._graph_client.is_closed:
            self._graph_client = httpx.AsyncClient(
                base_url=self._graph_base,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"Accept": "application/json"},
            )
        return self._graph_client

    async def close(self) -> None:
        """Close all HTTP clients."""
        await super().close()
        if self._graph_client and not self._graph_client.is_closed:
            await self._graph_client.aclose()
            self._graph_client = None

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch Instagram account info.

        Returns:
            Account metadata including username, followers, media count.
        """
        if self.instagram_account_id:
            # Graph API path
            params = {
                "fields": "id,username,account_type,media_count,followers_count",
                "access_token": self._access_token,
            }
            return await self.get(f"/{self.instagram_account_id}", params=params)
        # Basic Display
        params = {
            "fields": "id,username,account_type,media_count",
            "access_token": self._access_token,
        }
        return await self.get("/me", params=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_media_list(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent media items.

        Args:
            limit: Maximum number of media items to return.

        Returns:
            List of media objects with id, caption, media_type, timestamp.
        """
        account_id = self.instagram_account_id or "me"
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": limit,
            "access_token": self._access_token,
        }
        result = await self.get(f"/{account_id}/media", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_media_comments(self, media_id: str) -> List[Dict[str, Any]]:
        """Fetch comments on a media item.

        Args:
            media_id: Instagram media ID.

        Returns:
            List of comment objects.
        """
        params = {
            "fields": "id,username,text,timestamp,like_count,replies",
            "access_token": self._access_token,
        }
        result = await self.get(f"/{media_id}/comments", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def post_comment_reply(self, comment_id: str, message: str) -> Dict[str, Any]:
        """Reply to a comment on Instagram.

        Args:
            comment_id: The comment ID to reply to.
            message: Reply text.

        Returns:
            API response with reply ID.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for comment replies")
        params = {
            "message": message,
            "access_token": self._access_token,
        }
        client = await self._get_graph_client()
        response = await client.post(
            f"/{comment_id}/replies",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_insights(self, metric_period: str = "day") -> Dict[str, Any]:
        """Fetch account insights/metrics.

        Args:
            metric_period: Period for metrics (day, week, days_28, lifetime).

        Returns:
            Insights data including impressions, reach, profile_views, follower_growth.
        """
        if not self.instagram_account_id:
            return {}
        metrics = [
            "impressions",
            "reach",
            "profile_views",
            "follower_count",
            "email_contacts",
            "phone_call_clicks",
            "text_message_clicks",
            "website_clicks",
        ]
        params = {
            "metric": ",".join(metrics),
            "period": metric_period,
            "access_token": self._access_token,
        }
        return await self.get(f"/{self.instagram_account_id}/insights", params=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def create_container(
        self,
        image_url: str,
        caption: str,
        media_type: str = "IMAGE",
        is_carousel: bool = False,
        share_to_feed: bool = True,
    ) -> Dict[str, Any]:
        """Create a media container for publishing (Graph API).

        Args:
            image_url: Publicly accessible URL of the media to publish.
            caption: Post caption text.
            media_type: Type of media (IMAGE, VIDEO, REELS, STORIES, CAROUSEL).
            is_carousel: Whether this is a carousel item.
            share_to_feed: Whether to share to feed (for stories/reels).

        Returns:
            Container ID for status checking/publishing.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for publishing")
        json_data: Dict[str, Any] = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self._access_token,
        }
        if media_type == "VIDEO":
            json_data["media_type"] = "VIDEO"
            json_data["video_url"] = image_url
            del json_data["image_url"]
        elif media_type == "REELS":
            json_data["media_type"] = "REELS"
            json_data["video_url"] = image_url
            json_data["share_to_feed"] = share_to_feed
            del json_data["image_url"]
        elif media_type == "STORIES":
            json_data["media_type"] = "STORIES"
            json_data["image_url"] = image_url
        elif is_carousel or media_type == "CAROUSEL":
            json_data["media_type"] = "CAROUSEL"

        return await self.post(f"/{self.instagram_account_id}/media", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def create_carousel_container(
        self,
        children: List[str],
        caption: str,
    ) -> Dict[str, Any]:
        """Create a carousel container from existing media container IDs.

        Args:
            children: List of media container IDs to include in the carousel.
            caption: Post caption text.

        Returns:
            Carousel container ID.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for publishing")
        json_data = {
            "children": ",".join(children),
            "caption": caption,
            "media_type": "CAROUSEL",
            "access_token": self._access_token,
        }
        return await self.post(f"/{self.instagram_account_id}/media", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def publish_container(self, creation_id: str) -> Dict[str, Any]:
        """Publish a created media container.

        Args:
            creation_id: Container ID from create_container.

        Returns:
            Published media ID.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for publishing")
        json_data = {
            "creation_id": creation_id,
            "access_token": self._access_token,
        }
        return await self.post(f"/{self.instagram_account_id}/media_publish", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_container_status(self, creation_id: str) -> Dict[str, Any]:
        """Check the status of a media container.

        Args:
            creation_id: Container ID.

        Returns:
            Status info with status_code (FINISHED, IN_PROGRESS, ERROR).
        """
        params = {
            "fields": "status_code,status",
            "access_token": self._access_token,
        }
        return await self.get(f"/{creation_id}", params=params)

    # ------------------------------------------------------------------
    # Instagram DM (Graph API via Facebook)
    # ------------------------------------------------------------------

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_conversations(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch Instagram DM conversations via the Graph API.

        Args:
            limit: Maximum conversations to return.

        Returns:
            List of conversation objects with participants and last message.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for DM access")
        params = {
            "fields": (
                "id,participants,messages{"
                "id,created_time,from,to,message,sticker attachments"
                "},updated_time"
            ),
            "limit": limit,
            "access_token": self._access_token,
        }
        client = await self._get_graph_client()
        response = await client.get(
            "/me/conversations",
            params=params,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_conversation_messages(
        self, conversation_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch messages from a specific Instagram conversation.

        Args:
            conversation_id: The conversation/thread ID.
            limit: Maximum messages to return.

        Returns:
            List of message objects.
        """
        params = {
            "fields": "id,created_time,from,to,message,sticker,attachments",
            "limit": limit,
            "access_token": self._access_token,
        }
        client = await self._get_graph_client()
        response = await client.get(
            f"/{conversation_id}/messages",
            params=params,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_dm_message(self, recipient_id: str, message: str) -> Dict[str, Any]:
        """Send an Instagram DM via the Graph API.

        Args:
            recipient_id: The Instagram-scoped user ID of the recipient.
            message: Message text to send.

        Returns:
            API response with message ID.
        """
        if not self.instagram_account_id:
            raise ValueError("Graph API account ID required for sending DMs")
        json_data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
        }
        headers = {"Authorization": f"Bearer {self._access_token}"}
        client = await self._get_graph_client()
        response = await client.post(
            "/me/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh the Instagram Basic Display access token.

        Args:
            refresh_token: Current refresh token.

        Returns:
            Dictionary with new access_token and expires_in.
        """
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": refresh_token,
        }
        result = await self.get("/refresh_access_token", params=params)
        return {
            "access_token": result.get("access_token", ""),
            "expires_in": str(result.get("expires_in", 0)),
        }


# =============================================================================
# Meta/Facebook Client
# =============================================================================


class MetaClient(BaseAPIClient):
    """Async client for Facebook Graph API.

    Supports: page management, post creation, comment handling, insights.

    References:
        https://developers.facebook.com/docs/graph-api
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        page_id: Optional[str] = None,
    ):
        super().__init__(
            platform="facebook",
            base_url="https://graph.facebook.com/v18.0",
            access_token=access_token,
        )
        self.page_id = page_id

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch page information.

        Returns:
            Page metadata including name, fan count, category.
        """
        page_id = self.page_id or "me"
        params = {
            "fields": "id,name,fan_count,category,link,about",
            "access_token": self._access_token,
        }
        return await self.get(f"/{page_id}", params=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_page_posts(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent page posts.

        Args:
            limit: Maximum number of posts.

        Returns:
            List of post objects.
        """
        page_id = self.page_id or "me"
        params = {
            "fields": "id,message,created_time,likes.summary(true),comments.summary(true),shares",
            "limit": limit,
            "access_token": self._access_token,
        }
        result = await self.get(f"/{page_id}/posts", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def create_page_post(
        self,
        message: str,
        link: Optional[str] = None,
        scheduled_time: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new page post.

        Args:
            message: Post text content.
            link: Optional URL to share.
            scheduled_time: Unix timestamp for scheduled publish.

        Returns:
            API response with post ID.
        """
        page_id = self.page_id or "me"
        params: Dict[str, Any] = {
            "message": message,
            "access_token": self._access_token,
        }
        if link:
            params["link"] = link
        if scheduled_time:
            params["scheduled_publish_time"] = scheduled_time
            params["published"] = False
        return await self.post(f"/{page_id}/feed", json_data=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_post_comments(self, post_id: str) -> List[Dict[str, Any]]:
        """Fetch comments on a post.

        Args:
            post_id: Facebook post ID.

        Returns:
            List of comment objects.
        """
        params = {
            "fields": "id,message,from,created_time,like_count,comment_count",
            "access_token": self._access_token,
        }
        result = await self.get(f"/{post_id}/comments", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def reply_to_comment(
        self, comment_id: str, message: str
    ) -> Dict[str, Any]:
        """Reply to a Facebook comment.

        Args:
            comment_id: Comment ID to reply to.
            message: Reply text.

        Returns:
            API response.
        """
        params = {
            "message": message,
            "access_token": self._access_token,
        }
        return await self.post(f"/{comment_id}/comments", params=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_page_insights(
        self, metric_period: str = "day"
    ) -> Dict[str, Any]:
        """Fetch page insights.

        Args:
            metric_period: Metric time period.

        Returns:
            Page insights including impressions, reach, engagements.
        """
        page_id = self.page_id or "me"
        metrics = [
            "page_impressions",
            "page_impressions_unique",
            "page_engaged_users",
            "page_actions_post_reactions_total",
            "page_fan_adds",
            "page_fan_removes",
        ]
        params = {
            "metric": ",".join(metrics),
            "period": metric_period,
            "access_token": self._access_token,
        }
        return await self.get(f"/{page_id}/insights", params=params)

    # ------------------------------------------------------------------
    # Facebook Messenger API
    # ------------------------------------------------------------------

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_messenger_conversations(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch Facebook Messenger conversations for a page.

        Args:
            limit: Maximum conversations to return.

        Returns:
            List of conversation objects with participants and last message.
        """
        page_id = self.page_id or "me"
        params = {
            "fields": (
                "id,participants,messages{"
                "id,created_time,from,to,message,sticker,attachments"
                "},updated_time,unread_count"
            ),
            "limit": limit,
            "access_token": self._access_token,
        }
        result = await self.get(f"/{page_id}/conversations", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_messenger_messages(
        self, conversation_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch messages from a Facebook Messenger conversation.

        Args:
            conversation_id: The conversation/thread ID.
            limit: Maximum messages to return.

        Returns:
            List of message objects.
        """
        params = {
            "fields": "id,created_time,from,to,message,sticker,attachments",
            "limit": limit,
            "access_token": self._access_token,
        }
        result = await self.get(f"/{conversation_id}/messages", params=params)
        return result.get("data", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_messenger_message(self, recipient_id: str, message: str) -> Dict[str, Any]:
        """Send a Facebook Messenger message via the Graph API.

        Args:
            recipient_id: The PSID (Page-scoped ID) of the recipient.
            message: Message text to send.

        Returns:
            API response with message ID.
        """
        json_data = {
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "messaging_type": "RESPONSE",
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            "/me/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def mark_messenger_read(self, sender_id: str) -> Dict[str, Any]:
        """Mark messages from a sender as read (send read receipt).

        Args:
            sender_id: The sender's PSID.

        Returns:
            API response.
        """
        json_data = {
            "recipient": {"id": sender_id},
            "sender_action": "mark_seen",
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            "/me/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh Facebook access token.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New access token info with access_token, expires_in.
        """
        fb_app_id = getattr(settings, "FACEBOOK_APP_ID", "") or getattr(settings, "META_APP_ID", "")
        fb_app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "") or getattr(settings, "META_APP_SECRET", "")
        if not fb_app_id or not fb_app_secret:
            logger.error("Facebook App ID or Secret not configured in settings")
            raise ValueError("Facebook App ID and Secret must be configured in settings")

        params = {
            "grant_type": "fb_exchange_token",
            "client_id": fb_app_id,
            "client_secret": fb_app_secret,
            "fb_exchange_token": refresh_token,
        }
        result = await self.get("/oauth/access_token", params=params)
        return {
            "access_token": result.get("access_token", ""),
            "expires_in": str(result.get("expires_in", 0)),
        }


# =============================================================================
# TikTok Client
# =============================================================================


class TikTokClient(BaseAPIClient):
    """Async client for TikTok API (Research API + Content Sharing).

    Supports: user info, video upload, comment management, analytics.

    References:
        https://developers.tiktok.com/doc/research-api-specs-query-videos
        https://developers.tiktok.com/doc/tiktok-api-v2-video-upload
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        open_id: Optional[str] = None,
    ):
        super().__init__(
            platform="tiktok",
            base_url="https://open.tiktokapis.com/v2",
            access_token=access_token,
        )
        self.open_id = open_id

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch TikTok user info.

        Returns:
            User metadata including display_name, follower_count, likes_count.
        """
        headers = self._get_auth_header()
        params = {"fields": "display_name,bio_description,avatar_url,follower_count,following_count,likes_count"}
        return await self.get("/user/info/", params=params, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def list_videos(self, cursor: int = 0, max_count: int = 20) -> Dict[str, Any]:
        """Fetch user's published videos.

        Args:
            cursor: Pagination cursor.
            max_count: Maximum videos to return.

        Returns:
            Video list with has_more flag.
        """
        headers = self._get_auth_header()
        params = {"cursor": cursor, "max_count": max_count}
        return await self.get("/video/list/", params=params, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_video_comments(
        self, video_id: str, cursor: int = 0, max_count: int = 50
    ) -> Dict[str, Any]:
        """Fetch comments on a video.

        Args:
            video_id: TikTok video ID.
            cursor: Pagination cursor.
            max_count: Maximum comments.

        Returns:
            Comments list with has_more flag.
        """
        headers = self._get_auth_header()
        params = {"video_id": video_id, "cursor": cursor, "max_count": max_count}
        return await self.get("/video/comment/list/", params=params, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def reply_to_comment(
        self, video_id: str, comment_id: str, text: str
    ) -> Dict[str, Any]:
        """Reply to a TikTok comment.

        Args:
            video_id: Video ID.
            comment_id: Comment ID to reply to.
            text: Reply text.

        Returns:
            API response.
        """
        headers = self._get_auth_header()
        json_data = {
            "video_id": video_id,
            "comment_id": comment_id,
            "text": text,
        }
        return await self.post("/video/comment/reply/", json_data=json_data, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def init_video_upload(
        self,
        source_info: Dict[str, Any],
        post_info: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Initialize a video upload session.

        Args:
            source_info: Source video information (source, video_size, chunk_size, total_chunk_count).
            post_info: Optional post metadata (title, privacy_level, disable_duet, etc.).

        Returns:
            Upload URL and publish ID.
        """
        headers = self._get_auth_header()
        json_data = {"source_info": source_info}
        if post_info:
            json_data["post_info"] = post_info
        return await self.post("/post/publish/inbox/video/init/", json_data=json_data, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def query_video_info(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Query video info via TikTok Research API.

        Args:
            filters: Query filters (video_ids, region_code, etc.).

        Returns:
            Video data with metrics.
        """
        headers = self._get_auth_header()
        json_data = {"filters": filters}
        return await self.post("/research/video/query/", json_data=json_data, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_video_analytics(
        self, video_ids: List[str], fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Fetch analytics for specific videos.

        Args:
            video_ids: List of video IDs to fetch analytics for.
            fields: Optional list of metric fields to retrieve.

        Returns:
            Video analytics data.
        """
        if not fields:
            fields = [
                "share_count", "comment_count", "like_count", "view_count",
                "reach_count", "video_duration", "profile_region",
            ]
        headers = self._get_auth_header()
        json_data = {
            "filters": {"video_ids": video_ids},
            "fields": fields,
        }
        return await self.post("/research/video/query/", json_data=json_data, headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_creator_analytics(self) -> Dict[str, Any]:
        """Fetch creator account analytics.

        Returns:
            Creator analytics including followers, profile views, video views.
        """
        headers = self._get_auth_header()
        return await self.get("/research/creator/query/", headers=headers)

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh TikTok access token.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New token info.
        """
        client_key = getattr(settings, "TIKTOK_CLIENT_KEY", "")
        client_secret = getattr(settings, "TIKTOK_CLIENT_SECRET", "")
        if not client_key or not client_secret:
            logger.error("TikTok Client Key or Secret not configured in settings")
            raise ValueError("TikTok Client Key and Secret must be configured in settings")

        params = {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        client = await self._get_client()
        response = await client.post(
            "/oauth/token/",
            json=params,
        )
        response.raise_for_status()
        result = response.json()
        data = result.get("data", {})
        return {
            "access_token": data.get("access_token", ""),
            "expires_in": str(data.get("expires_in", 0)),
            "refresh_token": data.get("refresh_token", ""),
            "refresh_expires_in": str(data.get("refresh_expires_in", 0)),
            "open_id": data.get("open_id", ""),
        }


# =============================================================================
# WhatsApp Business Client
# =============================================================================


class WhatsAppClient(BaseAPIClient):
    """Async client for WhatsApp Business API (Cloud API).

    Supports: message sending (text, image, template), webhook handling,
    conversation management.

    References:
        https://developers.facebook.com/docs/whatsapp/cloud-api
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
    ):
        super().__init__(
            platform="whatsapp",
            base_url="https://graph.facebook.com/v18.0",
            access_token=access_token,
        )
        self.phone_number_id = phone_number_id

    def _get_phone_path(self) -> str:
        """Get the API path for the phone number ID."""
        return f"/{self.phone_number_id or 'me'}"

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch WhatsApp business account info.

        Returns:
            Account metadata.
        """
        params = {"access_token": self._access_token}
        return await self.get(self._get_phone_path(), params=params)

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_text_message(
        self, to: str, body: str, preview_url: bool = False
    ) -> Dict[str, Any]:
        """Send a text message via WhatsApp.

        Args:
            to: Recipient phone number (E.164 format).
            body: Message text.
            preview_url: Whether to show URL previews.

        Returns:
            Message send status and ID.
        """
        json_data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        components: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send a template message.

        Args:
            to: Recipient phone number.
            template_name: Template name.
            language_code: Language code.
            components: Template component parameters.

        Returns:
            Message send status.
        """
        json_data = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            json_data["template"]["components"] = components
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_image_message(
        self, to: str, image_url: str, caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an image message via WhatsApp.

        Args:
            to: Recipient phone number (E.164 format).
            image_url: Public URL of the image.
            caption: Optional caption text.

        Returns:
            Message send status and ID.
        """
        json_data: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url},
        }
        if caption:
            json_data["image"]["caption"] = caption
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_document_message(
        self, to: str, document_url: str, caption: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a document message via WhatsApp.

        Args:
            to: Recipient phone number (E.164 format).
            document_url: Public URL of the document.
            caption: Optional caption text.
            filename: Optional filename.

        Returns:
            Message send status and ID.
        """
        json_data: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": {"link": document_url},
        }
        if caption:
            json_data["document"]["caption"] = caption
        if filename:
            json_data["document"]["filename"] = filename
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_interactive_message(
        self,
        to: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an interactive button message via WhatsApp.

        Args:
            to: Recipient phone number (E.164 format).
            body_text: Main body text.
            buttons: List of button dicts with 'id' and 'title' keys (max 3).
            header_text: Optional header text.
            footer_text: Optional footer text.

        Returns:
            Message send status and ID.
        """
        actions = [
            {
                "type": "reply",
                "reply": {"id": btn["id"], "title": btn["title"][:20]},
            }
            for btn in buttons[:3]
        ]
        json_data: Dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": actions},
            },
        }
        if header_text:
            json_data["interactive"]["header"] = {
                "type": "text",
                "text": header_text,
            }
        if footer_text:
            json_data["interactive"]["footer"] = {"text": footer_text}
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @with_retry(max_retries=3, base_delay=1.0)
    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark a message as read.

        Args:
            message_id: WhatsApp message ID.

        Returns:
            API response.
        """
        json_data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        response = await client.post(
            f"{self._get_phone_path()}/messages",
            json=json_data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Webhook helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_webhook_signature(
        payload: bytes, signature: str, app_secret: str
    ) -> bool:
        """Validate WhatsApp webhook signature (X-Hub-Signature-256).

        Args:
            payload: Raw request body bytes.
            signature: X-Hub-Signature-256 header value (sha256=...).
            app_secret: Facebook app secret.

        Returns:
            True if signature is valid.
        """
        if not signature or not app_secret:
            return False
        expected = hmac.new(
            app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        # signature format: "sha256=<hex>"
        provided = signature.replace("sha256=", "")
        return hmac.compare_digest(provided, expected)

    @staticmethod
    def parse_inbound_message(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a WhatsApp inbound message from webhook payload.

        Args:
            payload: Parsed JSON webhook payload.

        Returns:
            Dict with from_number, message_id, message_type, body, timestamp
            or None if not a text message.
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None
            msg = messages[0]
            msg_type = msg.get("type", "")
            result: Dict[str, Any] = {
                "from_number": msg.get("from"),
                "message_id": msg.get("id"),
                "message_type": msg_type,
                "timestamp": msg.get("timestamp"),
                "profile_name": (
                    value.get("contacts", [{}])[0].get("profile", {}).get("name")
                ),
                "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
            }
            # Extract message content based on type
            if msg_type == "text":
                result["body"] = msg.get("text", {}).get("body", "")
            elif msg_type == "image":
                result["media_id"] = msg.get("image", {}).get("id")
                result["body"] = msg.get("image", {}).get("caption", "[Image]")
            elif msg_type == "document":
                result["media_id"] = msg.get("document", {}).get("id")
                result["body"] = msg.get("document", {}).get("caption", "[Document]")
            elif msg_type == "audio":
                result["media_id"] = msg.get("audio", {}).get("id")
                result["body"] = "[Audio message]"
            elif msg_type == "video":
                result["media_id"] = msg.get("video", {}).get("id")
                result["body"] = msg.get("video", {}).get("caption", "[Video]")
            elif msg_type == "interactive":
                interactive = msg.get("interactive", {})
                btn_reply = interactive.get("button_reply", {})
                result["body"] = btn_reply.get("title", "[Button click]")
                result["button_id"] = btn_reply.get("id")
            elif msg_type == "location":
                loc = msg.get("location", {})
                result["body"] = f"[Location: lat={loc.get('latitude')}, long={loc.get('longitude')}]"
            else:
                result["body"] = f"[{msg_type}]"
            return result
        except (KeyError, IndexError):
            return None

    @staticmethod
    def parse_message_status(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a WhatsApp message status update from webhook payload.

        Args:
            payload: Parsed JSON webhook payload.

        Returns:
            Dict with message_id, status, timestamp or None.
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            statuses = value.get("statuses", [])
            if not statuses:
                return None
            status = statuses[0]
            return {
                "message_id": status.get("id"),
                "status": status.get("status"),  # sent, delivered, read, failed
                "timestamp": status.get("timestamp"),
                "recipient": status.get("recipient_id"),
                "error": status.get("errors", [{}])[0] if status.get("errors") else None,
            }
        except (KeyError, IndexError):
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh access token via Facebook OAuth.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New token info.
        """
        fb_app_id = getattr(settings, "FACEBOOK_APP_ID", "") or getattr(settings, "META_APP_ID", "")
        fb_app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "") or getattr(settings, "META_APP_SECRET", "")
        if not fb_app_id or not fb_app_secret:
            logger.error("Facebook App ID or Secret not configured in settings")
            raise ValueError("Facebook App ID and Secret must be configured in settings")

        params = {
            "grant_type": "fb_exchange_token",
            "client_id": fb_app_id,
            "client_secret": fb_app_secret,
            "fb_exchange_token": refresh_token,
        }
        result = await self.get("/oauth/access_token", params=params)
        return {
            "access_token": result.get("access_token", ""),
            "expires_in": str(result.get("expires_in", 0)),
        }


# =============================================================================
# Telegram Client
# =============================================================================


class TelegramClient(BaseAPIClient):
    """Async client for Telegram Bot API.

    Supports: message sending, webhook setup, conversation updates.

    References:
        https://core.telegram.org/bots/api
    """

    def __init__(self, bot_token: Optional[str] = None):
        self._bot_token = bot_token
        super().__init__(
            platform="telegram",
            base_url=f"https://api.telegram.org/bot{bot_token}" if bot_token else "https://api.telegram.org",
            access_token=bot_token,
        )

    def set_bot_token(self, token: str) -> None:
        """Update the bot token and base URL."""
        self._bot_token = token
        self._access_token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        # Reset client to use new base URL
        if self._client and not self._client.is_closed:
            asyncio.create_task(self._client.aclose())
        self._client = None

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Get bot info.

        Returns:
            Bot user object.
        """
        return await self.get("/getMe")

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a text message.

        Args:
            chat_id: Target chat ID.
            text: Message text (max 4096 characters).
            reply_to_message_id: Message ID to reply to.

        Returns:
            Sent message object.
        """
        json_data: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id:
            json_data["reply_to_message_id"] = reply_to_message_id
        return await self.post("/sendMessage", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_updates(
        self, offset: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get updates (messages) sent to the bot.

        Args:
            offset: Update ID offset for pagination.
            limit: Maximum updates to retrieve.

        Returns:
            List of update objects.
        """
        params = {"offset": offset, "limit": limit}
        result = await self.get("/getUpdates", params=params)
        return result.get("result", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def set_webhook(self, url: str, secret_token: Optional[str] = None) -> bool:
        """Set the bot webhook URL.

        Args:
            url: HTTPS webhook endpoint URL.
            secret_token: Secret for validating webhook requests.

        Returns:
            True if successful.
        """
        json_data: Dict[str, Any] = {"url": url}
        if secret_token:
            json_data["secret_token"] = secret_token
        result = await self.post("/setWebhook", json_data=json_data)
        return result.get("ok", False)

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_inline_keyboard(
        self,
        chat_id: Union[str, int],
        text: str,
        buttons: List[List[Dict[str, str]]],
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a message with inline keyboard.

        Args:
            chat_id: Target chat ID.
            text: Message text (max 4096 characters).
            buttons: List of button rows, each a list of dicts with 'text' and 'callback_data'.
            reply_to_message_id: Message ID to reply to.

        Returns:
            Sent message object.
        """
        keyboard = [
            [
                {
                    "text": btn["text"],
                    "callback_data": btn.get("callback_data", ""),
                }
                for btn in row
            ]
            for row in buttons
        ]
        json_data: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard},
        }
        if reply_to_message_id:
            json_data["reply_to_message_id"] = reply_to_message_id
        return await self.post("/sendMessage", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def send_reply_keyboard(
        self,
        chat_id: Union[str, int],
        text: str,
        keyboard_buttons: List[List[str]],
        one_time: bool = True,
        resize: bool = True,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a message with a reply keyboard.

        Args:
            chat_id: Target chat ID.
            text: Message text.
            keyboard_buttons: List of button label rows.
            one_time: Hide keyboard after use.
            resize: Auto-resize keyboard.
            reply_to_message_id: Message ID to reply to.

        Returns:
            Sent message object.
        """
        keyboard = [[{"text": label} for label in row] for row in keyboard_buttons]
        json_data: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {
                "keyboard": keyboard,
                "one_time_keyboard": one_time,
                "resize_keyboard": resize,
            },
        }
        if reply_to_message_id:
            json_data["reply_to_message_id"] = reply_to_message_id
        return await self.post("/sendMessage", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def edit_message_text(
        self,
        chat_id: Union[str, int],
        message_id: int,
        text: str,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
    ) -> Dict[str, Any]:
        """Edit an existing message text.

        Args:
            chat_id: Target chat ID.
            message_id: Message ID to edit.
            text: New text.
            buttons: Optional new inline keyboard.

        Returns:
            Updated message object.
        """
        json_data: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if buttons:
            keyboard = [
                [
                    {"text": btn["text"], "callback_data": btn.get("callback_data", "")}
                    for btn in row
                ]
                for row in buttons
            ]
            json_data["reply_markup"] = {"inline_keyboard": keyboard}
        return await self.post("/editMessageText", json_data=json_data)

    @with_retry(max_retries=3, base_delay=1.0)
    async def delete_webhook(self) -> bool:
        """Delete the webhook. Returns True if successful."""
        result = await self.get("/deleteWebhook")
        return result.get("ok", False)

    # ------------------------------------------------------------------
    # Webhook helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_webhook_secret(
        payload: bytes, secret_token_header: str, expected_secret: str
    ) -> bool:
        """Validate Telegram webhook using secret token.

        Args:
            payload: Raw request body bytes.
            secret_token_header: X-Telegram-Bot-Api-Secret-Token header value.
            expected_secret: The expected secret token.

        Returns:
            True if secret matches.
        """
        if not expected_secret:
            return True  # No secret configured - allow
        return hmac.compare_digest(secret_token_header or "", expected_secret)

    @staticmethod
    def parse_inbound_update(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a Telegram inbound update from webhook payload.

        Args:
            payload: Parsed JSON webhook payload.

        Returns:
            Dict with chat_id, message_id, from_user, text, message_type,
            callback_data, etc. or None.
        """
        # Handle callback queries (inline keyboard button clicks)
        callback_query = payload.get("callback_query")
        if callback_query:
            message = callback_query.get("message", {})
            from_user = callback_query.get("from", {})
            return {
                "update_type": "callback_query",
                "chat_id": message.get("chat", {}).get("id"),
                "message_id": message.get("message_id"),
                "from_user_id": from_user.get("id"),
                "from_username": from_user.get("username"),
                "from_first_name": from_user.get("first_name"),
                "callback_data": callback_query.get("data"),
                "callback_id": callback_query.get("id"),
                "original_message_text": message.get("text", ""),
                "text": callback_query.get("data", ""),
            }

        # Handle regular messages
        message = payload.get("message")
        if not message:
            return None

        chat = message.get("chat", {})
        from_user = message.get("from", {})
        result: Dict[str, Any] = {
            "update_type": "message",
            "chat_id": chat.get("id"),
            "chat_type": chat.get("type"),  # private, group, supergroup
            "chat_title": chat.get("title"),
            "message_id": message.get("message_id"),
            "from_user_id": from_user.get("id"),
            "from_username": from_user.get("username"),
            "from_first_name": from_user.get("first_name"),
            "date": message.get("date"),
        }

        # Determine message content type
        if "text" in message:
            result["message_type"] = "text"
            result["text"] = message["text"]
            # Check for bot commands
            entities = message.get("entities", [])
            if entities and entities[0].get("type") == "bot_command":
                result["is_command"] = True
                result["command"] = message["text"].split()[0]
            else:
                result["is_command"] = False
        elif "photo" in message:
            result["message_type"] = "photo"
            photos = message["photo"]
            result["photo_file_id"] = photos[-1]["file_id"] if photos else None
            result["text"] = message.get("caption", "[Photo]")
        elif "document" in message:
            result["message_type"] = "document"
            result["document_file_id"] = message["document"].get("file_id")
            result["text"] = message.get("caption", "[Document]")
        elif "voice" in message:
            result["message_type"] = "voice"
            result["voice_file_id"] = message["voice"].get("file_id")
            result["text"] = "[Voice message]"
        elif "video" in message:
            result["message_type"] = "video"
            result["video_file_id"] = message["video"].get("file_id")
            result["text"] = message.get("caption", "[Video]")
        elif "location" in message:
            loc = message["location"]
            result["message_type"] = "location"
            result["text"] = f"[Location: lat={loc.get('latitude')}, long={loc.get('longitude')}]"
        elif "contact" in message:
            contact = message["contact"]
            result["message_type"] = "contact"
            result["text"] = f"[Contact: {contact.get('first_name')} - {contact.get('phone_number')}]"
        else:
            result["message_type"] = "unknown"
            result["text"] = "[Unsupported message type]"

        return result

    @staticmethod
    def parse_inline_query(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an inline query from webhook payload.

        Args:
            payload: Parsed JSON webhook payload.

        Returns:
            Dict with query details or None.
        """
        inline_query = payload.get("inline_query")
        if not inline_query:
            return None
        return {
            "update_type": "inline_query",
            "query_id": inline_query.get("id"),
            "from_user_id": inline_query.get("from", {}).get("id"),
            "query": inline_query.get("query"),
            "offset": inline_query.get("offset"),
        }

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Telegram bot tokens don't expire - return as-is.

        Args:
            refresh_token: Bot token (not actually refreshed).

        Returns:
            Same token with no expiration.
        """
        return {
            "access_token": self._bot_token or refresh_token,
            "expires_in": "0",  # Never expires
        }


# =============================================================================
# Google Maps / Google My Business Client
# =============================================================================


class GoogleMapsClient(BaseAPIClient):
    """Async client for Google My Business API and Places API.

    Supports: review management, account info, location insights.

    References:
        https://developers.google.com/my-business/reference/rest
        https://developers.google.com/maps/documentation/places/web-service
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        account_name: Optional[str] = None,
    ):
        super().__init__(
            platform="google_maps",
            base_url="https://mybusiness.googleapis.com/v4",
            access_token=access_token,
        )
        self.account_name = account_name

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_account_info(self) -> Dict[str, Any]:
        """Fetch Google My Business account info.

        Returns:
            Account metadata.
        """
        return await self.get("/accounts")

    @with_retry(max_retries=3, base_delay=1.0)
    async def list_locations(self) -> List[Dict[str, Any]]:
        """List business locations.

        Returns:
            List of location objects.
        """
        account = self.account_name or "-"
        result = await self.get(f"/{account}/locations")
        return result.get("locations", [])

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_location_reviews(
        self, location_id: str, page_size: int = 50
    ) -> Dict[str, Any]:
        """Fetch reviews for a location.

        Args:
            location_id: Google location ID.
            page_size: Maximum reviews per page.

        Returns:
            Reviews list with nextPageToken.
        """
        params = {"pageSize": page_size}
        return await self.get(
            f"/{self.account_name or '-'}/{location_id}/reviews",
            params=params,
        )

    @with_retry(max_retries=3, base_delay=1.0)
    async def reply_to_review(
        self, location_id: str, review_id: str, comment: str
    ) -> Dict[str, Any]:
        """Reply to a Google review.

        Args:
            location_id: Google location ID.
            review_id: Review ID to reply to.
            comment: Reply text.

        Returns:
            Updated review object.
        """
        json_data = {"comment": comment, "updateTime": datetime.now(timezone.utc).isoformat()}
        return await self.put(
            f"/{self.account_name or '-'}/{location_id}/reviews/{review_id}/reply",
            json_data=json_data,
        )

    @with_retry(max_retries=3, base_delay=1.0)
    async def delete_review_reply(
        self, location_id: str, review_id: str
    ) -> Dict[str, Any]:
        """Delete a review reply.

        Args:
            location_id: Google location ID.
            review_id: Review ID.

        Returns:
            API response.
        """
        return await self.delete(
            f"/{self.account_name or '-'}/{location_id}/reviews/{review_id}/reply"
        )

    @with_retry(max_retries=3, base_delay=1.0)
    async def get_location_insights(
        self,
        location_id: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Fetch location insights.

        Args:
            location_id: Google location ID.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            Insights data.
        """
        json_data = {
            "locationNames": [f"{self.account_name or '-'}/{location_id}"],
            "basicRequests": [
                {
                    "metric": "ALL",
                    "timeRange": {
                        "startTime": f"{start_date}T00:00:00Z",
                        "endTime": f"{end_date}T23:59:59Z",
                    },
                }
            ],
        }
        return await self.post("/accounts:batchGetInsights", json_data=json_data)

    async def put(
        self, path: str, *, json_data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Convenience PUT request."""
        return await self._request("PUT", path, json_data=json_data, **kwargs)

    async def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """Convenience DELETE request."""
        return await self._request("DELETE", path, **kwargs)

    @with_retry(max_retries=3, base_delay=1.0)
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh Google OAuth token.

        Args:
            refresh_token: Current refresh token.

        Returns:
            New token info.
        """
        google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        google_client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
        if not google_client_id or not google_client_secret:
            logger.error("Google Client ID or Secret not configured in settings")
            raise ValueError("Google Client ID and Secret must be configured in settings")

        client = httpx.AsyncClient()
        try:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": google_client_id,
                    "client_secret": google_client_secret,
                    "refresh_token": refresh_token,
                },
            )
            response.raise_for_status()
            result = response.json()
            return {
                "access_token": result.get("access_token", ""),
                "expires_in": str(result.get("expires_in", 0)),
            }
        finally:
            await client.aclose()


# =============================================================================
# Client Factory
# =============================================================================


def get_platform_client(
    platform: str,
    access_token: str,
    account_id: Optional[str] = None,
) -> BaseAPIClient:
    """Factory function to create the appropriate API client.

    Args:
        platform: Platform name (instagram, facebook, tiktok, etc.).
        access_token: Decrypted access token.
        account_id: Platform-specific account ID.

    Returns:
        Configured API client instance.

    Raises:
        ValueError: If platform is not supported.
    """
    if platform == "instagram":
        return InstagramClient(access_token=access_token, instagram_account_id=account_id)
    elif platform == "facebook":
        return MetaClient(access_token=access_token, page_id=account_id)
    elif platform == "tiktok":
        return TikTokClient(access_token=access_token, open_id=account_id)
    elif platform == "whatsapp":
        return WhatsAppClient(access_token=access_token, phone_number_id=account_id)
    elif platform == "telegram":
        return TelegramClient(bot_token=access_token)
    elif platform == "google_maps":
        return GoogleMapsClient(access_token=access_token, account_name=account_id)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


# =============================================================================
# Social Account Service
# =============================================================================


class SocialAccountService:
    """Service for managing connected social media accounts.

    Handles CRUD operations, credential encryption/decryption, token validation,
    and automatic token refresh with exponential backoff.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager()

    async def create_account(
        self, company_id: int, data: SocialAccountCreate, branch_id: Optional[int] = None
    ) -> SocialAccount:
        """Connect a new social media account.

        Encrypts tokens and validates credentials with the platform API.

        Args:
            company_id: Tenant company ID.
            data: Account creation data with tokens.
            branch_id: Optional branch ID.

        Returns:
            Created SocialAccount instance.

        Raises:
            ValidationError: If credentials are invalid.
        """
        # Encrypt tokens
        encrypted = self.credential_manager.encrypt_tokens(
            data.access_token, data.refresh_token
        )

        # Validate credentials by fetching account info
        try:
            client = get_platform_client(
                data.platform,
                data.access_token,
                data.account_id,
            )
            account_info = await client.get_account_info()
            await client.close()
        except Exception as exc:
            logger.error("Failed to validate credentials: %s", exc)
            raise ValidationError(f"Invalid credentials: {str(exc)}") from exc

        # Extract follower count if available
        follower_count = 0
        if isinstance(account_info, dict):
            follower_count = (
                account_info.get("followers_count")
                or account_info.get("fan_count")
                or account_info.get("follower_count")
                or 0
            )

        # Calculate token expiration
        token_expires_at = data.token_expires_at
        if not token_expires_at and data.refresh_token:
            token_expires_at = datetime.utcnow() + timedelta(hours=1)

        account = SocialAccount(
            company_id=company_id,
            branch_id=branch_id,
            platform=data.platform,
            account_name=data.account_name,
            account_id=data.account_id,
            access_token=encrypted["access_token"],
            refresh_token=encrypted.get("refresh_token"),
            token_expires_at=token_expires_at,
            profile_url=data.profile_url,
            follower_count=int(follower_count) if follower_count else 0,
            status=AccountStatus.ACTIVE,
            settings=data.settings,
        )

        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def get_account(self, account_id: int, company_id: int) -> SocialAccount:
        """Get a social account by ID with tenant check.

        Args:
            account_id: Account ID.
            company_id: Tenant company ID for isolation.

        Returns:
            SocialAccount instance.

        Raises:
            NotFoundError: If account not found or doesn't belong to tenant.
        """
        result = await self.db.execute(
            select(SocialAccount)
            .where(
                and_(
                    SocialAccount.id == account_id,
                    SocialAccount.company_id == company_id,
                )
            )
            .options(selectinload(SocialAccount.posts))
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Social account {account_id} not found")
        return account

    async def list_accounts(
        self,
        company_id: int,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List social accounts for a tenant.

        Args:
            company_id: Tenant company ID.
            platform: Filter by platform.
            status: Filter by status.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response with accounts.
        """
        query = select(SocialAccount).where(SocialAccount.company_id == company_id)

        if platform:
            query = query.where(SocialAccount.platform == platform)
        if status:
            query = query.where(SocialAccount.status == status)

        # Count total
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = query.order_by(desc(SocialAccount.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        accounts = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(accounts),
        }

    async def update_account(
        self,
        account_id: int,
        company_id: int,
        data: SocialAccountUpdate,
    ) -> SocialAccount:
        """Update account settings.

        Args:
            account_id: Account ID.
            company_id: Tenant company ID.
            data: Update data.

        Returns:
            Updated account.
        """
        account = await self.get_account(account_id, company_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def delete_account(self, account_id: int, company_id: int) -> None:
        """Disconnect and delete a social account.

        Args:
            account_id: Account ID.
            company_id: Tenant company ID.
        """
        account = await self.get_account(account_id, company_id)
        await self.db.delete(account)
        await self.db.commit()

    async def refresh_account_token(
        self, account_id: int, company_id: int, force: bool = False
    ) -> Dict[str, str]:
        """Refresh an account's access token.

        Args:
            account_id: Account ID.
            company_id: Tenant company ID.
            force: Force refresh even if not expired.

        Returns:
            Token refresh result.
        """
        account = await self.get_account(account_id, company_id)

        if not account.refresh_token:
            return {"success": False, "message": "No refresh token available"}

        # Check if token actually needs refresh
        if not force and account.token_expires_at:
            if account.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
                return {"success": True, "message": "Token still valid"}

        try:
            refresh_token_plain = self.credential_manager.decrypt_refresh_token(
                account.refresh_token
            )
            client = get_platform_client(
                account.platform,
                self.credential_manager.decrypt_access_token(account.access_token),
                account.account_id,
            )
            result = await client.refresh_token(refresh_token_plain)
            await client.close()

            new_access_token = result.get("access_token", "")
            new_refresh_token = result.get("refresh_token")
            expires_in = int(result.get("expires_in", 0) or 0)

            if not new_access_token:
                return {"success": False, "message": "No access token in refresh response"}

            # Encrypt new tokens
            encrypted = self.credential_manager.encrypt_tokens(
                new_access_token, new_refresh_token
            )
            account.access_token = encrypted["access_token"]
            if new_refresh_token:
                account.refresh_token = encrypted.get("refresh_token")
            if expires_in > 0:
                account.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            account.status = AccountStatus.ACTIVE

            await self.db.commit()
            return {
                "success": True,
                "expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
                "message": "Token refreshed successfully",
            }

        except Exception as exc:
            logger.error("Token refresh failed: %s", exc)
            account.status = AccountStatus.ERROR
            await self.db.commit()
            return {"success": False, "message": f"Refresh failed: {str(exc)}"}

    async def get_decrypted_token(self, account_id: int, company_id: int) -> str:
        """Get decrypted access token for API calls.

        Args:
            account_id: Account ID.
            company_id: Tenant company ID.

        Returns:
            Plaintext access token.
        """
        account = await self.get_account(account_id, company_id)
        return self.credential_manager.decrypt_access_token(account.access_token)


# =============================================================================
# Post Service
# =============================================================================


class PostService:
    """Service for social media post management.

    Handles content creation, scheduling, publishing via platform APIs,
    and engagement tracking.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager()

    async def create_post(
        self, company_id: int, data: SocialPostCreate, branch_id: Optional[int] = None
    ) -> SocialPost:
        """Create a new social post (draft or scheduled).

        Args:
            company_id: Tenant company ID.
            data: Post creation data.
            branch_id: Optional branch ID.

        Returns:
            Created SocialPost instance.
        """
        # Validate account exists and belongs to tenant
        result = await self.db.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.id == data.account_id,
                    SocialAccount.company_id == company_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Account {data.account_id} not found")

        status = PostStatus.SCHEDULED if data.scheduled_at else PostStatus.DRAFT

        post = SocialPost(
            company_id=company_id,
            branch_id=branch_id,
            account_id=data.account_id,
            platform=data.platform,
            content=data.content,
            media_urls=data.media_urls,
            hashtags=data.hashtags,
            status=status,
            scheduled_at=data.scheduled_at,
            ai_generated=data.ai_generated,
        )

        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def get_post(self, post_id: int, company_id: int) -> SocialPost:
        """Get a post by ID with tenant check.

        Args:
            post_id: Post ID.
            company_id: Tenant company ID.

        Returns:
            SocialPost instance.

        Raises:
            NotFoundError: If post not found.
        """
        result = await self.db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.id == post_id,
                    SocialPost.company_id == company_id,
                )
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            raise NotFoundError(f"Post {post_id} not found")
        return post

    async def list_posts(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List posts for a tenant.

        Args:
            company_id: Tenant company ID.
            account_id: Filter by account.
            status: Filter by status.
            platform: Filter by platform.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response.
        """
        query = select(SocialPost).where(SocialPost.company_id == company_id)

        if account_id:
            query = query.where(SocialPost.account_id == account_id)
        if status:
            query = query.where(SocialPost.status == status)
        if platform:
            query = query.where(SocialPost.platform == platform)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialPost.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        posts = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(posts),
        }

    async def update_post(
        self, post_id: int, company_id: int, data: SocialPostUpdate
    ) -> SocialPost:
        """Update a draft or scheduled post.

        Args:
            post_id: Post ID.
            company_id: Tenant company ID.
            data: Update data.

        Returns:
            Updated post.

        Raises:
            ValidationError: If post is already published.
        """
        post = await self.get_post(post_id, company_id)

        if post.status == PostStatus.PUBLISHED:
            raise ValidationError("Cannot update a published post")

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(post, field, value)

        # Recalculate status based on scheduled_at
        if "scheduled_at" in update_data:
            post.status = (
                PostStatus.SCHEDULED if update_data["scheduled_at"] else PostStatus.DRAFT
            )

        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def delete_post(self, post_id: int, company_id: int) -> None:
        """Delete a post.

        Args:
            post_id: Post ID.
            company_id: Tenant company ID.
        """
        post = await self.get_post(post_id, company_id)
        await self.db.delete(post)
        await self.db.commit()

    async def publish_now(self, post_id: int, company_id: int) -> Dict[str, str]:
        """Publish a draft or scheduled post immediately.

        Args:
            post_id: Post ID.
            company_id: Tenant company ID.

        Returns:
            Publish result with external post ID.
        """
        post = await self.get_post(post_id, company_id)

        if post.status == PostStatus.PUBLISHED:
            raise ValidationError("Post is already published")

        # Get account and decrypt token
        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == post.account_id)
        )
        account = result.scalar_one_or_none()
        if not account or account.status != AccountStatus.ACTIVE:
            raise ValidationError("Account not connected or active")

        try:
            access_token = CredentialManager.decrypt_access_token(account.access_token)
            client = get_platform_client(post.platform, access_token, account.account_id)

            external_post_id = None

            if post.platform == "instagram":
                # Use Graph API for publishing
                container = await client.create_container(
                    image_url=post.media_urls[0] if post.media_urls else "",
                    caption=post.content,
                )
                creation_id = container.get("id")
                if creation_id:
                    publish_result = await client.publish_container(creation_id)
                    external_post_id = publish_result.get("id")

            elif post.platform == "facebook":
                fb_client = cast(MetaClient, client)
                publish_result = await fb_client.create_page_post(
                    message=post.content,
                )
                external_post_id = publish_result.get("id")

            elif post.platform == "telegram":
                tg_client = cast(TelegramClient, client)
                # Use account_id as chat_id for Telegram
                send_result = await tg_client.send_message(
                    chat_id=account.account_id,
                    text=post.content,
                )
                external_post_id = str(send_result.get("result", {}).get("message_id"))

            else:
                raise ValidationError(f"Publishing not yet implemented for {post.platform}")

            await client.close()

            post.status = PostStatus.PUBLISHED
            post.external_post_id = external_post_id
            post.published_at = datetime.utcnow()

            await self.db.commit()
            return {
                "success": True,
                "external_post_id": external_post_id,
                "message": "Post published successfully",
            }

        except Exception as exc:
            logger.error("Failed to publish post %d: %s", post_id, exc)
            post.status = PostStatus.FAILED
            await self.db.commit()
            return {
                "success": False,
                "message": f"Publish failed: {str(exc)}",
            }

    async def sync_post_engagement(self, post_id: int, company_id: int) -> SocialPost:
        """Sync engagement stats for a published post from the platform.

        Supports Facebook, Instagram, and TikTok posts.

        Args:
            post_id: Post ID.
            company_id: Tenant company ID.

        Returns:
            Updated post.
        """
        post = await self.get_post(post_id, company_id)

        if not post.external_post_id:
            raise ValidationError("Post has no external ID")

        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == post.account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)

        try:
            client = get_platform_client(post.platform, access_token, account.account_id)
            engagement_stats: Dict[str, Any] = {}

            if post.platform == "facebook":
                fb_client = cast(MetaClient, client)
                params = {
                    "fields": "likes.summary(true),comments.summary(true),shares,reactions.summary(true)",
                    "access_token": access_token,
                }
                post_data = await fb_client.get(f"/{post.external_post_id}", params=params)
                engagement_stats = {
                    "likes": post_data.get("likes", {}).get("summary", {}).get("total_count", 0),
                    "shares": post_data.get("shares", {}).get("count", 0),
                    "comments": post_data.get("comments", {}).get("summary", {}).get("total_count", 0),
                    "reactions": post_data.get("reactions", {}).get("summary", {}).get("total_count", 0),
                }

            elif post.platform == "instagram":
                ig_client = cast(InstagramClient, client)
                # Instagram Graph API: get media insights
                params = {
                    "fields": "like_count,comments_count,media_type,permalink,timestamp",
                    "access_token": access_token,
                }
                post_data = await ig_client.get(f"/{post.external_post_id}", params=params)
                engagement_stats = {
                    "likes": post_data.get("like_count", 0),
                    "comments": post_data.get("comments_count", 0),
                    "shares": 0,  # Not directly available via Graph API
                }
                # Get insights for impressions/reach if business account
                try:
                    insights_params = {
                        "metric": "impressions,reach,engagement,saved",
                        "access_token": access_token,
                    }
                    insights = await ig_client.get(
                        f"/{post.external_post_id}/insights", params=insights_params
                    )
                    for metric in insights.get("data", []):
                        name = metric.get("name", "")
                        values = metric.get("values", [])
                        val = values[0].get("value", 0) if values else 0
                        engagement_stats[name] = val
                except Exception as ins_exc:
                    logger.debug("Instagram insights not available: %s", ins_exc)

            elif post.platform == "tiktok":
                tt_client = cast(TikTokClient, client)
                try:
                    analytics = await tt_client.get_video_analytics(
                        video_ids=[post.external_post_id]
                    )
                    video_data = analytics.get("data", {}).get("videos", [])
                    if video_data:
                        video = video_data[0]
                        engagement_stats = {
                            "likes": video.get("like_count", 0),
                            "comments": video.get("comment_count", 0),
                            "shares": video.get("share_count", 0),
                            "views": video.get("view_count", 0),
                            "reach": video.get("reach_count", 0),
                        }
                except Exception as tt_exc:
                    logger.debug("TikTok analytics not available: %s", tt_exc)

            post.engagement_stats = engagement_stats
            post.engagement_synced_at = datetime.utcnow()
            await client.close()
            await self.db.commit()
            await self.db.refresh(post)
            return post

        except Exception as exc:
            logger.error("Failed to sync engagement for post %d: %s", post_id, exc)
            raise


# =============================================================================
# Comment Service
# =============================================================================


class CommentService:
    """Service for social media comment management.

    Handles comment sync from platforms, sentiment analysis, and reply management.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_comment(
        self, company_id: int, data: SocialCommentCreate, branch_id: Optional[int] = None
    ) -> SocialComment:
        """Create a comment record.

        Args:
            company_id: Tenant company ID.
            data: Comment data.
            branch_id: Optional branch ID.

        Returns:
            Created comment.
        """
        comment = SocialComment(
            company_id=company_id,
            branch_id=branch_id,
            account_id=data.account_id,
            post_id=data.post_id,
            external_comment_id=data.external_comment_id,
            parent_comment_id=data.parent_comment_id,
            author_name=data.author_name,
            author_id=data.author_id,
            content=data.content,
            sentiment=data.sentiment,
            status=CommentStatus.NEW,
        )
        self.db.add(comment)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def get_comment(self, comment_id: int, company_id: int) -> SocialComment:
        """Get a comment by ID.

        Args:
            comment_id: Comment ID.
            company_id: Tenant company ID.

        Returns:
            SocialComment instance.
        """
        result = await self.db.execute(
            select(SocialComment).where(
                and_(
                    SocialComment.id == comment_id,
                    SocialComment.company_id == company_id,
                )
            )
        )
        comment = result.scalar_one_or_none()
        if not comment:
            raise NotFoundError(f"Comment {comment_id} not found")
        return comment

    async def list_comments(
        self,
        company_id: int,
        post_id: Optional[int] = None,
        status: Optional[str] = None,
        account_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List comments for a tenant.

        Args:
            company_id: Tenant company ID.
            post_id: Filter by post.
            status: Filter by status.
            account_id: Filter by account.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response.
        """
        query = select(SocialComment).where(SocialComment.company_id == company_id)

        if post_id:
            query = query.where(SocialComment.post_id == post_id)
        if status:
            query = query.where(SocialComment.status == status)
        if account_id:
            query = query.where(SocialComment.account_id == account_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialComment.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        comments = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(comments),
        }

    async def update_comment(
        self, comment_id: int, company_id: int, data: SocialCommentUpdate
    ) -> SocialComment:
        """Update a comment.

        Args:
            comment_id: Comment ID.
            company_id: Tenant company ID.
            data: Update data.

        Returns:
            Updated comment.
        """
        comment = await self.get_comment(comment_id, company_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(comment, field, value)
        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    async def reply_to_comment(
        self, comment_id: int, company_id: int, reply_content: str
    ) -> Dict[str, str]:
        """Reply to a comment via the platform API.

        Args:
            comment_id: Comment ID.
            company_id: Tenant company ID.
            reply_content: Reply text.

        Returns:
            Reply result.
        """
        comment = await self.get_comment(comment_id, company_id)

        if not comment.external_comment_id:
            raise ValidationError("Cannot reply: no external comment ID")

        # Get account credentials
        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == comment.account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)
        client = get_platform_client(account.platform, access_token, account.account_id)

        reply_id = None
        try:
            if account.platform == "instagram":
                ig_client = cast(InstagramClient, client)
                result_data = await ig_client.post_comment_reply(
                    comment.external_comment_id, reply_content
                )
                reply_id = result_data.get("id")

            elif account.platform == "facebook":
                fb_client = cast(MetaClient, client)
                result_data = await fb_client.reply_to_comment(
                    comment.external_comment_id, reply_content
                )
                reply_id = result_data.get("id")

            comment.status = CommentStatus.REPLIED
            comment.replied_content = reply_content
            await self.db.commit()

            return {
                "success": True,
                "reply_id": reply_id,
                "message": "Reply sent successfully",
            }

        except Exception as exc:
            logger.error("Failed to reply to comment %d: %s", comment_id, exc)
            return {
                "success": False,
                "message": f"Reply failed: {str(exc)}",
            }
        finally:
            await client.close()

    async def mark_as_read(self, comment_id: int, company_id: int) -> Dict[str, str]:
        """Mark a comment as read.

        Args:
            comment_id: Comment ID.
            company_id: Tenant company ID.

        Returns:
            Result.
        """
        comment = await self.get_comment(comment_id, company_id)
        comment.status = CommentStatus.READ
        await self.db.commit()
        return {"success": True, "message": "Comment marked as read"}

    async def sync_comments(
        self,
        company_id: int,
        account_id: int,
        post_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """Sync comments from the platform API.

        Supports Instagram, Facebook, and TikTok comment sync.

        Args:
            company_id: Tenant company ID.
            account_id: Account ID to sync.
            post_id: Optional specific post to sync.

        Returns:
            Sync statistics with created count per platform.
        """
        result = await self.db.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.id == account_id,
                    SocialAccount.company_id == company_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)
        client = get_platform_client(account.platform, access_token, account.account_id)

        created_count = 0
        updated_count = 0
        try:
            # Build posts query
            posts_query = select(SocialPost).where(
                and_(
                    SocialPost.account_id == account_id,
                    SocialPost.external_post_id.isnot(None),
                    SocialPost.status == PostStatus.PUBLISHED,
                )
            )
            if post_id:
                posts_query = posts_query.where(SocialPost.id == post_id)

            posts_result = await self.db.execute(posts_query)
            posts = posts_result.scalars().all()

            if account.platform == "instagram":
                ig_client = cast(InstagramClient, client)
                for post in posts:
                    try:
                        comments = await ig_client.get_media_comments(post.external_post_id)
                        for c in comments:
                            ext_id = c.get("id")
                            existing = await self.db.execute(
                                select(SocialComment).where(
                                    SocialComment.external_comment_id == ext_id
                                )
                            )
                            if existing.scalar_one_or_none():
                                continue

                            comment_data = SocialCommentCreate(
                                account_id=account_id,
                                post_id=post.id,
                                external_comment_id=ext_id,
                                author_name=c.get("username", c.get("from", {}).get("name", "Unknown")),
                                author_id=c.get("from", {}).get("id", ""),
                                content=c.get("text", c.get("message", "")),
                            )
                            await self.create_comment(company_id, comment_data)
                            created_count += 1
                            # Also sync reply comments (replies)
                            replies = c.get("replies", {}).get("data", [])
                            for reply in replies:
                                reply_ext_id = reply.get("id")
                                reply_existing = await self.db.execute(
                                    select(SocialComment).where(
                                        SocialComment.external_comment_id == reply_ext_id
                                    )
                                )
                                if reply_existing.scalar_one_or_none():
                                    continue
                                reply_data = SocialCommentCreate(
                                    account_id=account_id,
                                    post_id=post.id,
                                    external_comment_id=reply_ext_id,
                                    parent_comment_id=ext_id,
                                    author_name=reply.get("username", "Unknown"),
                                    content=reply.get("text", ""),
                                )
                                await self.create_comment(company_id, reply_data)
                                created_count += 1
                    except Exception as exc:
                        logger.error("Error syncing IG comments for post %d: %s", post.id, exc)

            elif account.platform == "facebook":
                fb_client = cast(MetaClient, client)
                for post in posts:
                    try:
                        comments = await fb_client.get_post_comments(post.external_post_id)
                        for c in comments:
                            ext_id = c.get("id")
                            existing = await self.db.execute(
                                select(SocialComment).where(
                                    SocialComment.external_comment_id == ext_id
                                )
                            )
                            existing_comment = existing.scalar_one_or_none()
                            if existing_comment:
                                # Update like count if changed
                                new_likes = c.get("like_count", 0)
                                if existing_comment.likes_count != new_likes:
                                    existing_comment.likes_count = new_likes
                                    updated_count += 1
                                continue

                            from_data = c.get("from", {})
                            comment_data = SocialCommentCreate(
                                account_id=account_id,
                                post_id=post.id,
                                external_comment_id=ext_id,
                                author_name=from_data.get("name", "Unknown"),
                                author_id=str(from_data.get("id", "")),
                                content=c.get("message", c.get("text", "")),
                                likes_count=c.get("like_count", 0),
                            )
                            await self.create_comment(company_id, comment_data)
                            created_count += 1
                    except Exception as exc:
                        logger.error("Error syncing FB comments for post %d: %s", post.id, exc)

            elif account.platform == "tiktok":
                tt_client = cast(TikTokClient, client)
                for post in posts:
                    try:
                        comments_result = await tt_client.get_video_comments(
                            video_id=post.external_post_id, max_count=50
                        )
                        comments_data = comments_result.get("data", {}).get("comments", [])
                        for c in comments_data:
                            ext_id = c.get("comment_id", c.get("id"))
                            existing = await self.db.execute(
                                select(SocialComment).where(
                                    SocialComment.external_comment_id == ext_id
                                )
                            )
                            if existing.scalar_one_or_none():
                                continue

                            comment_data = SocialCommentCreate(
                                account_id=account_id,
                                post_id=post.id,
                                external_comment_id=ext_id,
                                author_name=c.get("username", c.get("user", {}).get("display_name", "Unknown")),
                                author_id=c.get("user_id", ""),
                                content=c.get("text", c.get("content", "")),
                                likes_count=c.get("like_count", 0),
                            )
                            await self.create_comment(company_id, comment_data)
                            created_count += 1
                    except Exception as exc:
                        logger.error("Error syncing TikTok comments for post %d: %s", post.id, exc)

            account.last_sync_at = datetime.utcnow()
            await self.db.commit()

        finally:
            await client.close()

        return {"created": created_count, "updated": updated_count}

    async def analyze_sentiment(self, comment_id: int, company_id: int) -> Dict[str, str]:
        """Analyze comment sentiment using AI integration.

        In production, this calls the AI service. For now, uses a simple keyword approach.

        Args:
            comment_id: Comment ID.
            company_id: Tenant company ID.

        Returns:
            Sentiment result.
        """
        comment = await self.get_comment(comment_id, company_id)

        # Simple keyword-based sentiment (replace with AI service call)
        positive_words = {
            "good", "great", "excellent", "amazing", "love", "best", "awesome",
            "perfect", "beautiful", "nice", "thanks", "thank", "happy", "fantastic",
            "wonderful", "brilliant", "outstanding", "superb", "lovely", "like",
        }
        negative_words = {
            "bad", "terrible", "awful", "hate", "worst", "horrible", "poor",
            "disappointing", "useless", "broken", "wrong", "problem", "issue",
            "error", "fail", "failed", "slow", "expensive", "waste", "never",
        }

        content_lower = comment.content.lower()
        pos_count = sum(1 for w in positive_words if w in content_lower)
        neg_count = sum(1 for w in negative_words if w in content_lower)

        if pos_count > neg_count:
            sentiment = CommentSentiment.POSITIVE
        elif neg_count > pos_count:
            sentiment = CommentSentiment.NEGATIVE
        else:
            sentiment = CommentSentiment.NEUTRAL

        comment.sentiment = sentiment
        await self.db.commit()

        return {"sentiment": sentiment.value, "message": "Sentiment analyzed"}


# =============================================================================
# Message Service
# =============================================================================


class MessageService:
    """Service for direct message/conversation management.

    Handles message sync, conversation threading, and replies via platform APIs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_message(
        self, company_id: int, data: SocialMessageCreate, branch_id: Optional[int] = None
    ) -> SocialMessage:
        """Create a message record.

        Args:
            company_id: Tenant company ID.
            data: Message data.
            branch_id: Optional branch ID.

        Returns:
            Created message.
        """
        message = SocialMessage(
            company_id=company_id,
            branch_id=branch_id,
            account_id=data.account_id,
            platform=data.platform,
            external_conversation_id=data.external_conversation_id,
            external_message_id=data.external_message_id,
            sender_name=data.sender_name,
            sender_id=data.sender_id,
            content=data.content,
            direction=data.direction,
            status=MessageStatus.NEW,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_message(self, message_id: int, company_id: int) -> SocialMessage:
        """Get a message by ID.

        Args:
            message_id: Message ID.
            company_id: Tenant company ID.

        Returns:
            SocialMessage instance.
        """
        result = await self.db.execute(
            select(SocialMessage).where(
                and_(
                    SocialMessage.id == message_id,
                    SocialMessage.company_id == company_id,
                )
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            raise NotFoundError(f"Message {message_id} not found")
        return message

    async def list_messages(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List messages for a tenant.

        Args:
            company_id: Tenant company ID.
            account_id: Filter by account.
            platform: Filter by platform.
            status: Filter by status.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response.
        """
        query = select(SocialMessage).where(SocialMessage.company_id == company_id)

        if account_id:
            query = query.where(SocialMessage.account_id == account_id)
        if platform:
            query = query.where(SocialMessage.platform == platform)
        if status:
            query = query.where(SocialMessage.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialMessage.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        messages = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(messages),
        }

    async def list_conversations(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List conversation summaries grouped by conversation ID.

        Args:
            company_id: Tenant company ID.
            account_id: Filter by account.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated conversation summaries.
        """
        query = select(SocialMessage).where(SocialMessage.company_id == company_id)
        if account_id:
            query = query.where(SocialMessage.account_id == account_id)

        count_result = await self.db.execute(
            select(
                func.count(func.distinct(SocialMessage.external_conversation_id))
            ).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get distinct conversation IDs with pagination
        conv_query = (
            select(SocialMessage.external_conversation_id)
            .where(SocialMessage.company_id == company_id)
            .distinct()
            .order_by(desc(func.max(SocialMessage.created_at)))
        )
        if account_id:
            conv_query = conv_query.where(SocialMessage.account_id == account_id)
        conv_query = conv_query.group_by(SocialMessage.external_conversation_id)
        conv_query = conv_query.offset((page - 1) * page_size).limit(page_size)

        conv_result = await self.db.execute(conv_query)
        conversation_ids = conv_result.scalars().all()

        conversations = []
        for conv_id in conversation_ids:
            # Get latest message for summary
            latest = await self.db.execute(
                select(SocialMessage)
                .where(
                    and_(
                        SocialMessage.company_id == company_id,
                        SocialMessage.external_conversation_id == conv_id,
                    )
                )
                .order_by(desc(SocialMessage.created_at))
                .limit(1)
            )
            latest_msg = latest.scalar_one_or_none()
            if not latest_msg:
                continue

            # Count unread
            unread_result = await self.db.execute(
                select(func.count())
                .where(
                    and_(
                        SocialMessage.company_id == company_id,
                        SocialMessage.external_conversation_id == conv_id,
                        SocialMessage.status == MessageStatus.NEW,
                        SocialMessage.direction == MessageDirection.INBOUND,
                    )
                )
            )
            unread_count = unread_result.scalar() or 0

            conversations.append(
                {
                    "external_conversation_id": conv_id,
                    "platform": latest_msg.platform,
                    "account_id": latest_msg.account_id,
                    "participant_name": latest_msg.sender_name,
                    "last_message": latest_msg.content,
                    "last_message_at": latest_msg.created_at,
                    "unread_count": unread_count,
                }
            )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": conversations,
        }

    async def reply_to_conversation(
        self, message_id: int, company_id: int, reply_content: str
    ) -> Dict[str, str]:
        """Reply to a conversation via the platform API.

        Args:
            message_id: Message ID (any message in the conversation).
            company_id: Tenant company ID.
            reply_content: Reply text.

        Returns:
            Reply result.
        """
        message = await self.get_message(message_id, company_id)

        result = await self.db.execute(
            select(SocialAccount).where(SocialAccount.id == message.account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)
        client = get_platform_client(account.platform, access_token, account.account_id)

        try:
            message_id_result = None

            if account.platform == "whatsapp":
                wa_client = cast(WhatsAppClient, client)
                # Extract sender phone from sender_id
                result_data = await wa_client.send_text_message(
                    to=message.sender_id or "",
                    body=reply_content,
                )
                message_id_result = result_data.get("messages", [{}])[0].get("id")

            elif account.platform == "telegram":
                tg_client = cast(TelegramClient, client)
                result_data = await tg_client.send_message(
                    chat_id=message.external_conversation_id,
                    text=reply_content,
                )
                message_id_result = str(result_data.get("result", {}).get("message_id"))

            # Record the outbound message
            outbound = SocialMessage(
                company_id=company_id,
                branch_id=message.branch_id,
                account_id=message.account_id,
                platform=message.platform,
                external_conversation_id=message.external_conversation_id,
                external_message_id=message_id_result,
                sender_name="Business",
                sender_id=account.account_id,
                content=reply_content,
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.READ,
            )
            self.db.add(outbound)

            # Mark original message as replied
            message.status = MessageStatus.REPLIED
            await self.db.commit()

            return {
                "success": True,
                "message_id": message_id_result,
                "message": "Reply sent successfully",
            }

        except Exception as exc:
            logger.error("Failed to reply to message %d: %s", message_id, exc)
            return {
                "success": False,
                "message": f"Reply failed: {str(exc)}",
            }
        finally:
            await client.close()

    async def mark_conversation_as_read(
        self, conversation_id: str, company_id: int, account_id: int
    ) -> Dict[str, Any]:
        """Mark all messages in a conversation as read.

        Args:
            conversation_id: External conversation ID.
            company_id: Tenant company ID.
            account_id: Account ID.

        Returns:
            Result with marked count.
        """
        result = await self.db.execute(
            select(SocialMessage).where(
                and_(
                    SocialMessage.company_id == company_id,
                    SocialMessage.external_conversation_id == conversation_id,
                    SocialMessage.status == MessageStatus.NEW,
                )
            )
        )
        messages = result.scalars().all()
        count = 0
        for msg in messages:
            msg.status = MessageStatus.READ
            count += 1
        await self.db.commit()

        # Send read receipt to platform if supported
        try:
            account_result = await self.db.execute(
                select(SocialAccount).where(SocialAccount.id == account_id)
            )
            account = account_result.scalar_one_or_none()
            if account and account.platform == SocialPlatform.FACEBOOK:
                access_token = CredentialManager.decrypt_access_token(account.access_token)
                client = get_platform_client(account.platform, access_token, account.account_id)
                fb_client = cast(MetaClient, client)
                # Find sender_id from the latest inbound message
                latest_inbound = [m for m in messages if m.direction == MessageDirection.INBOUND]
                if latest_inbound:
                    await fb_client.mark_messenger_read(latest_inbound[0].sender_id or "")
                await client.close()
        except Exception as exc:
            logger.warning("Failed to send platform read receipt: %s", exc)

        return {"success": True, "marked_count": count, "message": f"{count} messages marked as read"}

    async def sync_conversations(
        self,
        company_id: int,
        account_id: int,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Sync DM conversations from Instagram or Facebook Messenger.

        Args:
            company_id: Tenant company ID.
            account_id: Account ID to sync.
            limit: Max conversations to fetch.

        Returns:
            Sync statistics.
        """
        result = await self.db.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.id == account_id,
                    SocialAccount.company_id == company_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)
        client = get_platform_client(account.platform, access_token, account.account_id)

        fetched = 0
        new_messages = 0
        try:
            if account.platform == SocialPlatform.INSTAGRAM:
                ig_client = cast(InstagramClient, client)
                conversations = await ig_client.get_conversations(limit=limit)
                for conv in conversations:
                    fetched += 1
                    conv_id = conv.get("id", "")
                    participants = conv.get("participants", {}).get("data", [])
                    participant_name = participants[0].get("name", "Unknown") if participants else "Unknown"
                    participant_id = participants[0].get("id", "") if participants else ""

                    messages = conv.get("messages", {}).get("data", [])
                    for msg in messages:
                        ext_msg_id = msg.get("id", "")
                        # Check if message already exists
                        exists = await self.db.execute(
                            select(SocialMessage).where(
                                SocialMessage.external_message_id == ext_msg_id
                            )
                        )
                        if exists.scalar_one_or_none():
                            continue

                        from_data = msg.get("from", {})
                        sender_name = from_data.get("name", "Unknown")
                        sender_id = str(from_data.get("id", ""))
                        content = msg.get("message", "")

                        msg_data = SocialMessageCreate(
                            account_id=account_id,
                            platform="instagram",
                            external_conversation_id=conv_id,
                            external_message_id=ext_msg_id,
                            sender_name=sender_name,
                            sender_id=sender_id,
                            content=content,
                            direction="inbound" if sender_id != account.account_id else "outbound",
                        )
                        await self.create_message(company_id, msg_data)
                        new_messages += 1

            elif account.platform == SocialPlatform.FACEBOOK:
                fb_client = cast(MetaClient, client)
                conversations = await fb_client.get_messenger_conversations(limit=limit)
                for conv in conversations:
                    fetched += 1
                    conv_id = conv.get("id", "")
                    participants = conv.get("participants", {}).get("data", [])
                    # Find the non-page participant
                    participant_name = "Unknown"
                    participant_id = ""
                    for p in participants:
                        if str(p.get("id", "")) != str(account.account_id):
                            participant_name = p.get("name", "Unknown")
                            participant_id = str(p.get("id", ""))
                            break

                    messages = conv.get("messages", {}).get("data", [])
                    for msg in messages:
                        ext_msg_id = msg.get("id", "")
                        exists = await self.db.execute(
                            select(SocialMessage).where(
                                SocialMessage.external_message_id == ext_msg_id
                            )
                        )
                        if exists.scalar_one_or_none():
                            continue

                        from_data = msg.get("from", {})
                        sender_name = from_data.get("name", "Unknown")
                        sender_id = str(from_data.get("id", ""))
                        content = msg.get("message", "")

                        msg_data = SocialMessageCreate(
                            account_id=account_id,
                            platform="facebook",
                            external_conversation_id=conv_id,
                            external_message_id=ext_msg_id,
                            sender_name=sender_name,
                            sender_id=sender_id,
                            content=content,
                            direction="inbound" if sender_id != account.account_id else "outbound",
                        )
                        await self.create_message(company_id, msg_data)
                        new_messages += 1

            account.last_sync_at = datetime.utcnow()
            await self.db.commit()

        finally:
            await client.close()

        return {
            "success": True,
            "fetched": fetched,
            "new_messages": new_messages,
            "message": f"Synced {new_messages} new messages from {fetched} conversations",
        }

    async def analyze_message_sentiment(self, message_id: int, company_id: int) -> Dict[str, Any]:
        """Analyze sentiment of a message using keyword-based + AI hybrid approach.

        Args:
            message_id: Message ID.
            company_id: Tenant company ID.

        Returns:
            Sentiment result with escalation flag.
        """
        message = await self.get_message(message_id, company_id)

        # Keyword-based sentiment analysis
        positive_words = {
            "good", "great", "excellent", "amazing", "love", "best", "awesome",
            "perfect", "beautiful", "nice", "thanks", "thank", "happy", "fantastic",
            "wonderful", "brilliant", "outstanding", "superb", "lovely", "like",
            "teşekkür", "sağol", "harika", "mükemmel", "çok iyi", "bayıldım",
            "çok güzel", "süper", "tebrik", "memnun", "sevdim",
        }
        negative_words = {
            "bad", "terrible", "awful", "hate", "worst", "horrible", "poor",
            "disappointing", "useless", "broken", "wrong", "problem", "issue",
            "error", "fail", "failed", "slow", "expensive", "waste", "never",
            "angry", "furious", "unacceptable", "complaint", "refund", "cancel",
            "berbat", "kötü", "rezalet", "sinir", "problemli", "hatalı",
            "pişman", "iptal", "iade", "şikayet", "çok kötü", "yavaş",
            "sorunlu", "başarısız", "hayal kırıklığı", "umutsuz", "öfkeli",
            "mükemmel değil", "hiç iyi değil", "asla", "çalışmıyor",
        }

        content_lower = message.content.lower()
        pos_count = sum(1 for w in positive_words if w in content_lower)
        neg_count = sum(1 for w in negative_words if w in content_lower)

        if neg_count > pos_count:
            sentiment = MessageSentiment.NEGATIVE
            confidence = min(0.95, 0.5 + (neg_count - pos_count) * 0.15)
        elif pos_count > neg_count:
            sentiment = MessageSentiment.POSITIVE
            confidence = min(0.95, 0.5 + (pos_count - neg_count) * 0.15)
        else:
            sentiment = MessageSentiment.NEUTRAL
            confidence = 0.5

        message.sentiment = sentiment
        await self.db.commit()

        # Sentiment escalation: negative sentiment triggers auto-escalation
        escalated = False
        if sentiment == MessageSentiment.NEGATIVE and confidence >= 0.7:
            escalated = True
            logger.warning(
                "Sentiment escalation triggered for message %d (confidence: %.2f)",
                message_id, confidence,
            )

        return {
            "sentiment": sentiment.value,
            "confidence": round(confidence, 4),
            "escalated": escalated,
            "message": f"Sentiment: {sentiment.value} (confidence: {confidence:.2f})" + (" - ESCALATED" if escalated else ""),
        }

    async def generate_ai_reply_suggestion(
        self, message_id: int, company_id: int, tone: str = "professional"
    ) -> Dict[str, Any]:
        """Generate an AI reply suggestion for a conversation.

        Auto-send is DISABLED by default. The suggestion must be reviewed
        and approved by a human agent before sending.

        Args:
            message_id: Message ID (any message in the conversation).
            company_id: Tenant company ID.
            tone: Reply tone (professional, friendly, formal).

        Returns:
            AI suggestion with confidence score.
        """
        message = await self.get_message(message_id, company_id)

        # Get conversation context (last 10 messages)
        context_result = await self.db.execute(
            select(SocialMessage)
            .where(
                and_(
                    SocialMessage.company_id == company_id,
                    SocialMessage.external_conversation_id == message.external_conversation_id,
                )
            )
            .order_by(desc(SocialMessage.created_at))
            .limit(10)
        )
        context_messages = context_result.scalars().all()

        # Build conversation context
        conversation_history = "\n".join([
            f"{'Customer' if m.direction == MessageDirection.INBOUND else 'Agent'}: {m.content}"
            for m in reversed(context_messages)
        ])

        # Simple template-based AI suggestion (replace with LLM call in production)
        tone_prefixes = {
            "professional": "Thank you for reaching out. ",
            "friendly": "Hey there! ",
            "formal": "Dear valued customer, ",
        }
        tone_closings = {
            "professional": " Best regards, Support Team",
            "friendly": " Cheers! 😊",
            "formal": " Sincerely, Customer Support",
        }

        prefix = tone_prefixes.get(tone, tone_prefixes["professional"])
        closing = tone_closings.get(tone, tone_closings["professional"])

        content_lower = message.content.lower()

        # Intent-based suggestion templates
        if any(w in content_lower for w in ("fiyat", "price", "ücret", "cost", "ne kadar", "kaç para")):
            suggestion = f"{prefix}We'd be happy to provide pricing information. Could you please let us know which specific product or service you're interested in?{closing}"
        elif any(w in content_lower for w in ("sorun", "problem", "issue", "error", "hata", "çalışmıyor")):
            suggestion = f"{prefix}We sincerely apologize for the inconvenience. To help resolve this issue as quickly as possible, could you please provide more details about the problem you're experiencing?{closing}"
        elif any(w in content_lower for w in ("teşekkür", "thanks", "thank", "sağol", "teşekkürler")):
            suggestion = f"{prefix}You're very welcome! We're always here to help. If you need anything else, please don't hesitate to reach out.{closing}"
        elif any(w in content_lower for w in ("iade", "refund", "iptal", "cancel")):
            suggestion = f"{prefix}We understand you'd like to request a refund or cancellation. We'd be happy to assist you with this. Could you please provide your order or transaction ID?{closing}"
        elif any(w in content_lower for w in ("merhaba", "hello", "hi", "selam")):
            suggestion = f"{prefix}Hello! Welcome to our support channel. How can we assist you today?{closing}"
        elif any(w in content_lower for w in ("şikayet", "complaint", "şikayetçi", "memnun değil")):
            suggestion = f"{prefix}We take your feedback very seriously and sincerely apologize for any disappointment. A senior support agent will review your case and get back to you shortly.{closing}"
        else:
            suggestion = f"{prefix}Thank you for your message. We've received it and one of our support agents will get back to you as soon as possible.{closing}"

        confidence = 0.75  # Template-based suggestions have moderate confidence

        # Store the suggestion but DO NOT auto-send
        message.ai_suggested_reply = suggestion
        message.ai_auto_reply_sent = False
        await self.db.commit()

        return {
            "suggestion": suggestion,
            "confidence": round(confidence, 4),
            "tone": tone,
            "auto_send_enabled": False,
            "message": "AI reply suggestion generated (auto-send is OFF)",
        }

    async def get_unread_counts(self, company_id: int) -> Dict[str, Any]:
        """Get unread message counts per platform and total.

        Args:
            company_id: Tenant company ID.

        Returns:
            Unread counts by platform and total.
        """
        from sqlalchemy import func

        total_result = await self.db.execute(
            select(func.count())
            .where(
                and_(
                    SocialMessage.company_id == company_id,
                    SocialMessage.status == MessageStatus.NEW,
                    SocialMessage.direction == MessageDirection.INBOUND,
                )
            )
        )
        total_unread = total_result.scalar() or 0

        # Per platform
        platform_result = await self.db.execute(
            select(SocialMessage.platform, func.count())
            .where(
                and_(
                    SocialMessage.company_id == company_id,
                    SocialMessage.status == MessageStatus.NEW,
                    SocialMessage.direction == MessageDirection.INBOUND,
                )
            )
            .group_by(SocialMessage.platform)
        )
        by_platform = {row[0]: row[1] for row in platform_result.all()}

        return {
            "total_unread": total_unread,
            "by_platform": by_platform,
        }

    async def queue_incoming_message(
        self,
        company_id: int,
        account_id: int,
        platform: str,
        external_conversation_id: str,
        external_message_id: Optional[str],
        sender_name: str,
        sender_id: Optional[str],
        content: str,
    ) -> ConversationQueue:
        """Queue an incoming message for ordered processing.

        Negative sentiment messages get higher priority.

        Args:
            company_id: Tenant company ID.
            account_id: Account ID.
            platform: Source platform.
            external_conversation_id: Conversation/thread ID.
            external_message_id: Platform message ID.
            sender_name: Sender display name.
            sender_id: Platform sender ID.
            content: Message text.

        Returns:
            Created queue entry.
        """
        # Priority boost for negative keywords
        negative_keywords = [
            "sorun", "problem", "issue", "error", "hata", "şikayet",
            "complaint", "angry", "furious", "kötü", "berbat", "terrible",
            "iptal", "cancel", "iade", "refund", "pişman",
        ]
        priority = 10 if any(kw in content.lower() for kw in negative_keywords) else 0

        entry = ConversationQueue(
            company_id=company_id,
            account_id=account_id,
            platform=platform,
            external_conversation_id=external_conversation_id,
            external_message_id=external_message_id,
            sender_name=sender_name,
            sender_id=sender_id,
            content=content,
            status="pending",
            priority=priority,
            retry_count=0,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def process_queued_messages(self, company_id: int, batch_size: int = 50) -> Dict[str, int]:
        """Process pending messages from the queue.

        Creates SocialMessage records, runs sentiment analysis, and
        triggers escalation for negative sentiment.

        Args:
            company_id: Tenant company ID.
            batch_size: Max messages to process.

        Returns:
            Processing statistics.
        """
        from sqlalchemy import asc

        result = await self.db.execute(
            select(ConversationQueue)
            .where(
                and_(
                    ConversationQueue.company_id == company_id,
                    ConversationQueue.status == "pending",
                )
            )
            .order_by(asc(ConversationQueue.priority), asc(ConversationQueue.created_at))
            .limit(batch_size)
        )
        pending = result.scalars().all()

        processed = 0
        escalated = 0
        failed = 0

        for entry in pending:
            try:
                entry.status = "processing"
                await self.db.commit()

                # Create the actual message record
                msg_data = SocialMessageCreate(
                    account_id=entry.account_id,
                    platform=entry.platform.value if hasattr(entry.platform, "value") else str(entry.platform),
                    external_conversation_id=entry.external_conversation_id,
                    external_message_id=entry.external_message_id,
                    sender_name=entry.sender_name,
                    sender_id=entry.sender_id,
                    content=entry.content,
                    direction="inbound",
                )
                message = await self.create_message(company_id, msg_data)

                # Run sentiment analysis
                sentiment_result = await self.analyze_message_sentiment(message.id, company_id)

                # Generate AI reply suggestion (auto-send is OFF by default)
                await self.generate_ai_reply_suggestion(message.id, company_id)

                entry.status = "completed"
                entry.processed_at = datetime.utcnow()
                await self.db.commit()
                processed += 1

                if sentiment_result.get("escalated"):
                    escalated += 1

            except Exception as exc:
                logger.error("Failed to process queued message %d: %s", entry.id, exc)
                entry.status = "failed"
                entry.error_message = str(exc)[:500]
                entry.retry_count += 1
                await self.db.commit()
                failed += 1

        return {
            "processed": processed,
            "escalated": escalated,
            "failed": failed,
        }


# =============================================================================
# Analytics Service
# =============================================================================


class AnalyticsService:
    """Service for social media analytics aggregation.

    Handles daily snapshots, trend analysis, and dashboard data.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_snapshot(
        self, company_id: int, data: SocialAnalyticsCreate, branch_id: Optional[int] = None
    ) -> SocialAnalytic:
        """Create an analytics snapshot.

        Args:
            company_id: Tenant company ID.
            data: Analytics data.
            branch_id: Optional branch ID.

        Returns:
            Created snapshot.
        """
        snapshot = SocialAnalytic(
            company_id=company_id,
            branch_id=branch_id,
            account_id=data.account_id,
            platform=data.platform,
            metric_date=data.metric_date,
            impressions=data.impressions,
            reach=data.reach,
            engagement=data.engagement,
            clicks=data.clicks,
            shares=data.shares,
            comments=data.comments,
            likes=data.likes,
            followers_gained=data.followers_gained,
            followers_lost=data.followers_lost,
            raw_data=data.raw_data,
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot

    async def list_analytics(
        self,
        company_id: int,
        account_id: Optional[int] = None,
        platform: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List analytics snapshots.

        Args:
            company_id: Tenant company ID.
            account_id: Filter by account.
            platform: Filter by platform.
            start_date: Filter start date.
            end_date: Filter end date.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response.
        """
        query = select(SocialAnalytic).where(SocialAnalytic.company_id == company_id)

        if account_id:
            query = query.where(SocialAnalytic.account_id == account_id)
        if platform:
            query = query.where(SocialAnalytic.platform == platform)
        if start_date:
            query = query.where(SocialAnalytic.metric_date >= start_date)
        if end_date:
            query = query.where(SocialAnalytic.metric_date <= end_date)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialAnalytic.metric_date))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(items),
        }

    async def get_dashboard(self, company_id: int) -> AnalyticsDashboard:
        """Generate aggregated analytics dashboard.

        Args:
            company_id: Tenant company ID.

        Returns:
            Dashboard data with totals and trends.
        """
        # Last 7 days range
        end_date = datetime.utcnow()
        start_date_7d = end_date - timedelta(days=7)
        start_date_14d = end_date - timedelta(days=14)

        # Total followers (from accounts)
        accounts_result = await self.db.execute(
            select(func.sum(SocialAccount.follower_count))
            .where(
                and_(
                    SocialAccount.company_id == company_id,
                    SocialAccount.status == AccountStatus.ACTIVE,
                )
            )
        )
        total_followers = accounts_result.scalar() or 0

        # Last 7 days metrics
        metrics_7d = await self.db.execute(
            select(
                func.sum(SocialAnalytic.impressions),
                func.sum(SocialAnalytic.engagement),
                func.sum(SocialAnalytic.clicks),
            )
            .where(
                and_(
                    SocialAnalytic.company_id == company_id,
                    SocialAnalytic.metric_date >= start_date_7d,
                    SocialAnalytic.metric_date <= end_date,
                )
            )
        )
        impressions_7d, engagement_7d, clicks_7d = metrics_7d.one_or_none() or (0, 0, 0)

        # Previous 7 days metrics for change calculation
        metrics_14d = await self.db.execute(
            select(
                func.sum(SocialAnalytic.impressions),
                func.sum(SocialAnalytic.engagement),
            )
            .where(
                and_(
                    SocialAnalytic.company_id == company_id,
                    SocialAnalytic.metric_date >= start_date_14d,
                    SocialAnalytic.metric_date < start_date_7d,
                )
            )
        )
        impressions_prev, engagement_prev = metrics_14d.one_or_none() or (0, 0)

        impressions_change = (impressions_7d or 0) - (impressions_prev or 0)

        # Engagement rate
        total_impressions = impressions_7d or 0
        total_engagement = engagement_7d or 0
        engagement_rate = (total_engagement / total_impressions * 100) if total_impressions > 0 else 0.0

        # Platform breakdown
        platform_result = await self.db.execute(
            select(
                SocialAnalytic.platform,
                func.sum(SocialAnalytic.impressions),
                func.sum(SocialAnalytic.engagement),
                func.sum(SocialAnalytic.clicks),
            )
            .where(
                and_(
                    SocialAnalytic.company_id == company_id,
                    SocialAnalytic.metric_date >= start_date_7d,
                )
            )
            .group_by(SocialAnalytic.platform)
        )
        platform_breakdown = [
            {
                "platform": row[0],
                "impressions": row[1] or 0,
                "engagement": row[2] or 0,
                "clicks": row[3] or 0,
            }
            for row in platform_result.all()
        ]

        # Daily trend (last 14 days)
        trend_result = await self.db.execute(
            select(
                func.date(SocialAnalytic.metric_date).label("date"),
                func.sum(SocialAnalytic.impressions),
                func.sum(SocialAnalytic.engagement),
                func.sum(SocialAnalytic.clicks),
                func.sum(SocialAnalytic.likes),
            )
            .where(
                and_(
                    SocialAnalytic.company_id == company_id,
                    SocialAnalytic.metric_date >= start_date_14d,
                )
            )
            .group_by(func.date(SocialAnalytic.metric_date))
            .order_by(asc("date"))
        )
        daily_trend = [
            {
                "date": str(row[0]),
                "impressions": row[1] or 0,
                "engagement": row[2] or 0,
                "clicks": row[3] or 0,
                "likes": row[4] or 0,
            }
            for row in trend_result.all()
        ]

        # Followers change (approximate from analytics)
        followers_result = await self.db.execute(
            select(
                func.sum(SocialAnalytic.followers_gained),
                func.sum(SocialAnalytic.followers_lost),
            )
            .where(
                and_(
                    SocialAnalytic.company_id == company_id,
                    SocialAnalytic.metric_date >= start_date_7d,
                )
            )
        )
        gained, lost = followers_result.one_or_none() or (0, 0)
        followers_change_7d = (gained or 0) - (lost or 0)

        return AnalyticsDashboard(
            total_followers=int(total_followers),
            total_impressions=int(total_impressions),
            total_engagement=int(total_engagement),
            total_clicks=int(clicks_7d or 0),
            followers_change_7d=followers_change_7d,
            impressions_change_7d=int(impressions_change),
            engagement_rate_avg=round(engagement_rate, 2),
            platform_breakdown=platform_breakdown,
            daily_trend=daily_trend,
        )

    async def sync_account_analytics(
        self, company_id: int, account_id: int
    ) -> Dict[str, Any]:
        """Sync analytics for a specific account from the platform.

        Args:
            company_id: Tenant company ID.
            account_id: Account ID.

        Returns:
            Sync result.
        """
        result = await self.db.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.id == account_id,
                    SocialAccount.company_id == company_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("Account not found")

        access_token = CredentialManager.decrypt_access_token(account.access_token)
        client = get_platform_client(account.platform, access_token, account.account_id)

        try:
            raw_data = {}
            impressions = reach = engagement = clicks = shares = comments = likes = 0
            followers_gained = followers_lost = 0

            if account.platform == "instagram":
                ig_client = cast(InstagramClient, client)
                insights = await ig_client.get_insights(metric_period="day")
                raw_data = insights
                data = insights.get("data", [])
                for metric in data:
                    name = metric.get("name", "")
                    values = metric.get("values", [])
                    val = values[0].get("value", 0) if values else 0
                    if name == "impressions":
                        impressions = val
                    elif name == "reach":
                        reach = val
                    elif name == "profile_views":
                        engagement = val

            elif account.platform == "facebook":
                fb_client = cast(MetaClient, client)
                insights = await fb_client.get_page_insights(metric_period="day")
                raw_data = insights
                data = insights.get("data", [])
                for metric in data:
                    name = metric.get("name", "")
                    values = metric.get("values", [])
                    val = values[0].get("value", 0) if values else 0
                    if name == "page_impressions":
                        impressions = val
                    elif name == "page_impressions_unique":
                        reach = val
                    elif name == "page_engaged_users":
                        engagement = val
                    elif name == "page_actions_post_reactions_total":
                        likes = val
                    elif name == "page_fan_adds":
                        followers_gained = val
                    elif name == "page_fan_removes":
                        followers_lost = val

            # Create snapshot
            snapshot_data = SocialAnalyticsCreate(
                account_id=account_id,
                platform=account.platform.value,
                metric_date=datetime.utcnow(),
                impressions=impressions,
                reach=reach,
                engagement=engagement,
                clicks=clicks,
                shares=shares,
                comments=comments,
                likes=likes,
                followers_gained=followers_gained,
                followers_lost=followers_lost,
                raw_data=raw_data,
            )
            await self.create_snapshot(company_id, snapshot_data)

            # Update account follower count
            account_info = await client.get_account_info()
            new_followers = (
                account_info.get("followers_count")
                or account_info.get("fan_count")
                or account_info.get("follower_count")
                or account.follower_count
            )
            account.follower_count = int(new_followers) if new_followers else account.follower_count
            account.last_sync_at = datetime.utcnow()
            await self.db.commit()

            return {"success": True, "message": "Analytics synced"}

        except Exception as exc:
            logger.error("Failed to sync analytics for account %d: %s", account_id, exc)
            return {"success": False, "message": f"Sync failed: {str(exc)}"}
        finally:
            await client.close()


# =============================================================================
# Competitor Service
# =============================================================================


class CompetitorService:
    """Service for tracking competitor social media accounts.

    Handles competitor CRUD, metrics collection, and trend comparison.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_competitor(
        self, company_id: int, data: SocialCompetitorCreate, branch_id: Optional[int] = None
    ) -> SocialCompetitor:
        """Add a competitor to track.

        Args:
            company_id: Tenant company ID.
            data: Competitor data.
            branch_id: Optional branch ID.

        Returns:
            Created competitor.
        """
        competitor = SocialCompetitor(
            company_id=company_id,
            branch_id=branch_id,
            platform=data.platform,
            competitor_name=data.competitor_name,
            competitor_account_id=data.competitor_account_id,
        )
        self.db.add(competitor)
        await self.db.commit()
        await self.db.refresh(competitor)
        return competitor

    async def get_competitor(self, competitor_id: int, company_id: int) -> SocialCompetitor:
        """Get a competitor by ID.

        Args:
            competitor_id: Competitor ID.
            company_id: Tenant company ID.

        Returns:
            SocialCompetitor instance.
        """
        result = await self.db.execute(
            select(SocialCompetitor).where(
                and_(
                    SocialCompetitor.id == competitor_id,
                    SocialCompetitor.company_id == company_id,
                )
            )
        )
        competitor = result.scalar_one_or_none()
        if not competitor:
            raise NotFoundError(f"Competitor {competitor_id} not found")
        return competitor

    async def list_competitors(
        self,
        company_id: int,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List tracked competitors.

        Args:
            company_id: Tenant company ID.
            platform: Filter by platform.
            page: Page number.
            page_size: Items per page.

        Returns:
            Paginated response.
        """
        query = select(SocialCompetitor).where(SocialCompetitor.company_id == company_id)

        if platform:
            query = query.where(SocialCompetitor.platform == platform)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialCompetitor.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        competitors = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(competitors),
        }

    async def update_competitor(
        self,
        competitor_id: int,
        company_id: int,
        data: SocialCompetitorUpdate,
    ) -> SocialCompetitor:
        """Update competitor data.

        Args:
            competitor_id: Competitor ID.
            company_id: Tenant company ID.
            data: Update data.

        Returns:
            Updated competitor.
        """
        competitor = await self.get_competitor(competitor_id, company_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(competitor, field, value)
        await self.db.commit()
        await self.db.refresh(competitor)
        return competitor

    async def delete_competitor(self, competitor_id: int, company_id: int) -> None:
        """Remove a competitor.

        Args:
            competitor_id: Competitor ID.
            company_id: Tenant company ID.
        """
        competitor = await self.get_competitor(competitor_id, company_id)
        await self.db.delete(competitor)
        await self.db.commit()

    async def analyze_competitor(
        self, competitor_id: int, company_id: int
    ) -> Dict[str, Any]:
        """Fetch and update competitor metrics from the platform.

        Note: This uses public data where available. Some platforms require
        authentication for full competitor data.

        Args:
            competitor_id: Competitor ID.
            company_id: Tenant company ID.

        Returns:
            Analysis result.
        """
        competitor = await self.get_competitor(competitor_id, company_id)

        try:
            # Store current metrics in history before updating
            if competitor.follower_count is not None:
                history_entry = {
                    "date": datetime.utcnow().isoformat(),
                    "follower_count": competitor.follower_count,
                    "post_count": competitor.post_count,
                    "avg_engagement": float(competitor.avg_engagement) if competitor.avg_engagement else None,
                }
                current_history = list(competitor.metrics_history or [])
                current_history.append(history_entry)
                # Keep last 52 entries (1 year weekly)
                competitor.metrics_history = current_history[-52:]

            # Fetch competitor data via public APIs where available
            # Instagram and Facebook: no public API without auth - use available endpoints
            # Telegram: public bot API can get chat member counts
            # Google Maps: Places API can fetch public reviews and ratings
            if competitor.platform == "telegram":
                # Use Telegram Bot API to get chat member count
                try:
                    from sqlalchemy import select as sa_select
                    acct_result = await self.db.execute(
                        sa_select(SocialAccount).where(
                            SocialAccount.platform == SocialPlatform.TELEGRAM,
                            SocialAccount.company_id == company_id,
                        )
                    )
                    bot_account = acct_result.scalar_one_or_none()
                    if bot_account and bot_account.access_token:
                        token = CredentialManager.decrypt_access_token(bot_account.access_token)
                        tg_client = TelegramClient(bot_token=token)
                        count_result = await tg_client.get_account_info()
                        # Note: getting competitor chat info requires the bot to be in the chat
                        await tg_client.close()
                except Exception:
                    pass  # Silent fail - competitor data may not be accessible

            elif competitor.platform == "google_maps":
                # Use Places API to get public place details
                try:
                    from sqlalchemy import select as sa_select
                    acct_result = await self.db.execute(
                        sa_select(SocialAccount).where(
                            SocialAccount.platform == SocialPlatform.GOOGLE_MAPS,
                            SocialAccount.company_id == company_id,
                        )
                    )
                    maps_account = acct_result.scalar_one_or_none()
                    if maps_account and maps_account.access_token:
                        token = CredentialManager.decrypt_access_token(maps_account.access_token)
                        gm_client = GoogleMapsClient(access_token=token)
                        await gm_client.close()
                except Exception:
                    pass  # Silent fail

            await self.db.commit()
            return {"success": True, "competitor_id": competitor.id}

        except Exception as exc:
            logger.error("Competitor analysis failed: %s", exc)
            return {"success": False, "error": str(exc)}


# =============================================================================
# Inbound Message Service  (webhook -> message record -> ticket creation)
# =============================================================================


class InboundMessageService:
    """Process inbound messages from WhatsApp/Telegram webhooks.

    Flow: webhook payload -> parse -> store message -> find/create ticket
    -> trigger AI auto-reply or escalation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager()

    async def process_whatsapp_message(
        self,
        company_id: int,
        account_id: int,
        parsed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process an inbound WhatsApp message.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            parsed: Parsed message from WhatsAppClient.parse_inbound_message().

        Returns:
            Dict with message_id, ticket_id, action taken.
        """
        from sqlalchemy import select as sa_select

        # 1. Store the inbound message
        conversation_id = parsed["from_number"]
        message = SocialMessage(
            company_id=company_id,
            account_id=account_id,
            platform=SocialPlatform.WHATSAPP,
            external_conversation_id=conversation_id,
            external_message_id=parsed.get("message_id"),
            sender_name=parsed.get("profile_name", "Unknown"),
            sender_id=parsed["from_number"],
            content=parsed.get("body", ""),
            direction=MessageDirection.INBOUND,
            status=MessageStatus.NEW,
        )
        self.db.add(message)
        await self.db.flush()

        # 2. Find or create a support ticket for this conversation
        ticket_result = await self.db.execute(
            sa_select(SupportTicket).where(
                SupportTicket.company_id == company_id,
                SupportTicket.source == "whatsapp",
                SupportTicket.source_conversation_id == conversation_id,
                SupportTicket.status.notin_(["resolved", "closed"]),
            )
        )
        ticket = ticket_result.scalar_one_or_none()

        from app.support.service import TicketService, MessageService

        if not ticket:
            # Create new ticket
            ticket_service = TicketService(self.db)
            ticket = await ticket_service.create_ticket(
                company_id=company_id,
                branch_id=None,  # Will be resolved from account
                data={
                    "customer_id": parsed["from_number"],
                    "customer_name": parsed.get("profile_name", "WhatsApp User"),
                    "source": "whatsapp",
                    "source_conversation_id": conversation_id,
                    "subject": parsed.get("body", "WhatsApp message")[:100],
                    "initial_message": parsed.get("body", ""),
                    "priority": "medium",
                },
            )
            action = "created_ticket"
        else:
            # Add message to existing ticket
            message_service = MessageService(self.db)
            await message_service.add_message(
                ticket_id=ticket.id,
                company_id=company_id,
                data={
                    "sender_type": "customer",
                    "content": parsed.get("body", ""),
                },
            )
            action = "added_to_existing_ticket"

        await self.db.commit()

        return {
            "success": True,
            "message_id": message.id,
            "ticket_id": ticket.id,
            "action": action,
            "conversation_id": conversation_id,
        }

    async def process_telegram_message(
        self,
        company_id: int,
        account_id: int,
        parsed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process an inbound Telegram message.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            parsed: Parsed message from TelegramClient.parse_inbound_update().

        Returns:
            Dict with message_id, ticket_id, action taken.
        """
        from sqlalchemy import select as sa_select

        chat_id = str(parsed["chat_id"])
        conversation_id = chat_id

        # 1. Store the inbound message
        message = SocialMessage(
            company_id=company_id,
            account_id=account_id,
            platform=SocialPlatform.TELEGRAM,
            external_conversation_id=conversation_id,
            external_message_id=str(parsed.get("message_id", "")),
            sender_name=parsed.get("from_first_name", "Telegram User"),
            sender_id=str(parsed.get("from_user_id", "")),
            content=parsed.get("text", ""),
            direction=MessageDirection.INBOUND,
            status=MessageStatus.NEW,
        )
        self.db.add(message)
        await self.db.flush()

        # 2. Find or create a support ticket
        ticket_result = await self.db.execute(
            sa_select(SupportTicket).where(
                SupportTicket.company_id == company_id,
                SupportTicket.source == "telegram",
                SupportTicket.source_conversation_id == conversation_id,
                SupportTicket.status.notin_(["resolved", "closed"]),
            )
        )
        ticket = ticket_result.scalar_one_or_none()

        from app.support.service import TicketService, MessageService

        if not ticket:
            ticket_service = TicketService(self.db)
            ticket = await ticket_service.create_ticket(
                company_id=company_id,
                branch_id=None,
                data={
                    "customer_id": str(parsed.get("from_user_id", "")),
                    "customer_name": parsed.get("from_first_name", "Telegram User"),
                    "customer_email": None,
                    "source": "telegram",
                    "source_conversation_id": conversation_id,
                    "subject": parsed.get("text", "Telegram message")[:100],
                    "initial_message": parsed.get("text", ""),
                    "priority": "medium",
                },
            )
            action = "created_ticket"
        else:
            message_service = MessageService(self.db)
            await message_service.add_message(
                ticket_id=ticket.id,
                company_id=company_id,
                data={
                    "sender_type": "customer",
                    "content": parsed.get("text", ""),
                },
            )
            action = "added_to_existing_ticket"

        await self.db.commit()

        return {
            "success": True,
            "message_id": message.id,
            "ticket_id": ticket.id,
            "action": action,
            "conversation_id": conversation_id,
        }


# =============================================================================
# Outbound Message Service  (reply -> API send -> status tracking)
# =============================================================================


class OutboundMessageService:
    """Send outbound replies via WhatsApp/Telegram APIs and track status.

    Flow: support reply -> detect platform -> API send -> store status.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager()

    async def send_reply(
        self,
        ticket_id: int,
        company_id: int,
        content: str,
        sender_id: Optional[int] = None,
        ai_generated: bool = False,
        ai_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send a reply to the original channel (WhatsApp or Telegram).

        Args:
            ticket_id: Support ticket ID.
            company_id: Tenant company ID.
            content: Reply text.
            sender_id: Agent user ID.
            ai_generated: Whether reply was AI-generated.
            ai_confidence: AI confidence score.

        Returns:
            Dict with success, message_id, api_message_id.
        """
        from sqlalchemy import select as sa_select
        from app.support.models import SupportTicket

        # Get ticket to find source and conversation
        ticket_result = await self.db.execute(
            sa_select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = ticket_result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        source = ticket.source
        conversation_id = ticket.source_conversation_id
        if not conversation_id:
            return {
                "success": False,
                "message": "Ticket has no source conversation ID",
            }

        # Get the social account for this source
        account_result = await self.db.execute(
            sa_select(SocialAccount).where(
                SocialAccount.company_id == company_id,
                SocialAccount.platform == source,
            )
        )
        account = account_result.scalar_one_or_none()
        if not account:
            return {
                "success": False,
                "message": f"No {source} account connected",
            }

        # Decrypt token
        try:
            token = self.credential_manager.decrypt_access_token(account.access_token)
        except Exception:
            return {"success": False, "message": "Failed to decrypt access token"}

        # Send via appropriate API
        api_response: Dict[str, Any] = {}
        api_message_id: Optional[str] = None

        try:
            if source == "whatsapp":
                client = WhatsAppClient(
                    access_token=token,
                    phone_number_id=account.account_id,
                )
                api_response = await client.send_text_message(
                    to=conversation_id,
                    body=content,
                )
                api_message_id = api_response.get("messages", [{}])[0].get("id")
                await client.close()

            elif source == "telegram":
                client = TelegramClient(bot_token=token)
                api_response = await client.send_message(
                    chat_id=int(conversation_id),
                    text=content,
                )
                api_message_id = str(api_response.get("result", {}).get("message_id"))
                await client.close()

            else:
                return {
                    "success": False,
                    "message": f"Unsupported source: {source}",
                }

        except Exception as exc:
            logger.error("Failed to send %s reply for ticket %d: %s", source, ticket_id, exc)
            return {
                "success": False,
                "message": f"API send failed: {str(exc)}",
            }

        # Store outbound message record
        message = SocialMessage(
            company_id=company_id,
            account_id=account.id,
            platform=getattr(SocialPlatform, source.upper(), None),
            external_conversation_id=conversation_id,
            external_message_id=api_message_id,
            sender_name="Agent" if not ai_generated else "AI",
            sender_id=str(sender_id) if sender_id else None,
            content=content,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.REPLIED,
        )
        self.db.add(message)

        # Add to support ticket as well
        from app.support.service import MessageService
        message_service = MessageService(self.db)
        await message_service.add_message(
            ticket_id=ticket_id,
            company_id=company_id,
            data={
                "sender_type": "ai" if ai_generated else "agent",
                "sender_id": sender_id,
                "content": content,
                "ai_generated": ai_generated,
                "ai_confidence": ai_confidence,
            },
        )

        await self.db.commit()
        await self.db.refresh(message)

        return {
            "success": True,
            "message_id": message.id,
            "api_message_id": api_message_id,
            "platform": source,
        }

    async def send_whatsapp_reply(
        self,
        account_id: int,
        company_id: int,
        to: str,
        content: str,
        message_type: str = "text",
    ) -> Dict[str, Any]:
        """Send a WhatsApp reply directly.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.
            to: Recipient phone number.
            content: Message content.
            message_type: 'text', 'image', 'document', 'interactive'.

        Returns:
            API response.
        """
        account = await self._get_account(account_id, company_id)
        token = self.credential_manager.decrypt_access_token(account.access_token)
        client = WhatsAppClient(access_token=token, phone_number_id=account.account_id)

        try:
            if message_type == "text":
                result = await client.send_text_message(to=to, body=content)
            elif message_type == "interactive":
                result = await client.send_interactive_message(
                    to=to,
                    body_text=content,
                    buttons=[
                        {"id": "yes", "title": "Yes"},
                        {"id": "no", "title": "No"},
                    ],
                )
            else:
                result = await client.send_text_message(to=to, body=content)
            return {"success": True, "api_response": result}
        except Exception as exc:
            logger.error("WhatsApp send failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            await client.close()

    async def send_telegram_reply(
        self,
        account_id: int,
        company_id: int,
        chat_id: Union[str, int],
        content: str,
        use_inline_keyboard: bool = False,
    ) -> Dict[str, Any]:
        """Send a Telegram reply directly.

        Args:
            account_id: Social account ID.
            company_id: Tenant company ID.
            chat_id: Target chat ID.
            content: Message text.
            use_inline_keyboard: Whether to include action buttons.

        Returns:
            API response.
        """
        account = await self._get_account(account_id, company_id)
        token = self.credential_manager.decrypt_access_token(account.access_token)
        client = TelegramClient(bot_token=token)

        try:
            if use_inline_keyboard:
                result = await client.send_inline_keyboard(
                    chat_id=chat_id,
                    text=content,
                    buttons=[
                        [
                            {"text": "Resolve", "callback_data": "resolve"},
                            {"text": "Escalate", "callback_data": "escalate"},
                        ]
                    ],
                )
            else:
                result = await client.send_message(chat_id=chat_id, text=content)
            return {"success": True, "api_response": result}
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            await client.close()

    async def _get_account(self, account_id: int, company_id: int) -> SocialAccount:
        """Get social account with validation."""
        from sqlalchemy import select as sa_select
        result = await self.db.execute(
            sa_select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.company_id == company_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Account {account_id} not found")
        return account


# =============================================================================
# Inbound Message Service (Instagram/Facebook DM -> queue -> ticket)
# =============================================================================


class InboundMessageService:
    """Process inbound Instagram/Facebook DM messages.

    Flow: webhook -> parse -> queue -> create SocialMessage + ticket.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_instagram_dm(
        self,
        company_id: int,
        account_id: int,
        sender_id: str,
        sender_name: str,
        message_text: str,
        message_mid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process an inbound Instagram DM message.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            sender_id: Instagram-scoped user ID.
            sender_name: Sender display name.
            message_text: Message content.
            message_mid: Platform message ID.

        Returns:
            Dict with message_id, ticket_id, action.
        """
        from sqlalchemy import select as sa_select
        from app.support.models import SupportTicket
        from app.support.service import TicketService as SupportTicketService
        from app.support.service import MessageService as SupportMessageService

        conversation_id = sender_id

        # 1. Queue the incoming message
        msg_service = MessageService(self.db)
        queue_entry = await msg_service.queue_incoming_message(
            company_id=company_id,
            account_id=account_id,
            platform="instagram",
            external_conversation_id=conversation_id,
            external_message_id=message_mid,
            sender_name=sender_name,
            sender_id=sender_id,
            content=message_text,
        )

        # 2. Create the actual message record
        message = await msg_service.create_message(
            company_id,
            SocialMessageCreate(
                account_id=account_id,
                platform="instagram",
                external_conversation_id=conversation_id,
                external_message_id=message_mid,
                sender_name=sender_name,
                sender_id=sender_id,
                content=message_text,
                direction="inbound",
            ),
        )

        # 3. Run sentiment analysis
        sentiment_result = await msg_service.analyze_message_sentiment(message.id, company_id)

        # 4. Generate AI reply suggestion (auto-send OFF by default)
        await msg_service.generate_ai_reply_suggestion(message.id, company_id)

        # 5. Find or create a support ticket
        ticket_result = await self.db.execute(
            sa_select(SupportTicket).where(
                SupportTicket.company_id == company_id,
                SupportTicket.source == "instagram",
                SupportTicket.source_conversation_id == conversation_id,
                SupportTicket.status.notin_(["resolved", "closed"]),
            )
        )
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            priority = "high" if sentiment_result.get("escalated") else "medium"
            ticket_service = SupportTicketService(self.db)
            ticket = await ticket_service.create_ticket(
                company_id=company_id,
                branch_id=None,
                data={
                    "customer_id": sender_id,
                    "customer_name": sender_name,
                    "source": "instagram",
                    "source_conversation_id": conversation_id,
                    "subject": message_text[:100],
                    "initial_message": message_text,
                    "priority": priority,
                },
            )
            action = "created_ticket"
        else:
            support_msg_service = SupportMessageService(self.db)
            await support_msg_service.add_message(
                ticket_id=ticket.id,
                company_id=company_id,
                data={
                    "sender_type": "customer",
                    "content": message_text,
                },
            )
            # Escalate if negative sentiment detected
            if sentiment_result.get("escalated") and ticket.priority != "urgent":
                ticket.priority = "high"
            action = "added_to_existing_ticket"

        # Mark queue entry as completed
        queue_entry.status = "completed"
        queue_entry.processed_at = datetime.utcnow()
        await self.db.commit()

        return {
            "success": True,
            "message_id": message.id,
            "ticket_id": ticket.id,
            "action": action,
            "sentiment": sentiment_result.get("sentiment"),
            "escalated": sentiment_result.get("escalated"),
            "conversation_id": conversation_id,
        }

    async def process_facebook_messenger(
        self,
        company_id: int,
        account_id: int,
        sender_id: str,
        sender_name: str,
        message_text: str,
        message_mid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process an inbound Facebook Messenger message.

        Args:
            company_id: Tenant company ID.
            account_id: Social account ID.
            sender_id: Page-scoped user ID (PSID).
            sender_name: Sender display name.
            message_text: Message content.
            message_mid: Platform message ID.

        Returns:
            Dict with message_id, ticket_id, action.
        """
        from sqlalchemy import select as sa_select
        from app.support.models import SupportTicket
        from app.support.service import TicketService as SupportTicketService
        from app.support.service import MessageService as SupportMessageService

        conversation_id = sender_id

        # 1. Queue the incoming message
        msg_service = MessageService(self.db)
        queue_entry = await msg_service.queue_incoming_message(
            company_id=company_id,
            account_id=account_id,
            platform="facebook",
            external_conversation_id=conversation_id,
            external_message_id=message_mid,
            sender_name=sender_name,
            sender_id=sender_id,
            content=message_text,
        )

        # 2. Create the actual message record
        message = await msg_service.create_message(
            company_id,
            SocialMessageCreate(
                account_id=account_id,
                platform="facebook",
                external_conversation_id=conversation_id,
                external_message_id=message_mid,
                sender_name=sender_name,
                sender_id=sender_id,
                content=message_text,
                direction="inbound",
            ),
        )

        # 3. Run sentiment analysis
        sentiment_result = await msg_service.analyze_message_sentiment(message.id, company_id)

        # 4. Generate AI reply suggestion (auto-send OFF by default)
        await msg_service.generate_ai_reply_suggestion(message.id, company_id)

        # 5. Find or create a support ticket
        ticket_result = await self.db.execute(
            sa_select(SupportTicket).where(
                SupportTicket.company_id == company_id,
                SupportTicket.source == "facebook",
                SupportTicket.source_conversation_id == conversation_id,
                SupportTicket.status.notin_(["resolved", "closed"]),
            )
        )
        ticket = ticket_result.scalar_one_or_none()

        if not ticket:
            priority = "high" if sentiment_result.get("escalated") else "medium"
            ticket_service = SupportTicketService(self.db)
            ticket = await ticket_service.create_ticket(
                company_id=company_id,
                branch_id=None,
                data={
                    "customer_id": sender_id,
                    "customer_name": sender_name,
                    "source": "facebook",
                    "source_conversation_id": conversation_id,
                    "subject": message_text[:100],
                    "initial_message": message_text,
                    "priority": priority,
                },
            )
            action = "created_ticket"
        else:
            support_msg_service = SupportMessageService(self.db)
            await support_msg_service.add_message(
                ticket_id=ticket.id,
                company_id=company_id,
                data={
                    "sender_type": "customer",
                    "content": message_text,
                },
            )
            if sentiment_result.get("escalated") and ticket.priority != "urgent":
                ticket.priority = "high"
            action = "added_to_existing_ticket"

        # Mark queue entry as completed
        queue_entry.status = "completed"
        queue_entry.processed_at = datetime.utcnow()
        await self.db.commit()

        return {
            "success": True,
            "message_id": message.id,
            "ticket_id": ticket.id,
            "action": action,
            "sentiment": sentiment_result.get("sentiment"),
            "escalated": sentiment_result.get("escalated"),
            "conversation_id": conversation_id,
        }


# =============================================================================
# Context Managers for Service Lifecycles
# =============================================================================


class ServiceContext:
    """Context manager for bulk service operations.

    Ensures all API clients are properly closed after operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.account_service = SocialAccountService(db)
        self.post_service = PostService(db)
        self.comment_service = CommentService(db)
        self.message_service = MessageService(db)
        self.analytics_service = AnalyticsService(db)
        self.competitor_service = CompetitorService(db)
        self.webhook_service = WebhookService(db)
        self.inbound_service = InboundMessageService(db)
        self.outbound_service = OutboundMessageService(db)

    async def __aenter__(self) -> "ServiceContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up any resources on exit."""
        pass  # httpx clients auto-close via context managers

# =============================================================================
# Webhook Service
# =============================================================================


class WebhookService:
    """Service for handling webhook events from social platforms.

    Handles webhook reception, signature validation, event logging,
    and queued processing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self,
        company_id: int,
        platform: str,
        event_type: str,
        payload: Dict[str, Any],
        account_id: Optional[int] = None,
    ) -> SocialWebhook:
        """Create a webhook event record."""
        event = SocialWebhook(
            company_id=company_id,
            account_id=account_id,
            platform=platform,
            event_type=event_type,
            payload=payload,
            processed=False,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def list_events(
        self,
        company_id: int,
        platform: Optional[str] = None,
        processed: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List webhook events."""
        query = select(SocialWebhook).where(SocialWebhook.company_id == company_id)

        if platform:
            query = query.where(SocialWebhook.platform == platform)
        if processed is not None:
            query = query.where(SocialWebhook.processed == processed)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialWebhook.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        events = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(events),
        }

    async def get_event(self, event_id: int, company_id: int) -> SocialWebhook:
        """Get a webhook event by ID."""
        result = await self.db.execute(
            select(SocialWebhook).where(
                and_(
                    SocialWebhook.id == event_id,
                    SocialWebhook.company_id == company_id,
                )
            )
        )
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundError(f"Webhook event {event_id} not found")
        return event

    async def process_event(self, event_id: int, company_id: int) -> Dict[str, Any]:
        """Process a webhook event."""
        event = await self.get_event(event_id, company_id)

        try:
            if event.platform == "whatsapp":
                await self._process_whatsapp_event(event, company_id)
            elif event.platform == "telegram":
                await self._process_telegram_event(event, company_id)
            elif event.platform in ("instagram", "facebook"):
                await self._process_meta_event(event, company_id)
            else:
                event.processed = True
                event.processed_at = datetime.utcnow()
                await self.db.commit()
                return {"success": True, "message": "Event acknowledged"}

            event.processed = True
            event.processed_at = datetime.utcnow()
            await self.db.commit()
            return {"success": True, "message": "Event processed"}

        except Exception as exc:
            logger.error("Failed to process webhook event %d: %s", event_id, exc)
            event.error_message = str(exc)[:500]
            await self.db.commit()
            return {"success": False, "message": f"Processing failed: {str(exc)}"}

    async def _process_whatsapp_event(
        self, event: SocialWebhook, company_id: int
    ) -> None:
        """Process a WhatsApp webhook event."""
        payload = event.payload
        entry = payload.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    message_data = SocialMessageCreate(
                        account_id=event.account_id or 0,
                        platform="whatsapp",
                        external_conversation_id=msg.get("from", ""),
                        external_message_id=msg.get("id"),
                        sender_name=msg.get("from", "Unknown"),
                        sender_id=msg.get("from"),
                        content=msg.get("text", {}).get("body", ""),
                        direction="inbound",
                    )
                    service = MessageService(self.db)
                    await service.create_message(company_id, message_data)

    async def _process_telegram_event(
        self, event: SocialWebhook, company_id: int
    ) -> None:
        """Process a Telegram webhook event."""
        payload = event.payload
        tg_message = payload.get("message", {})
        if tg_message:
            chat = tg_message.get("chat", {})
            from_user = tg_message.get("from", {})
            message_data = SocialMessageCreate(
                account_id=event.account_id or 0,
                platform="telegram",
                external_conversation_id=str(chat.get("id", "")),
                external_message_id=str(tg_message.get("message_id", "")),
                sender_name=from_user.get("first_name", "Unknown"),
                sender_id=str(from_user.get("id", "")),
                content=tg_message.get("text", ""),
                direction="inbound",
            )
            service = MessageService(self.db)
            await service.create_message(company_id, message_data)

    async def _process_meta_event(
        self, event: SocialWebhook, company_id: int
    ) -> None:
        """Process Facebook/Instagram webhook events."""
        payload = event.payload
        entry = payload.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for change in changes:
                field = change.get("field", "")
                value = change.get("value", {})

                if field in ("mentions", "mentions_comment"):
                    # Handle mention events - create comment record
                    pass
                elif field == "feed":
                    # New post/comment on feed
                    item = value.get("item", "")
                    if item == "comment":
                        comment_data = SocialCommentCreate(
                            account_id=event.account_id or 0,
                            post_id=0,  # Will be resolved
                            external_comment_id=str(value.get("comment_id", "")),
                            author_name=value.get("from", {}).get("name", "Unknown"),
                            author_id=str(value.get("from", {}).get("id", "")),
                            content=value.get("message", ""),
                        )
                        service = CommentService(self.db)
                        await service.create_comment(company_id, comment_data)
                elif field == "messages":
                    # DM received
                    sender = value.get("sender", {})
                    message_data = SocialMessageCreate(
                        account_id=event.account_id or 0,
                        platform=event.platform,
                        external_conversation_id=str(sender.get("id", "")),
                        external_message_id=str(value.get("message_id", "")),
                        sender_name=sender.get("name", "Unknown"),
                        sender_id=str(sender.get("id", "")),
                        content=value.get("message", ""),
                        direction="inbound",
                    )
                    service = MessageService(self.db)
                    await service.create_message(company_id, message_data)

    def verify_webhook_signature(
        self,
        platform: str,
        payload: bytes,
        signature: Optional[str],
        secret: Optional[str] = None,
    ) -> bool:
        """Verify webhook signature for supported platforms.

        Supports:
        - Facebook/Instagram: x-hub-signature-256 (sha256=<hex>)
        - TikTok: x-tiktok-signature (sha256=<hex>)
        - Telegram: secret token header comparison

        Args:
            platform: Platform name.
            payload: Raw request body.
            signature: Signature header value (e.g. "sha256=abc123...").
            secret: Webhook secret/app secret.

        Returns:
            True if signature is valid.
        """
        if not signature or not secret:
            logger.warning(
                "Webhook signature verification skipped: missing signature or secret"
            )
            return False

        if platform in ("facebook", "instagram"):
            sig_parts = signature.split("=", 1)
            if len(sig_parts) != 2:
                logger.warning("Invalid signature format: %s", signature[:20])
                return False
            sig_algo, sig_value = sig_parts
            if sig_algo.lower() != "sha256":
                logger.warning("Unsupported signature algorithm: %s", sig_algo)
                return False
            expected = hmac.new(
                secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, sig_value)

        elif platform == "tiktok":
            sig_parts = signature.split("=", 1)
            if len(sig_parts) == 2:
                sig_algo, sig_value = sig_parts
                if sig_algo.lower() != "sha256":
                    return False
            else:
                sig_value = signature
            expected = hmac.new(
                secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, sig_value)

        elif platform == "telegram":
            return hmac.compare_digest(secret, signature)

        return False

    async def handle_subscription_verification(
        self,
        platform: str,
        hub_mode: Optional[str],
        hub_verify_token: Optional[str],
        hub_challenge: Optional[str],
        expected_verify_token: str,
    ) -> Optional[str]:
        """Handle Facebook/Instagram webhook subscription verification.

        Args:
            platform: Platform name.
            hub_mode: Subscription mode (should be 'subscribe').
            hub_verify_token: Verification token from request.
            hub_challenge: Challenge string to echo back.
            expected_verify_token: Expected verification token.

        Returns:
            Challenge response if verified, None otherwise.
        """
        if hub_mode == "subscribe" and hub_verify_token == expected_verify_token:
            logger.info("Webhook subscription verified for platform: %s", platform)
            return hub_challenge
        logger.warning(
            "Webhook verification failed for %s: mode=%s, token_match=%s",
            platform,
            hub_mode,
            hub_verify_token == expected_verify_token,
        )
        return None


# =============================================================================
# Publishing Queue Service
# =============================================================================


class PublishingQueueService:
    """Service for managing sequential publishing with rate limit control.

    Handles adding posts to queue, processing queue in sequence,
    and respecting rate limits between publishes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager()

    async def add_to_queue(
        self,
        company_id: int,
        account_id: int,
        post_id: int,
        platform: str,
        sequence_order: int = 0,
        scheduled_at: Optional[datetime] = None,
        rate_limit_delay: int = 60,
        branch_id: Optional[int] = None,
    ) -> PublishingQueue:
        """Add a post to the publishing queue."""
        from app.social.models import PublishingQueue, QueueStatus

        # Validate account belongs to company
        result = await self.db.execute(
            select(SocialAccount).where(
                and_(
                    SocialAccount.id == account_id,
                    SocialAccount.company_id == company_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError(f"Account {account_id} not found")

        # Validate post exists and belongs to company
        result = await self.db.execute(
            select(SocialPost).where(
                and_(
                    SocialPost.id == post_id,
                    SocialPost.company_id == company_id,
                    SocialPost.status.in_([PostStatus.DRAFT, PostStatus.SCHEDULED]),
                )
            )
        )
        post = result.scalar_one_or_none()
        if not post:
            raise ValidationError(
                f"Post {post_id} not found or not in draft/scheduled status"
            )

        queue_item = PublishingQueue(
            company_id=company_id,
            branch_id=branch_id,
            account_id=account_id,
            post_id=post_id,
            platform=platform,
            sequence_order=sequence_order,
            status=QueueStatus.PENDING,
            scheduled_at=scheduled_at,
            rate_limit_delay=rate_limit_delay,
        )
        self.db.add(queue_item)
        await self.db.commit()
        await self.db.refresh(queue_item)
        return queue_item

    async def get_queue_item(self, queue_id: int, company_id: int) -> PublishingQueue:
        """Get a queue item by ID."""
        from app.social.models import PublishingQueue

        result = await self.db.execute(
            select(PublishingQueue).where(
                and_(
                    PublishingQueue.id == queue_id,
                    PublishingQueue.company_id == company_id,
                )
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError(f"Queue item {queue_id} not found")
        return item

    async def list_queue(
        self,
        company_id: int,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List publishing queue items."""
        from app.social.models import PublishingQueue

        query = select(PublishingQueue).where(PublishingQueue.company_id == company_id)

        if status:
            query = query.where(PublishingQueue.status == status)
        if platform:
            query = query.where(PublishingQueue.platform == platform)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(
            asc(PublishingQueue.sequence_order),
            asc(PublishingQueue.scheduled_at),
        )
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(items),
        }

    async def update_queue_item(
        self, queue_id: int, company_id: int, data: Dict[str, Any]
    ) -> PublishingQueue:
        """Update a queue item."""
        from app.social.models import PublishingQueue

        item = await self.get_queue_item(queue_id, company_id)

        # Only allow updates on pending items
        from app.social.models import QueueStatus

        if item.status != QueueStatus.PENDING:
            raise ValidationError("Only pending queue items can be updated")

        allowed_fields = {"sequence_order", "scheduled_at", "rate_limit_delay"}
        for field, value in data.items():
            if field in allowed_fields:
                setattr(item, field, value)

        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def remove_from_queue(self, queue_id: int, company_id: int) -> None:
        """Remove a post from the publishing queue."""
        from app.social.models import PublishingQueue, QueueStatus

        item = await self.get_queue_item(queue_id, company_id)
        if item.status == QueueStatus.PROCESSING:
            raise ValidationError("Cannot remove a processing queue item")
        await self.db.delete(item)
        await self.db.commit()

    async def process_queue(self, company_id: int) -> Dict[str, Any]:
        """Process the publishing queue sequentially.

        Publishes pending posts in sequence order, respecting rate limits.

        Returns:
            Processing results summary.
        """
        from app.social.models import PublishingQueue, QueueStatus

        result = await self.db.execute(
            select(PublishingQueue)
            .where(
                and_(
                    PublishingQueue.company_id == company_id,
                    PublishingQueue.status == QueueStatus.PENDING,
                )
            )
            .order_by(
                asc(PublishingQueue.sequence_order),
                asc(PublishingQueue.scheduled_at),
            )
        )
        pending_items = list(result.scalars().all())

        processed = 0
        succeeded = 0
        failed = 0
        skipped = 0
        details = []

        for item in pending_items:
            # Check if scheduled time has passed
            if item.scheduled_at and item.scheduled_at > datetime.utcnow():
                skipped += 1
                details.append(
                    {
                        "queue_id": item.id,
                        "post_id": item.post_id,
                        "status": "skipped",
                        "reason": "Scheduled time not yet reached",
                    }
                )
                continue

            item.status = QueueStatus.PROCESSING
            await self.db.commit()

            try:
                post_service = PostService(self.db)
                result = await post_service.publish_now(item.post_id, company_id)

                if result.get("success"):
                    item.status = QueueStatus.PUBLISHED
                    item.published_at = datetime.utcnow()
                    succeeded += 1
                else:
                    item.status = QueueStatus.FAILED
                    item.retry_count += 1
                    item.last_error = result.get("message", "Unknown error")
                    failed += 1

                await self.db.commit()

                details.append(
                    {
                        "queue_id": item.id,
                        "post_id": item.post_id,
                        "status": "published" if result.get("success") else "failed",
                        "message": result.get("message", ""),
                    }
                )
                processed += 1

                # Rate limit delay before next publish
                if item.rate_limit_delay > 0:
                    await asyncio.sleep(min(item.rate_limit_delay, 300))

            except Exception as exc:
                logger.error("Queue processing failed for item %d: %s", item.id, exc)
                item.status = QueueStatus.FAILED
                item.retry_count += 1
                item.last_error = str(exc)[:500]
                await self.db.commit()
                failed += 1
                details.append(
                    {
                        "queue_id": item.id,
                        "post_id": item.post_id,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "details": details,
        }


# =============================================================================
# Social Listening Service
# =============================================================================


class SocialListeningService:
    """Service for social listening - hashtag/mention/keyword tracking.

    Monitors social platforms for specific hashtags, mentions, or keywords.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_listening(
        self,
        company_id: int,
        data: Dict[str, Any],
        branch_id: Optional[int] = None,
    ) -> SocialListening:
        """Create a new social listening entry."""
        from app.social.models import SocialListening

        entry = SocialListening(
            company_id=company_id,
            branch_id=branch_id,
            platform=data["platform"],
            listen_type=data["listen_type"],
            target=data["target"],
            is_active=data.get("is_active", True),
            settings=data.get("settings", {}),
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_listening(self, listening_id: int, company_id: int) -> SocialListening:
        """Get a listening entry by ID."""
        from app.social.models import SocialListening

        result = await self.db.execute(
            select(SocialListening).where(
                and_(
                    SocialListening.id == listening_id,
                    SocialListening.company_id == company_id,
                )
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise NotFoundError(f"Listening entry {listening_id} not found")
        return entry

    async def list_listening(
        self,
        company_id: int,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List social listening entries."""
        from app.social.models import SocialListening

        query = select(SocialListening).where(SocialListening.company_id == company_id)

        if platform:
            query = query.where(SocialListening.platform == platform)
        if is_active is not None:
            query = query.where(SocialListening.is_active == is_active)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(SocialListening.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(items),
        }

    async def update_listening(
        self, listening_id: int, company_id: int, data: Dict[str, Any]
    ) -> SocialListening:
        """Update a listening entry."""
        from app.social.models import SocialListening

        entry = await self.get_listening(listening_id, company_id)

        for field in ["target", "is_active", "settings"]:
            if field in data:
                setattr(entry, field, data[field])

        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def delete_listening(self, listening_id: int, company_id: int) -> None:
        """Delete a listening entry."""
        entry = await self.get_listening(listening_id, company_id)
        await self.db.delete(entry)
        await self.db.commit()

    async def check_listening(
        self, listening_id: int, company_id: int
    ) -> Dict[str, Any]:
        """Check a listening entry and collect results.

        Performs a platform-specific search for the target hashtag/mention/keyword.

        Returns:
            Check results with found items.
        """
        from app.social.models import SocialListening

        entry = await self.get_listening(listening_id, company_id)
        if not entry.is_active:
            return {"success": False, "message": "Listening entry is inactive"}

        results = []
        result_count = 0

        try:
            if entry.platform in ("instagram", "facebook"):
                # Use connected account's token to search
                result = await self.db.execute(
                    select(SocialAccount).where(
                        and_(
                            SocialAccount.company_id == company_id,
                            SocialAccount.platform == entry.platform,
                        )
                    )
                )
                account = result.scalar_one_or_none()
                if account:
                    access_token = CredentialManager.decrypt_access_token(
                        account.access_token
                    )
                    if entry.listen_type == "hashtag":
                        hashtag = entry.target.lstrip("#")
                        client = InstagramClient(
                            access_token=access_token,
                            instagram_account_id=account.account_id,
                        )
                        # Search hashtag via Graph API
                        search_result = await client.get(
                            "/ig_hashtag_search",
                            params={
                                "q": hashtag,
                                "user_id": account.account_id,
                                "access_token": access_token,
                            },
                        )
                        hashtag_ids = search_result.get("data", [])
                        if hashtag_ids:
                            hashtag_id = hashtag_ids[0].get("id")
                            media_result = await client.get(
                                f"/{hashtag_id}/recent_media",
                                params={
                                    "fields": "id,caption,media_type,permalink,timestamp",
                                    "access_token": access_token,
                                },
                            )
                            results = media_result.get("data", [])
                        await client.close()

            elif entry.platform == "tiktok":
                # TikTok Research API for hashtag search
                result = await self.db.execute(
                    select(SocialAccount).where(
                        and_(
                            SocialAccount.company_id == company_id,
                            SocialAccount.platform == entry.platform,
                        )
                    )
                )
                account = result.scalar_one_or_none()
                if account:
                    access_token = CredentialManager.decrypt_access_token(
                        account.access_token
                    )
                    hashtag = entry.target.lstrip("#")
                    client = TikTokClient(
                        access_token=access_token, open_id=account.account_id
                    )
                    # TikTok hashtag search via research API
                    await client.close()

            result_count = len(results)
            entry.last_result_count = result_count
            entry.last_checked_at = datetime.utcnow()
            entry.results_summary = results[:20]  # Store top 20
            await self.db.commit()

            return {
                "success": True,
                "listening_id": listening_id,
                "target": entry.target,
                "platform": entry.platform,
                "listen_type": entry.listen_type,
                "results_found": result_count,
                "results": results,
            }

        except Exception as exc:
            logger.error("Listening check failed for %d: %s", listening_id, exc)
            return {"success": False, "message": f"Check failed: {str(exc)}"}


# =============================================================================
# Hashtag Intelligence Service
# =============================================================================


class HashtagIntelligenceService:
    """Service for hashtag intelligence and recommendations.

    Tracks popular hashtags, analyzes trends, and provides suggestions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entry(
        self,
        company_id: int,
        data: Dict[str, Any],
        branch_id: Optional[int] = None,
    ) -> HashtagIntelligence:
        """Create a new hashtag intelligence entry."""
        entry = HashtagIntelligence(
            company_id=company_id,
            branch_id=branch_id,
            platform=data["platform"],
            hashtag=data["hashtag"].lstrip("#").lower(),
            post_count=data.get("post_count", 0),
            engagement_avg=data.get("engagement_avg", 0),
            trend_direction=data.get("trend_direction", "stable"),
            related_hashtags=data.get("related_hashtags", []),
            suggested_for=data.get("suggested_for", []),
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_entry(self, entry_id: int, company_id: int) -> HashtagIntelligence:
        """Get a hashtag intelligence entry by ID."""
        result = await self.db.execute(
            select(HashtagIntelligence).where(
                and_(
                    HashtagIntelligence.id == entry_id,
                    HashtagIntelligence.company_id == company_id,
                )
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise NotFoundError(f"Hashtag intelligence entry {entry_id} not found")
        return entry

    async def list_entries(
        self,
        company_id: int,
        platform: Optional[str] = None,
        trend_direction: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List hashtag intelligence entries."""
        query = select(HashtagIntelligence).where(
            HashtagIntelligence.company_id == company_id
        )

        if platform:
            query = query.where(HashtagIntelligence.platform == platform)
        if trend_direction:
            query = query.where(HashtagIntelligence.trend_direction == trend_direction)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(HashtagIntelligence.engagement_avg))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": list(items),
        }

    async def update_entry(
        self, entry_id: int, company_id: int, data: Dict[str, Any]
    ) -> HashtagIntelligence:
        """Update a hashtag intelligence entry."""
        entry = await self.get_entry(entry_id, company_id)

        allowed_fields = {
            "post_count",
            "engagement_avg",
            "trend_direction",
            "related_hashtags",
            "suggested_for",
        }
        for field, value in data.items():
            if field in allowed_fields:
                setattr(entry, field, value)

        entry.last_analyzed_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: int, company_id: int) -> None:
        """Delete a hashtag intelligence entry."""
        entry = await self.get_entry(entry_id, company_id)
        await self.db.delete(entry)
        await self.db.commit()

    async def analyze_hashtags(
        self, company_id: int, platform: str
    ) -> Dict[str, Any]:
        """Analyze hashtags for a platform and update intelligence.

        Uses connected account's API to fetch trending/popular hashtags.

        Returns:
            Analysis results.
        """
        try:
            result = await self.db.execute(
                select(SocialAccount).where(
                    and_(
                        SocialAccount.company_id == company_id,
                        SocialAccount.platform == platform,
                    )
                )
            )
            account = result.scalar_one_or_none()

            analyzed = 0
            if account and platform == "instagram":
                access_token = CredentialManager.decrypt_access_token(
                    account.access_token
                )
                client = InstagramClient(
                    access_token=access_token,
                    instagram_account_id=account.account_id,
                )

                # Get recent media and extract hashtags
                media_list = await client.get_media_list(limit=25)
                hashtag_stats: Dict[str, Dict[str, Any]] = {}

                for media in media_list:
                    caption = media.get("caption", "") or ""
                    hashtags = [
                        word.lower().strip("#.,!?:;").rstrip("#.,!?:;")
                        for word in caption.split()
                        if word.startswith("#")
                    ]
                    for tag in hashtags:
                        tag = tag.lstrip("#")
                        if not tag:
                            continue
                        if tag not in hashtag_stats:
                            hashtag_stats[tag] = {"count": 0, "media": []}
                        hashtag_stats[tag]["count"] += 1
                        hashtag_stats[tag]["media"].append(media.get("id"))

                await client.close()

                # Update intelligence entries
                for tag, stats in hashtag_stats.items():
                    existing = await self.db.execute(
                        select(HashtagIntelligence).where(
                            and_(
                                HashtagIntelligence.company_id == company_id,
                                HashtagIntelligence.platform == platform,
                                HashtagIntelligence.hashtag == tag,
                            )
                        )
                    )
                    entry = existing.scalar_one_or_none()

                    if entry:
                        entry.post_count = stats["count"]
                        entry.last_analyzed_at = datetime.utcnow()
                        # Calculate trend
                        if stats["count"] > entry.post_count:
                            entry.trend_direction = "up"
                        elif stats["count"] < entry.post_count:
                            entry.trend_direction = "down"
                        else:
                            entry.trend_direction = "stable"
                    else:
                        new_entry = HashtagIntelligence(
                            company_id=company_id,
                            platform=platform,
                            hashtag=tag,
                            post_count=stats["count"],
                            engagement_avg=0,
                            trend_direction="stable",
                            related_hashtags=[
                                t for t in hashtag_stats.keys() if t != tag
                            ][:10],
                        )
                        self.db.add(new_entry)
                        analyzed += 1

                await self.db.commit()

            return {
                "success": True,
                "platform": platform,
                "hashtags_analyzed": analyzed + len(hashtag_stats),
                "message": "Hashtag analysis completed",
            }

        except Exception as exc:
            logger.error("Hashtag analysis failed: %s", exc)
            return {"success": False, "message": f"Analysis failed: {str(exc)}"}

    async def suggest_hashtags(
        self, company_id: int, topic: str, platform: str, count: int = 10
    ) -> Dict[str, Any]:
        """Suggest hashtags based on a topic.

        Returns existing intelligence entries that match the topic,
        sorted by engagement.

        Args:
            company_id: Tenant company ID.
            topic: Topic or content description.
            platform: Target platform.
            count: Number of suggestions to return.

        Returns:
            Suggested hashtags with metadata.
        """
        topic_words = topic.lower().split()

        result = await self.db.execute(
            select(HashtagIntelligence)
            .where(
                and_(
                    HashtagIntelligence.company_id == company_id,
                    HashtagIntelligence.platform == platform,
                )
            )
            .order_by(desc(HashtagIntelligence.engagement_avg))
            .limit(count * 3)
        )
        entries = list(result.scalars().all())

        # Score entries by relevance to topic
        scored = []
        for entry in entries:
            score = 0
            hashtag_lower = entry.hashtag.lower()
            for word in topic_words:
                if word in hashtag_lower:
                    score += 10
                if word in " ".join(entry.related_hashtags).lower():
                    score += 3
            scored.append((score, entry))

        # Sort by score then engagement
        scored.sort(key=lambda x: (x[0], x[1].engagement_avg or 0), reverse=True)

        suggestions = [
            {
                "hashtag": f"#{entry.hashtag}",
                "post_count": entry.post_count,
                "engagement_avg": float(entry.engagement_avg) if entry.engagement_avg else 0,
                "trend_direction": entry.trend_direction,
                "related_hashtags": entry.related_hashtags[:5],
                "relevance_score": score,
            }
            for score, entry in scored[:count]
        ]

        return {
            "topic": topic,
            "platform": platform,
            "suggestions": suggestions,
        }


# =============================================================================
# TikTok Video Upload (Chunked)
# =============================================================================


class TikTokVideoUploader:
    """Helper class for chunked TikTok video uploads.

    Handles the multi-step upload process: init -> upload chunks -> publish.
    """

    def __init__(self, client: TikTokClient):
        self.client = client
        self.chunk_size = 10 * 1024 * 1024  # 10MB chunks

    async def upload_video(
        self,
        video_data: bytes,
        title: str,
        privacy_level: str = "public",
        disable_duet: bool = False,
        disable_comment: bool = False,
    ) -> Dict[str, Any]:
        """Upload a video to TikTok using chunked upload.

        Args:
            video_data: Raw video bytes.
            title: Video title/caption.
            privacy_level: Privacy setting (public, mutual_follow_friends, private).
            disable_duet: Whether to disable duets.
            disable_comment: Whether to disable comments.

        Returns:
            Upload result with publish_id and status.
        """
        total_size = len(video_data)
        total_chunks = (total_size + self.chunk_size - 1) // self.chunk_size

        # Step 1: Initialize upload
        source_info = {
            "source": "PULL_FROM_URL" if total_size > 100 * 1024 * 1024 else "FILE_UPLOAD",
            "video_size": total_size,
            "chunk_size": self.chunk_size,
            "total_chunk_count": total_chunks,
        }
        post_info = {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": str(disable_duet).lower(),
            "disable_comment": str(disable_comment).lower(),
        }

        init_result = await self.client.init_video_upload(
            source_info=source_info,
            post_info=post_info,
        )

        publish_id = init_result.get("data", {}).get("publish_id")
        upload_url = init_result.get("data", {}).get("upload_url")

        if not publish_id:
            return {"success": False, "error": "Failed to initialize upload"}

        # Step 2: Upload chunks (if FILE_UPLOAD)
        if source_info["source"] == "FILE_UPLOAD" and upload_url:
            for i in range(total_chunks):
                start = i * self.chunk_size
                end = min(start + self.chunk_size, total_size)
                chunk = video_data[start:end]

                await self._upload_chunk(upload_url, chunk, i, total_chunks)

        return {
            "success": True,
            "publish_id": publish_id,
            "status": "uploaded",
            "chunks": total_chunks,
        }

    async def _upload_chunk(
        self, upload_url: str, chunk: bytes, chunk_index: int, total_chunks: int
    ) -> None:
        """Upload a single chunk.

        Args:
            upload_url: Chunk upload URL.
            chunk: Chunk bytes.
            chunk_index: Current chunk index (0-based).
            total_chunks: Total number of chunks.
        """
        headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes {chunk_index * self.chunk_size}-{chunk_index * self.chunk_size + len(chunk) - 1}/{total_chunks * self.chunk_size}",
            "Content-Length": str(len(chunk)),
        }
        client = await self.client._get_client()
        response = await client.put(upload_url, content=chunk, headers=headers)
        response.raise_for_status()
        logger.debug("Uploaded chunk %d/%d", chunk_index + 1, total_chunks)
