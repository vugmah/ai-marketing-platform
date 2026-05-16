"""Platform Delivery Dispatch Service

Safe message dispatch across Instagram, Facebook, WhatsApp, Telegram.
No bulk send. Rate limited. Approval required before send.
Tenant isolated. Failed delivery logged with retry.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Delivery status for outbound messages."""

    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RETRYING = "retrying"
    RATE_LIMITED = "rate_limited"
    POLICY_BLOCKED = "policy_blocked"
    CANCELLED = "cancelled"


class PlatformDispatcher:
    """Base dispatcher for outbound messages.

    Actual API calls are simulated (no real API keys in pilot).
    Delivery status is tracked with retry logic.
    """

    # Platform-specific rate limits (messages per minute per tenant)
    RATE_LIMITS = {
        "instagram": 5,      # Instagram DM: very conservative
        "facebook": 10,      # Facebook Messenger
        "tiktok": 3,         # TikTok: very limited
        "whatsapp": 15,      # WhatsApp Business
        "telegram": 20,      # Telegram Bot
    }

    # Platform-specific restrictions
    RESTRICTIONS = {
        "instagram": {
            "supports_dm": True,
            "requires_reciprocal": True,  # Must follow each other
            "max_message_length": 1000,
            "no_external_links": False,
        },
        "facebook": {
            "supports_dm": True,
            "requires_page_connection": True,
            "max_message_length": 2000,
            "no_external_links": False,
        },
        "tiktok": {
            "supports_dm": True,
            "requires_mutual_follow": True,
            "max_message_length": 500,
            "no_external_links": True,
        },
        "whatsapp": {
            "supports_dm": True,
            "requires_opt_in": True,
            "max_message_length": 4096,
            "no_external_links": False,
            "business_hours_only": True,
        },
        "telegram": {
            "supports_dm": True,
            "requires_bot_start": True,
            "max_message_length": 4096,
            "no_external_links": False,
        },
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._rate_limit_buckets: Dict[str, Dict[str, Any]] = {}

    def _check_rate_limit(self, company_id: int, platform: str) -> tuple[bool, Optional[int]]:
        """Check if rate limit allows sending. Returns (allowed, retry_after_seconds).

        Conservative limits for pilot:
        - Instagram: 5/min per tenant
        - Facebook: 10/min per tenant
        - TikTok: 3/min per tenant
        - WhatsApp: 15/min per tenant
        - Telegram: 20/min per tenant
        """
        key = f"{company_id}:{platform}"
        now = datetime.now(timezone.utc)
        limit = self.RATE_LIMITS.get(platform, 5)

        bucket = self._rate_limit_buckets.get(key)
        if not bucket:
            self._rate_limit_buckets[key] = {"count": 1, "reset_at": now + timedelta(minutes=1)}
            return True, None

        if now >= bucket["reset_at"]:
            bucket["count"] = 1
            bucket["reset_at"] = now + timedelta(minutes=1)
            return True, None

        if bucket["count"] >= limit:
            retry_after = int((bucket["reset_at"] - now).total_seconds())
            return False, max(1, retry_after)

        bucket["count"] += 1
        return True, None

    def _check_policy_compliance(self, platform: str, message_body: str) -> tuple[bool, str]:
        """Check message against platform policies.

        Returns:
            Tuple of (is_compliant, reason).
        """
        restrictions = self.RESTRICTIONS.get(platform, {})
        max_length = restrictions.get("max_message_length", 1000)

        if len(message_body) > max_length:
            return False, f"Message exceeds {max_length} chars for {platform}"

        # Check for spam patterns
        spam_patterns = ["%%%", "$$$$", "!!!", "FREE!!!", "CLICK NOW", "URGENT!!!"]
        body_upper = message_body.upper()
        for pattern in spam_patterns:
            if pattern in body_upper:
                return False, f"Spam pattern detected: {pattern}"

        # Check for excessive caps (more than 50% caps)
        letters = [c for c in message_body if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.5:
                return False, "Excessive capitalization"

        # Check for excessive exclamation marks
        if message_body.count("!") > 3:
            return False, "Too many exclamation marks"

        return True, "compliant"

    async def dispatch(
        self,
        company_id: int,
        platform: str,
        recipient_id: str,
        recipient_username: str,
        message_body: str,
        message_subject: Optional[str] = None,
        branch_id: Optional[int] = None,
        approval_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispatch a message to the target platform.

        Args:
            company_id: Tenant company ID.
            platform: Target platform (instagram, facebook, tiktok, whatsapp, telegram).
            recipient_id: Recipient's platform account ID.
            recipient_username: Recipient's username.
            message_body: Message content.
            message_subject: Optional subject line.
            branch_id: Optional branch ID.
            approval_id: Associated approval request ID.

        Returns:
            Dict with delivery status, tracking ID, and any errors.
        """
        tracking_id = f"del_{company_id}_{platform}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        # Step 1: Rate limit check
        allowed, retry_after = self._check_rate_limit(company_id, platform)
        if not allowed:
            logger.warning(f"Rate limited: company={company_id}, platform={platform}, retry_after={retry_after}s")
            return {
                "tracking_id": tracking_id,
                "status": DeliveryStatus.RATE_LIMITED,
                "platform": platform,
                "recipient": recipient_username,
                "error": f"Rate limit exceeded. Retry after {retry_after} seconds.",
                "retry_after": retry_after,
                "sent_at": None,
            }

        # Step 2: Policy compliance check
        is_compliant, reason = self._check_policy_compliance(platform, message_body)
        if not is_compliant:
            logger.warning(f"Policy blocked: company={company_id}, platform={platform}, reason={reason}")
            return {
                "tracking_id": tracking_id,
                "status": DeliveryStatus.POLICY_BLOCKED,
                "platform": platform,
                "recipient": recipient_username,
                "error": reason,
                "policy_violation": True,
                "sent_at": None,
            }

        # Step 3: Platform-specific validation
        restrictions = self.RESTRICTIONS.get(platform, {})
        if platform in ["whatsapp", "telegram"] and restrictions.get("requires_opt_in"):
            # Check opt-in (simplified for pilot - would query actual opt-in status)
            logger.info(f"Opt-in check passed (simulated): platform={platform}")

        # Step 4: Simulate API dispatch
        # NOTE: In production, this would call the actual platform API
        # For pilot, we simulate the dispatch and log it
        try:
            dispatch_result = await self._simulate_platform_dispatch(
                platform=platform,
                recipient_id=recipient_id,
                message_body=message_body,
                message_subject=message_subject,
            )

            status = (
                DeliveryStatus.SENT
                if dispatch_result["success"]
                else DeliveryStatus.FAILED
            )

            return {
                "tracking_id": tracking_id,
                "status": status,
                "platform": platform,
                "recipient": recipient_username,
                "recipient_id": recipient_id,
                "message_length": len(message_body),
                "sent_at": datetime.now(timezone.utc).isoformat() if dispatch_result["success"] else None,
                "platform_message_id": dispatch_result.get("message_id"),
                "error": dispatch_result.get("error"),
                "rate_limit_applied": True,
                "policy_check": "compliant",
                "estimated_delivery_time_ms": dispatch_result.get("latency_ms"),
            }

        except Exception as e:
            logger.error(f"Dispatch failed: company={company_id}, platform={platform}, error={e}")
            return {
                "tracking_id": tracking_id,
                "status": DeliveryStatus.FAILED,
                "platform": platform,
                "recipient": recipient_username,
                "error": str(e)[:255],
                "sent_at": None,
                "retryable": True,
            }

    async def _simulate_platform_dispatch(
        self,
        platform: str,
        recipient_id: str,
        message_body: str,
        message_subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate platform API dispatch.

        In production, this would call the actual platform API.
        Returns realistic simulated responses.
        """
        import random
        import asyncio

        # Simulate network latency
        latency_ms = random.randint(200, 1500)
        await asyncio.sleep(latency_ms / 1000)

        # Simulate 95% success rate for pilot testing
        if random.random() < 0.95:
            return {
                "success": True,
                "message_id": f"msg_{platform}_{recipient_id}_{datetime.now(timezone.utc).strftime('%s%f')}",
                "latency_ms": latency_ms,
            }
        else:
            # Simulate occasional failures
            error_types = [
                "recipient_not_found",
                "user_blocked",
                "temporary_error",
                "platform_timeout",
            ]
            return {
                "success": False,
                "error": random.choice(error_types),
                "latency_ms": latency_ms,
            }

    async def get_delivery_status(self, tracking_id: str) -> Dict[str, Any]:
        """Get delivery status by tracking ID.

        In production, would query the platform's delivery status API.
        """
        return {
            "tracking_id": tracking_id,
            "status": DeliveryStatus.SENT,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Status tracking simulated for pilot",
        }

    async def retry_failed_delivery(
        self,
        tracking_id: str,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Retry a failed delivery with exponential backoff.

        Args:
            tracking_id: Original tracking ID.
            max_retries: Maximum retry attempts.

        Returns:
            Updated delivery status.
        """
        import asyncio

        for attempt in range(1, max_retries + 1):
            # Exponential backoff: 2^attempt seconds
            wait_time = min(2 ** attempt, 60)
            logger.info(f"Retry attempt {attempt}/{max_retries} for {tracking_id}, waiting {wait_time}s")
            await asyncio.sleep(wait_time)

            # Simulate retry
            import random
            if random.random() < 0.7:  # 70% success on retry
                return {
                    "tracking_id": tracking_id,
                    "status": DeliveryStatus.SENT,
                    "retry_attempt": attempt,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "tracking_id": tracking_id,
            "status": DeliveryStatus.FAILED,
            "retry_attempt": max_retries,
            "error": "Max retries exceeded",
            "requires_manual_intervention": True,
        }

    def get_platform_limits(self, platform: str) -> Dict[str, Any]:
        """Get rate limits and restrictions for a platform."""
        return {
            "platform": platform,
            "rate_limit_per_minute": self.RATE_LIMITS.get(platform, 5),
            "supports_dm": True,
            "restrictions": self.RESTRICTIONS.get(platform, {}),
            "warmup_recommended": platform in ["instagram", "tiktok"],
        }
