"""Safe Outreach Governance Service

Daily quotas, per-platform limits, warm-up strategy,
suspicious outreach detection, and spam-risk scoring.

Conservative defaults for pilot.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class OutreachGovernanceService:
    """Governance layer for safe outreach.

    Enforces daily quotas, platform limits, warm-up strategy,
    and spam-risk detection.
    """

    # Default daily quotas per tenant (very conservative for pilot)
    DEFAULT_DAILY_QUOTAS = {
        "instagram": 20,      # Max 20 Instagram DMs/day per tenant
        "facebook": 30,       # Max 30 FB Messenger/day
        "tiktok": 10,         # Max 10 TikTok DMs/day
        "whatsapp": 50,       # Max 50 WhatsApp messages/day
        "telegram": 40,       # Max 40 Telegram messages/day
    }

    # Per-message-type daily limits
    TYPE_LIMITS = {
        "welcome_new_follower": 0.3,    # 30% of daily quota
        "campaign_suggestion": 0.2,     # 20% of daily quota
        "reengagement_for_low": 0.2,    # 20% of daily quota
        "win_back_unfollow": 0.1,       # 10% of daily quota
        "dm_follow_up": 0.1,            # 10% of daily quota
        "local_branch_campaign": 0.05,  # 5% of daily quota
        "engagement_reward": 0.05,      # 5% of daily quota
    }

    # Cooldown periods between messages (seconds)
    COOLDOWN_SECONDS = {
        "instagram": 120,    # 2 min between Instagram DMs
        "facebook": 60,      # 1 min between FB messages
        "tiktok": 300,       # 5 min between TikTok DMs
        "whatsapp": 30,      # 30 sec between WhatsApp messages
        "telegram": 30,      # 30 sec between Telegram messages
    }

    # Warm-up schedule: first week gradually increase
    WARMUP_SCHEDULE = {
        1: 0.2,   # Day 1: 20% of quota
        2: 0.3,   # Day 2: 30%
        3: 0.4,   # Day 3: 40%
        4: 0.5,   # Day 4: 50%
        5: 0.6,   # Day 5: 60%
        6: 0.75,  # Day 6: 75%
        7: 0.85,  # Day 7: 85%
        8: 1.0,   # Day 8+: 100%
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def get_effective_quota(
        self,
        platform: str,
        tenant_days_active: int,
        custom_quota: Optional[int] = None,
    ) -> int:
        """Get effective daily quota considering warm-up.

        Args:
            platform: Target platform.
            tenant_days_active: Days since tenant first activated outreach.
            custom_quota: Optional custom quota override.

        Returns:
            Effective daily quota (messages per day).
        """
        base = custom_quota or self.DEFAULT_DAILY_QUOTAS.get(platform, 20)

        # Apply warm-up multiplier
        if tenant_days_active <= 0:
            warmup_multiplier = 0.1  # Very first day
        elif tenant_days_active <= 7:
            warmup_multiplier = self.WARMUP_SCHEDULE.get(tenant_days_active, 1.0)
        else:
            warmup_multiplier = 1.0

        effective = int(base * warmup_multiplier)
        return max(1, effective)  # At least 1

    def check_quota(
        self,
        company_id: int,
        platform: str,
        sent_today: int,
        tenant_days_active: int,
        custom_quota: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Check if tenant has remaining quota for the day.

        Args:
            company_id: Tenant company ID.
            platform: Target platform.
            sent_today: Messages sent today so far.
            tenant_days_active: Days since tenant first activated outreach.
            custom_quota: Optional custom quota.

        Returns:
            Quota status with remaining and limit info.
        """
        effective_quota = self.get_effective_quota(platform, tenant_days_active, custom_quota)
        remaining = max(0, effective_quota - sent_today)
        usage_pct = (sent_today / effective_quota * 100) if effective_quota > 0 else 100

        if sent_today >= effective_quota:
            allowed = False
            status = "quota_exceeded"
        elif sent_today >= effective_quota * 0.8:
            allowed = True
            status = "quota_warning"
        else:
            allowed = True
            status = "ok"

        return {
            "company_id": company_id,
            "platform": platform,
            "daily_quota": effective_quota,
            "sent_today": sent_today,
            "remaining": remaining,
            "usage_percentage": round(usage_pct, 1),
            "allowed": allowed,
            "status": status,
            "warmup_phase": tenant_days_active <= 7,
            "warmup_multiplier": self.WARMUP_SCHEDULE.get(min(tenant_days_active, 8), 1.0),
        }

    def check_type_limit(
        self,
        message_type: str,
        platform: str,
        sent_today_type: int,
        tenant_days_active: int,
    ) -> Dict[str, Any]:
        """Check per-message-type daily limit.

        Returns:
            Type limit status.
        """
        effective_quota = self.get_effective_quota(platform, tenant_days_active)
        type_ratio = self.TYPE_LIMITS.get(message_type, 0.1)
        type_limit = max(1, int(effective_quota * type_ratio))

        remaining = max(0, type_limit - sent_today_type)
        allowed = sent_today_type < type_limit

        return {
            "message_type": message_type,
            "type_limit": type_limit,
            "sent_today": sent_today_type,
            "remaining": remaining,
            "allowed": allowed,
            "usage_percentage": round(sent_today_type / type_limit * 100, 1) if type_limit > 0 else 0,
        }

    def check_cooldown(
        self,
        platform: str,
        last_sent_at: Optional[datetime],
    ) -> Dict[str, Any]:
        """Check if cooldown period has elapsed.

        Returns:
            Cooldown status.
        """
        required_seconds = self.COOLDOWN_SECONDS.get(platform, 60)

        if not last_sent_at:
            return {
                "platform": platform,
                "cooldown_required_seconds": required_seconds,
                "elapsed_seconds": None,
                "cooldown_passed": True,
                "remaining_seconds": 0,
            }

        elapsed = (datetime.now(timezone.utc) - last_sent_at).total_seconds()
        passed = elapsed >= required_seconds
        remaining = max(0, required_seconds - elapsed)

        return {
            "platform": platform,
            "cooldown_required_seconds": required_seconds,
            "elapsed_seconds": round(elapsed, 0),
            "cooldown_passed": passed,
            "remaining_seconds": round(remaining, 0),
        }

    def calculate_spam_risk(
        self,
        message_body: str,
        messages_sent_today: int,
        platform: str,
        unique_recipients_today: int,
        total_recipients_today: int,
    ) -> Dict[str, Any]:
        """Calculate spam-risk score for an outreach attempt.

        Returns:
            Spam-risk analysis with score and recommendations.
        """
        risk = 0.0
        flags = []

        # 1. Message content risk
        msg_lower = message_body.lower()

        # Spam keywords
        spam_words = ["free", "win", "click", "now", "urgent", "limited", "act fast", "exclusive offer"]
        spam_count = sum(1 for w in spam_words if w in msg_lower)
        if spam_count > 0:
            risk += spam_count * 0.1
            flags.append(f"spam_keywords:{spam_count}")

        # Exclamation marks
        excl_count = message_body.count("!")
        if excl_count > 2:
            risk += (excl_count - 2) * 0.05
            flags.append(f"excessive_exclamation:{excl_count}")

        # All caps ratio
        letters = [c for c in message_body if c.isalpha()]
        if letters:
            caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if caps_ratio > 0.3:
                risk += (caps_ratio - 0.3) * 0.3
                flags.append(f"high_caps_ratio:{caps_ratio:.0%}")

        # Message length
        if len(message_body) > 500:
            risk += 0.05
            flags.append("long_message")

        # 2. Volume risk
        if messages_sent_today > 30:
            risk += 0.2
            flags.append(f"high_volume_today:{messages_sent_today}")
        elif messages_sent_today > 15:
            risk += 0.1
            flags.append(f"moderate_volume:{messages_sent_today}")

        # 3. Recipient diversity
        if total_recipients_today > 0:
            diversity = unique_recipients_today / total_recipients_today
            if diversity < 0.8:
                risk += (1 - diversity) * 0.15
                flags.append(f"low_recipient_diversity:{diversity:.0%}")

        # 4. Platform-specific risk
        platform_multipliers = {
            "instagram": 1.1,
            "facebook": 1.0,
            "tiktok": 1.3,
            "whatsapp": 0.9,
            "telegram": 0.9,
        }
        risk *= platform_multipliers.get(platform, 1.0)

        final_risk = min(1.0, risk)

        # Classification
        if final_risk >= 0.7:
            tier = "high"
            action = "block_and_review"
        elif final_risk >= 0.4:
            tier = "medium"
            action = "require_approval"
        elif final_risk >= 0.2:
            tier = "low"
            action = "monitor"
        else:
            tier = "minimal"
            action = "allow"

        return {
            "spam_risk_score": round(final_risk, 3),
            "risk_tier": tier,
            "recommended_action": action,
            "flags": flags,
            "volume_today": messages_sent_today,
            "recipient_diversity": (
                round(unique_recipients_today / total_recipients_today, 2)
                if total_recipients_today > 0 else 1.0
            ),
            "message_analysis": {
                "length": len(message_body),
                "exclamation_count": excl_count,
                "spam_keyword_count": spam_count,
            },
            "confidence": 0.75,
        }

    def get_safe_cadence_recommendation(
        self,
        platform: str,
        follower_engagement_frequency: float,
    ) -> Dict[str, Any]:
        """Get safe messaging cadence recommendation.

        Returns:
            Cadence recommendation.
        """
        # Base cadence by platform
        base_cadences = {
            "instagram": {"min_hours": 24, "max_per_week": 3},
            "facebook": {"min_hours": 18, "max_per_week": 4},
            "tiktok": {"min_hours": 48, "max_per_week": 2},
            "whatsapp": {"min_hours": 12, "max_per_week": 5},
            "telegram": {"min_hours": 12, "max_per_week": 5},
        }
        base = base_cadences.get(platform, {"min_hours": 24, "max_per_week": 3})

        # Adjust for engagement frequency
        if follower_engagement_frequency >= 3:
            multiplier = 0.7  # High engager = can message more often
        elif follower_engagement_frequency >= 1:
            multiplier = 1.0  # Normal
        else:
            multiplier = 1.5  # Low engager = less frequent

        min_hours = max(6, int(base["min_hours"] * multiplier))
        max_per_week = max(1, int(base["max_per_week"] / multiplier))

        return {
            "platform": platform,
            "recommended_min_hours_between_messages": min_hours,
            "recommended_max_per_week": max_per_week,
            "engagement_frequency": follower_engagement_frequency,
            "multiplier_applied": multiplier,
            "note": "Conservative cadence for pilot. Adjust based on response rates.",
        }

    def check_outreach_eligibility(
        self,
        company_id: int,
        platform: str,
        message_type: str,
        message_body: str,
        sent_today: int,
        sent_today_type: int,
        tenant_days_active: int,
        last_sent_at: Optional[datetime],
        unique_recipients_today: int,
        total_recipients_today: int,
    ) -> Dict[str, Any]:
        """Comprehensive outreach eligibility check.

        Runs all governance checks in order and returns combined result.
        """
        checks = []
        overall_allowed = True
        overall_reasons = []

        # 1. Quota check
        quota_check = self.check_quota(company_id, platform, sent_today, tenant_days_active)
        checks.append({"check": "quota", **quota_check})
        if not quota_check["allowed"]:
            overall_allowed = False
            overall_reasons.append(f"Daily quota exceeded: {quota_check['sent_today']}/{quota_check['daily_quota']}")

        # 2. Type limit check
        type_check = self.check_type_limit(message_type, platform, sent_today_type, tenant_days_active)
        checks.append({"check": "type_limit", **type_check})
        if not type_check["allowed"]:
            overall_allowed = False
            overall_reasons.append(f"Type limit exceeded: {type_check['sent_today']}/{type_check['type_limit']}")

        # 3. Cooldown check
        cooldown_check = self.check_cooldown(platform, last_sent_at)
        checks.append({"check": "cooldown", **cooldown_check})
        if not cooldown_check["cooldown_passed"]:
            overall_allowed = False
            overall_reasons.append(f"Cooldown active: {cooldown_check['remaining_seconds']}s remaining")

        # 4. Spam risk check
        spam_check = self.calculate_spam_risk(
            message_body, sent_today, platform,
            unique_recipients_today, total_recipients_today,
        )
        checks.append({"check": "spam_risk", **spam_check})
        if spam_check["spam_risk_score"] >= 0.7:
            overall_allowed = False
            overall_reasons.append(f"High spam risk: {spam_check['spam_risk_score']:.2f}")

        return {
            "company_id": company_id,
            "platform": platform,
            "message_type": message_type,
            "allowed": overall_allowed,
            "reasons": overall_reasons if overall_reasons else ["All checks passed"],
            "checks": checks,
            "warmup_phase": tenant_days_active <= 7,
            "next_available_at": (
                (last_sent_at + timedelta(seconds=self.COOLDOWN_SECONDS.get(platform, 60))).isoformat()
                if last_sent_at and not cooldown_check["cooldown_passed"]
                else datetime.now(timezone.utc).isoformat()
            ),
        }
