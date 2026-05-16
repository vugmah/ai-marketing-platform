"""Audience Recovery Intelligence Service

Churn prediction, engagement decay analysis, retention scoring,
and recovery campaign suggestions.

All predictions are estimates with confidence scores.
"""

import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession


class AudienceRecoveryService:
    """Predict and prevent audience churn.

    Uses engagement patterns to identify at-risk followers
    and suggest recovery actions.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def predict_churn_risk(
        self,
        engagement_frequency: float,
        days_since_engagement: int,
        total_engagements: int,
        follower_age_days: int,
        platform: str,
    ) -> Dict[str, Any]:
        """Predict churn risk for a follower.

        Returns risk score (0-1) and risk tier.
        """
        # Base risk from inactivity
        inactivity_risk = min(1.0, days_since_engagement / 60)

        # Frequency risk (lower frequency = higher risk)
        freq_risk = max(0, 1.0 - (engagement_frequency / 5))

        # Volume risk (few engagements = higher risk)
        volume_risk = max(0, 1.0 - (total_engagements / 10))

        # Age risk (new followers churn more)
        age_risk = 0.3 if follower_age_days < 14 else 0.0

        # Platform-specific adjustments
        platform_multipliers = {
            "instagram": 1.0,
            "facebook": 0.9,
            "tiktok": 1.1,
            "whatsapp": 0.7,
            "telegram": 0.8,
        }
        multiplier = platform_multipliers.get(platform, 1.0)

        # Weighted combination
        risk = (
            inactivity_risk * 0.4 +
            freq_risk * 0.25 +
            volume_risk * 0.2 +
            age_risk * 0.15
        ) * multiplier

        risk = min(1.0, max(0.0, risk))

        # Classify tier
        if risk >= 0.7:
            tier = "high"
        elif risk >= 0.4:
            tier = "medium"
        elif risk >= 0.15:
            tier = "low"
        else:
            tier = "minimal"

        # Confidence based on data quality
        confidence = min(1.0, (total_engagements / 5) + 0.3)

        return {
            "churn_risk_score": round(risk, 3),
            "risk_tier": tier,
            "confidence": round(confidence, 3),
            "factors": {
                "inactivity_risk": round(inactivity_risk, 3),
                "frequency_risk": round(freq_risk, 3),
                "volume_risk": round(volume_risk, 3),
                "age_risk": round(age_risk, 3),
                "platform_multiplier": multiplier,
            },
            "estimated_churn_days": (
                int(30 + (1 - risk) * 60) if risk > 0.3 else None
            ),
            "note": "Churn risk is an estimate based on engagement patterns.",
        }

    def analyze_engagement_decay(
        self,
        daily_engagements: List[int],
    ) -> Dict[str, Any]:
        """Analyze engagement decay trend.

        Args:
            daily_engagements: List of daily engagement counts (last N days).

        Returns:
            Decay analysis with trend direction and severity.
        """
        if len(daily_engagements) < 7:
            return {
                "trend": "insufficient_data",
                "decay_rate": None,
                "confidence": 0.0,
                "note": "Need at least 7 days of data",
            }

        # Split into first half and second half
        mid = len(daily_engagements) // 2
        first_half = daily_engagements[:mid]
        second_half = daily_engagements[mid:]

        first_avg = statistics.mean(first_half) if first_half else 0
        second_avg = statistics.mean(second_half) if second_half else 0

        if first_avg == 0:
            decay_rate = 0.0
        else:
            decay_rate = (first_avg - second_avg) / first_avg

        # Trend classification
        if decay_rate > 0.3:
            trend = "sharp_decline"
        elif decay_rate > 0.1:
            trend = "moderate_decline"
        elif decay_rate > -0.1:
            trend = "stable"
        elif decay_rate > -0.3:
            trend = "moderate_growth"
        else:
            trend = "strong_growth"

        # Confidence based on data consistency
        if len(daily_engagements) >= 14:
            confidence = 0.8
        elif len(daily_engagements) >= 7:
            confidence = 0.6
        else:
            confidence = 0.3

        # Prediction
        if decay_rate > 0.1:
            projected_daily = max(0, second_avg * (1 - decay_rate))
        else:
            projected_daily = second_avg

        return {
            "trend": trend,
            "decay_rate": round(decay_rate, 3),
            "first_half_avg": round(first_avg, 1),
            "second_half_avg": round(second_avg, 1),
            "projected_daily_engagement": round(projected_daily, 1),
            "confidence": confidence,
            "days_analyzed": len(daily_engagements),
            "alert": decay_rate > 0.3,
        }

    def calculate_retention_score(
        self,
        starting_followers: int,
        current_followers: int,
        new_followers_estimated: int,
        lost_followers_estimated: int,
        high_value_retained: int,
        high_value_total: int,
        period_days: int,
    ) -> Dict[str, Any]:
        """Calculate audience retention score.

        Returns:
            Retention metrics with score (0-100).
        """
        if starting_followers == 0:
            return {
                "retention_score": 0,
                "retention_rate": 0.0,
                "churn_rate": 0.0,
                "confidence": 0.0,
            }

        retention_rate = (
            (current_followers - new_followers_estimated) / starting_followers * 100
        ) if starting_followers > 0 else 0
        retention_rate = max(0, min(100, retention_rate))

        churn_rate = (lost_followers_estimated / starting_followers * 100) if starting_followers > 0 else 0
        growth_rate = ((current_followers - starting_followers) / starting_followers * 100) if starting_followers > 0 else 0

        # High value retention
        hv_retention = (
            (high_value_retained / high_value_total * 100) if high_value_total > 0 else 100
        )

        # Composite retention score (0-100)
        score = (
            retention_rate * 0.4 +
            (100 - churn_rate) * 0.3 +
            max(0, growth_rate) * 0.15 +
            hv_retention * 0.15
        )
        score = max(0, min(100, score))

        # Confidence
        confidence = 0.7 if period_days >= 7 else 0.5

        return {
            "retention_score": round(score, 1),
            "retention_rate": round(retention_rate, 2),
            "churn_rate": round(churn_rate, 2),
            "growth_rate": round(growth_rate, 2),
            "high_value_retention": round(hv_retention, 2),
            "starting_followers": starting_followers,
            "current_followers": current_followers,
            "new_followers_estimated": new_followers_estimated,
            "lost_followers_estimated": lost_followers_estimated,
            "period_days": period_days,
            "confidence": confidence,
            "grade": self._score_to_grade(score),
        }

    def predict_reengagement_timing(
        self,
        last_engagement_at: Optional[datetime],
        engagement_frequency: float,
        churn_risk_score: float,
    ) -> Dict[str, Any]:
        """Predict optimal re-engagement timing.

        Returns:
            Optimal timing with confidence.
        """
        if not last_engagement_at:
            return {
                "optimal_timing": "asap",
                "recommended_date": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.3,
                "reason": "No engagement history",
            }

        days_since = (datetime.now(timezone.utc) - last_engagement_at).days

        # Calculate optimal delay
        base_delay = max(1, int(7 / max(engagement_frequency, 0.5)))

        # Adjust for churn risk
        if churn_risk_score > 0.7:
            base_delay = max(1, base_delay - 3)  # Urgent
        elif churn_risk_score > 0.4:
            base_delay = max(2, base_delay - 1)  # Soon
        else:
            base_delay += 2  # Can wait

        recommended_date = datetime.now(timezone.utc) + timedelta(days=base_delay)

        # Don't recommend weekends for business messages
        if recommended_date.weekday() >= 5:
            recommended_date += timedelta(days=7 - recommended_date.weekday())

        confidence = 0.5 + (1 - churn_risk_score) * 0.3

        return {
            "optimal_timing": f"in_{base_delay}_days",
            "recommended_date": recommended_date.isoformat(),
            "days_since_last_engagement": days_since,
            "confidence": round(confidence, 3),
            "reason": f"Based on {days_since} days since last engagement, risk={churn_risk_score:.2f}",
        }

    def suggest_recovery_campaign(
        self,
        churn_risk_tier: str,
        follower_value_tier: str,
        platform: str,
        branch_context: str = "",
    ) -> Dict[str, Any]:
        """Suggest a recovery campaign based on follower profile.

        Returns:
            Campaign suggestion with expected impact.
        """
        # Campaign type selection
        if churn_risk_tier == "high":
            if follower_value_tier == "high_value":
                campaign_type = "personalized_outreach"
                priority = "urgent"
                expected_response = 25.0
            else:
                campaign_type = "win_back_campaign"
                priority = "high"
                expected_response = 15.0
        elif churn_risk_tier == "medium":
            campaign_type = "reengagement_campaign"
            priority = "medium"
            expected_response = 20.0
        elif follower_value_tier == "high_value":
            campaign_type = "loyalty_reward"
            priority = "medium"
            expected_response = 35.0
        else:
            campaign_type = "general_campaign"
            priority = "low"
            expected_response = 10.0

        # Platform-specific adjustments
        platform_response_multipliers = {
            "instagram": 1.2,
            "facebook": 1.0,
            "tiktok": 0.8,
            "whatsapp": 1.5,
            "telegram": 1.3,
        }
        multiplier = platform_response_multipliers.get(platform, 1.0)
        expected_response *= multiplier

        return {
            "campaign_type": campaign_type,
            "priority": priority,
            "expected_response_rate": round(expected_response, 1),
            "platform": platform,
            "target_segment": f"{churn_risk_tier}_risk_{follower_value_tier}",
            "suggested_actions": self._get_campaign_actions(campaign_type),
            "confidence": 0.6 if churn_risk_tier != "high" else 0.5,
        }

    def _get_campaign_actions(self, campaign_type: str) -> List[str]:
        """Get suggested actions for a campaign type."""
        actions = {
            "personalized_outreach": [
                "Generate personalized DM via AI",
                "Include exclusive offer",
                "Request approval before send",
            ],
            "win_back_campaign": [
                "Create win-back message",
                "Offer welcome-back discount",
                "Schedule follow-up",
            ],
            "reengagement_campaign": [
                "Generate re-engagement message",
                "Highlight new content",
                "Request approval before send",
            ],
            "loyalty_reward": [
                "Create thank-you message",
                "Offer loyalty reward",
                "Request approval before send",
            ],
            "general_campaign": [
                "Add to general campaign list",
                "Monitor engagement",
                "Re-evaluate in 2 weeks",
            ],
        }
        return actions.get(campaign_type, ["Monitor and re-evaluate"])

    def _score_to_grade(self, score: float) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    async def get_recovery_dashboard(
        self,
        company_id: int,
        account_id: int,
    ) -> Dict[str, Any]:
        """Get full recovery dashboard data.

        In production, would query the database.
        For pilot, returns structure with sample data.
        """
        return {
            "company_id": company_id,
            "account_id": account_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "high_risk_followers": {
                "count": 0,  # Would query database
                "action": "Requires immediate attention",
            },
            "medium_risk_followers": {
                "count": 0,
                "action": "Schedule re-engagement",
            },
            "recovery_campaigns_suggested": 0,
            "recovery_campaigns_active": 0,
            "average_retention_score": 0.0,
            "engagement_trend": "stable",
            "note": "Dashboard data requires database queries in production.",
        }
