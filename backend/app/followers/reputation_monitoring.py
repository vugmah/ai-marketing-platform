"""Platform Reputation Monitoring + Outreach Fatigue + Operator Coaching

Three integrated services:
1. PlatformReputationMonitor: Track platform risk signals
2. OutreachFatigueDetector: Detect and prevent messaging fatigue  
3. OperatorCoaching: Guide operators toward safe outreach

All estimates use confidence scores. No scraping.
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 1. Platform Reputation Monitor
# =============================================================================

class PlatformReputationMonitor:
    """Monitor platform health and reputation risk signals.

    Tracks delivery failures, spam warnings, rate limits, blocks,
    reports, and shadow-ban indicators (heuristic).
    """

    # Risk thresholds per platform
    RISK_THRESHOLDS = {
        "delivery_failure_rate": 0.15,    # >15% delivery failure = warning
        "spam_warning_rate": 0.05,        # >5% spam warnings = critical
        "block_rate": 0.02,               # >2% blocks = critical
        "report_rate": 0.01,              # >1% reports = critical
        "engagement_drop": 0.30,          # >30% engagement drop = warning
        "rate_limit_hit_rate": 0.20,      # >20% rate limited = warning
    }

    # Platform base reputation scores (0-100)
    BASE_REPUTATION = {
        "instagram": 85,
        "facebook": 90,
        "tiktok": 75,
        "whatsapp": 95,
        "telegram": 92,
    }

    def calculate_reputation_score(
        self,
        platform: str,
        total_sent: int,
        delivery_failed: int,
        spam_warnings: int,
        rate_limited_count: int,
        blocked_count: int,
        reported_count: int,
        engagement_before: float,
        engagement_after: float,
        days_window: int = 7,
    ) -> Dict[str, Any]:
        """Calculate platform reputation score.

        Returns:
            Dict with score, risk level, and alerts.
        """
        if total_sent == 0:
            return {
                "platform": platform,
                "reputation_score": self.BASE_REPUTATION.get(platform, 80),
                "risk_level": "unknown",
                "alerts": [],
                "confidence": 0.0,
                "note": "No messages sent in this period.",
            }

        base = self.BASE_REPUTATION.get(platform, 80)
        penalties = []
        alerts = []

        # Delivery failure penalty
        failure_rate = delivery_failed / total_sent
        if failure_rate > self.RISK_THRESHOLDS["delivery_failure_rate"]:
            penalty = min(30, failure_rate * 100)
            penalties.append(penalty)
            alerts.append(f"HIGH delivery failure: {(failure_rate*100):.1f}%")
        elif failure_rate > 0.05:
            penalties.append(failure_rate * 50)
            alerts.append(f"Elevated delivery failure: {(failure_rate*100):.1f}%")

        # Spam warning penalty
        spam_rate = spam_warnings / total_sent
        if spam_rate > self.RISK_THRESHOLDS["spam_warning_rate"]:
            penalty = min(40, spam_rate * 200)
            penalties.append(penalty)
            alerts.append(f"CRITICAL spam warnings: {(spam_rate*100):.1f}%")

        # Block penalty
        block_rate = blocked_count / total_sent
        if block_rate > self.RISK_THRESHOLDS["block_rate"]:
            penalty = min(50, block_rate * 500)
            penalties.append(penalty)
            alerts.append(f"CRITICAL block rate: {(block_rate*100):.1f}%")

        # Report penalty
        report_rate = reported_count / total_sent
        if report_rate > self.RISK_THRESHOLDS["report_rate"]:
            penalty = min(50, report_rate * 1000)
            penalties.append(penalty)
            alerts.append(f"CRITICAL report rate: {(report_rate*100):.1f}%")

        # Rate limit penalty
        rate_limit_rate = rate_limited_count / total_sent
        if rate_limit_rate > self.RISK_THRESHOLDS["rate_limit_hit_rate"]:
            penalties.append(10)
            alerts.append(f"Frequent rate limits: {(rate_limit_rate*100):.1f}%")

        # Engagement drop penalty
        if engagement_before > 0:
            engagement_drop = (engagement_before - engagement_after) / engagement_before
            if engagement_drop > self.RISK_THRESHOLDS["engagement_drop"]:
                penalties.append(engagement_drop * 30)
                alerts.append(f"Engagement dropped: {(engagement_drop*100):.1f}%")

        # Shadow-ban heuristic
        shadow_ban_indicators = 0
        shadow_ban_reasons = []
        if failure_rate > 0.2 and delivery_failed > 5:
            shadow_ban_indicators += 1
            shadow_ban_reasons.append("high_failure_rate")
        if engagement_drop > 0.4 and total_sent > 10:
            shadow_ban_indicators += 1
            shadow_ban_reasons.append("engagement_drop")
        if block_rate > 0.01:
            shadow_ban_indicators += 1
            shadow_ban_reasons.append("blocks")
        if spam_rate > 0.02:
            shadow_ban_indicators += 1
            shadow_ban_reasons.append("spam_flags")

        is_shadow_ban_risk = shadow_ban_indicators >= 3
        if is_shadow_ban_risk:
            penalties.append(25)
            alerts.append(f"SHADOW-BAN RISK: {shadow_ban_indicators}/4 indicators")

        final_score = max(0, base - sum(penalties))

        # Risk level
        if final_score >= 80:
            risk = "low"
        elif final_score >= 60:
            risk = "medium"
        elif final_score >= 40:
            risk = "high"
        else:
            risk = "critical"

        # Confidence
        confidence = min(1.0, total_sent / 20) if total_sent > 0 else 0.0

        return {
            "platform": platform,
            "reputation_score": round(final_score, 1),
            "base_score": base,
            "risk_level": risk,
            "total_penalty": round(sum(penalties), 1),
            "alerts": alerts,
            "shadow_ban_risk": is_shadow_ban_risk,
            "shadow_ban_indicators": shadow_ban_indicators,
            "shadow_ban_reasons": shadow_ban_reasons,
            "metrics": {
                "total_sent": total_sent,
                "delivery_failure_rate": round(failure_rate, 4),
                "spam_warning_rate": round(spam_rate, 4),
                "block_rate": round(block_rate, 4),
                "report_rate": round(report_rate, 4),
                "engagement_drop": round((engagement_before - engagement_after) / engagement_before, 4) if engagement_before > 0 else 0,
            },
            "days_window": days_window,
            "confidence": round(confidence, 3),
            "recommendation": (
                "PAUSE outreach" if risk == "critical"
                else "REDUCE volume" if risk == "high"
                else "MONITOR closely" if risk == "medium"
                else "Continue normal operations"
            ),
        }

    def get_platform_health_dashboard(self) -> Dict[str, Any]:
        """Get health dashboard for all platforms."""
        platforms = ["instagram", "facebook", "tiktok", "whatsapp", "telegram"]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platforms": {p: {"base_reputation": self.BASE_REPUTATION.get(p, 80)} for p in platforms},
            "thresholds": self.RISK_THRESHOLDS,
            "note": "Reputation scores require actual delivery data. Base scores shown.",
        }


# =============================================================================
# 2. Outreach Fatigue Detector
# =============================================================================

class OutreachFatigueDetector:
    """Detect and prevent outreach fatigue.

    Tracks message frequency per recipient, response patterns,
    and recommends cooldown periods.
    """

    # Fatigue thresholds
    FATIGUE_THRESHOLDS = {
        "max_messages_per_week": 3,
        "max_messages_per_month": 8,
        "min_response_gap_days": 7,
        "max_campaign_exposure": 2,
    }

    def calculate_fatigue_score(
        self,
        messages_sent_to_user: int,
        messages_last_7_days: int,
        messages_last_30_days: int,
        user_responses: int,
        last_response_at: Optional[datetime],
        campaigns_exposed: int,
        avg_response_time_hours: Optional[float],
    ) -> Dict[str, Any]:
        """Calculate fatigue score for a user.

        Returns:
            Dict with fatigue score (0-1), risk level, and recommendations.
        """
        fatigue = 0.0
        indicators = []

        # 1. Volume fatigue
        if messages_last_7_days >= self.FATIGUE_THRESHOLDS["max_messages_per_week"]:
            fatigue += 0.3
            indicators.append(f"weekly_limit_exceeded:{messages_last_7_days}")
        elif messages_last_7_days >= 2:
            fatigue += 0.15
            indicators.append(f"weekly_high:{messages_last_7_days}")

        if messages_last_30_days >= self.FATIGUE_THRESHOLDS["max_messages_per_month"]:
            fatigue += 0.25
            indicators.append(f"monthly_limit_exceeded:{messages_last_30_days}")

        # 2. Non-response fatigue
        if messages_sent_to_user > 0:
            response_rate = user_responses / messages_sent_to_user
            if response_rate < 0.1 and messages_sent_to_user >= 3:
                fatigue += 0.2
                indicators.append(f"low_response_rate:{response_rate:.2f}")
            elif response_rate < 0.3 and messages_sent_to_user >= 2:
                fatigue += 0.1
                indicators.append(f"moderate_response_rate:{response_rate:.2f}")

        # 3. Campaign exposure fatigue
        if campaigns_exposed >= self.FATIGUE_THRESHOLDS["max_campaign_exposure"]:
            fatigue += 0.15
            indicators.append(f"campaign_overexposed:{campaigns_exposed}")

        # 4. Recency fatigue
        if last_response_at:
            days_since = (datetime.now(timezone.utc) - last_response_at).days
            if days_since > 30 and messages_sent_to_user >= 2:
                fatigue += 0.1
                indicators.append(f"no_response_{days_since}d")

        # 5. Response time degradation
        if avg_response_time_hours and avg_response_time_hours > 48:
            fatigue += 0.1
            indicators.append(f"slow_response:{avg_response_time_hours:.0f}h")

        final_fatigue = min(1.0, fatigue)

        # Risk level
        if final_fatigue >= 0.7:
            tier = "critical"
            action = "BLOCK outreach to this user"
            cooldown_days = 30
        elif final_fatigue >= 0.5:
            tier = "high"
            action = "Recommend extended cooldown"
            cooldown_days = 14
        elif final_fatigue >= 0.3:
            tier = "medium"
            action = "Apply standard cooldown"
            cooldown_days = 7
        else:
            tier = "low"
            action = "Safe to message"
            cooldown_days = 0

        confidence = min(1.0, messages_sent_to_user / 5 + 0.3)

        return {
            "fatigue_score": round(final_fatigue, 3),
            "risk_tier": tier,
            "recommended_action": action,
            "recommended_cooldown_days": cooldown_days,
            "indicators": indicators,
            "confidence": round(confidence, 3),
            "is_blocked": tier == "critical",
            "next_eligible_date": (
                (datetime.now(timezone.utc) + timedelta(days=cooldown_days)).isoformat()
                if cooldown_days > 0 else datetime.now(timezone.utc).isoformat()
            ),
            "note": "Fatigue score estimates user receptiveness to outreach.",
        }

    def check_outreach_allowed(
        self,
        recipient_id: str,
        messages_sent_to_user: int,
        messages_last_7_days: int,
        user_responses: int,
        last_response_at: Optional[datetime],
    ) -> Dict[str, Any]:
        """Quick check if outreach to a user is allowed.

        Returns:
            Dict with allowed boolean and reason.
        """
        fatigue = self.calculate_fatigue_score(
            messages_sent_to_user=messages_sent_to_user,
            messages_last_7_days=messages_last_7_days,
            messages_last_30_days=messages_sent_to_user,
            user_responses=user_responses,
            last_response_at=last_response_at,
            campaigns_exposed=0,
            avg_response_time_hours=None,
        )

        return {
            "recipient_id": recipient_id,
            "allowed": not fatigue["is_blocked"],
            "fatigue_score": fatigue["fatigue_score"],
            "risk_tier": fatigue["risk_tier"],
            "reason": fatigue["recommended_action"],
            "cooldown_days": fatigue["recommended_cooldown_days"],
            "next_eligible_date": fatigue["next_eligible_date"],
        }

    def get_fatigue_summary(self, recipient_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get aggregate fatigue summary across recipients.

        Args:
            recipient_data: List of recipient outreach records.

        Returns:
            Summary with distribution and alerts.
        """
        if not recipient_data:
            return {"total_recipients": 0, "blocked": 0, "fatigued": 0, "healthy": 0}

        blocked = sum(1 for r in recipient_data if r.get("fatigue_score", 0) >= 0.7)
        fatigued = sum(1 for r in recipient_data if 0.3 <= r.get("fatigue_score", 0) < 0.7)
        healthy = sum(1 for r in recipient_data if r.get("fatigue_score", 0) < 0.3)

        return {
            "total_recipients": len(recipient_data),
            "blocked": blocked,
            "fatigued": fatigued,
            "healthy": healthy,
            "blocked_percentage": round(blocked / len(recipient_data) * 100, 1),
            "fatigued_percentage": round(fatigued / len(recipient_data) * 100, 1),
            "alert": blocked > len(recipient_data) * 0.1,
        }


# =============================================================================
# 3. Operator Coaching
# =============================================================================

class OperatorCoaching:
    """Provide real-time guidance and warnings to operators.

    Risk warnings, policy reminders, safe messaging tips,
    and best-practice recommendations.
    """

    # Safety tip library
    SAFETY_TIPS = [
        "Kullaniciya haftada en fazla 3 mesaj gonderin.",
        "Cevap vermeyen kullanicilara 7 gun ara verin.",
        "Spam keyword kullanmayin: FREE, WIN, CLICK NOW.",
        "Tum buyuk harf kullanmayin.",
        "Her mesaj onaydan gecmeli.",
        "Dusuk AI confidence mesajlarini manuel gozden gecirin.",
        "Platform rate limitlerine uyun.",
        "Aggressive marketing dili kullanmayin.",
        "Her mesajda dogal ve kisa dil kullanin.",
        "Kullanici tepkisini takip edin, mesaj hacmini buna gore ayarlayin.",
    ]

    POLICY_REMINDERS = {
        "instagram": "Instagram: Karsilikli takip sarti, 5 mesaj/dk limit.",
        "facebook": "Facebook: Sayfa baglantisi gerekli, 10 mesaj/dk limit.",
        "tiktok": "TikTok: Karsilikli takip, link yasak, 3 mesaj/dk limit.",
        "whatsapp": "WhatsApp: Opt-in gerekli, is saatlerinde gonderim.",
        "telegram": "Telegram: Bot baslatma gerekli, 20 mesaj/dk limit.",
    }

    def get_coaching_for_outreach(
        self,
        platform: str,
        message_type: str,
        recipient_fatigue_score: float,
        platform_reputation_score: float,
        ai_confidence: float,
        spam_risk_score: float,
        messages_sent_today: int,
        daily_quota: int,
    ) -> Dict[str, Any]:
        """Get real-time coaching guidance for an outreach attempt.

        Returns:
            Dict with warnings, recommendations, and tips.
        """
        warnings = []
        recommendations = []
        severity = "info"

        # 1. Fatigue warning
        if recipient_fatigue_score >= 0.7:
            warnings.append(f"Kullanici fatigue skoru yuksek ({recipient_fatigue_score:.2f}). Gondermeyin.")
            severity = "error"
        elif recipient_fatigue_score >= 0.5:
            warnings.append(f"Kullanici fatigue skoru orta ({recipient_fatigue_score:.2f}). Cooldown onerilir.")
            severity = "warning"

        # 2. Platform reputation warning
        if platform_reputation_score < 40:
            warnings.append(f"Platform reputation dusuk ({platform_reputation_score}). Outreach durdurulmali.")
            severity = "error"
        elif platform_reputation_score < 60:
            warnings.append(f"Platform reputation orta ({platform_reputation_score}). Dikkatli olun.")
            severity = "warning" if severity == "info" else severity

        # 3. AI confidence warning
        if ai_confidence < 0.5:
            warnings.append(f"AI confidence cok dusuk ({ai_confidence:.2f}). Manuel review gerekli.")
            severity = "error"
        elif ai_confidence < 0.7:
            warnings.append(f"AI confidence dusuk ({ai_confidence:.2f}). Dikkatli gozden gecirin.")
            severity = "warning" if severity == "info" else severity

        # 4. Spam risk warning
        if spam_risk_score >= 0.7:
            warnings.append(f"Spam risk yuksek ({spam_risk_score:.2f})! Bu mesaj gonderilmemeli.")
            severity = "error"
        elif spam_risk_score >= 0.4:
            warnings.append(f"Spam risk orta ({spam_risk_score:.2f}). Mesaji duzenleyin.")
            severity = "warning" if severity == "info" else severity

        # 5. Quota warning
        quota_pct = (messages_sent_today / daily_quota * 100) if daily_quota > 0 else 0
        if quota_pct >= 90:
            warnings.append(f"Gunluk kota neredeyse doldu ({messages_sent_today}/{daily_quota}).")
            severity = "warning" if severity == "info" else severity

        # Recommendations
        if recipient_fatigue_score < 0.3 and platform_reputation_score >= 70:
            recommendations.append("Bu kullanici guvenli. Onay ile gonderebilirsiniz.")

        if ai_confidence >= 0.8:
            recommendations.append("AI confidence yuksek. Onaylanmasi onerilir.")

        best_time = self._get_best_timing(platform)
        if best_time:
            recommendations.append(f"En iyi gonderim zamani: {best_time}.")

        # Policy reminder
        policy = self.POLICY_REMINDERS.get(platform, "")

        return {
            "platform": platform,
            "message_type": message_type,
            "severity": severity,
            "warnings": warnings,
            "recommendations": recommendations,
            "policy_reminder": policy,
            "safety_tip": self._get_random_tip(),
            "metrics": {
                "recipient_fatigue_score": round(recipient_fatigue_score, 3),
                "platform_reputation_score": round(platform_reputation_score, 1),
                "ai_confidence": round(ai_confidence, 3),
                "spam_risk_score": round(spam_risk_score, 3),
                "quota_usage_pct": round(quota_pct, 1),
            },
            "is_safe_to_proceed": (
                severity != "error" and
                recipient_fatigue_score < 0.7 and
                platform_reputation_score >= 40 and
                spam_risk_score < 0.7
            ),
            "requires_explicit_confirmation": (
                severity == "warning" or
                ai_confidence < 0.7 or
                spam_risk_score >= 0.4
            ),
        }

    def _get_best_timing(self, platform: str) -> str:
        """Get best sending time for platform."""
        import random
        hours = ["09:00-11:00", "13:00-15:00", "17:00-19:00"]
        return random.choice(hours)

    def _get_random_tip(self) -> str:
        """Get a random safety tip."""
        import random
        return random.choice(self.SAFETY_TIPS)

    def get_daily_briefing(self) -> Dict[str, Any]:
        """Get daily operator briefing."""
        return {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": "Günlük Outreach Güvenlik Özeti",
            "key_points": [
                "Tüm outbound mesajlar onay gerektirir.",
                "Auto-send kapalidir.",
                "Rate limitler: Instagram 5/dk, WhatsApp 15/dk.",
                "Fatigue skoru > 0.7 olan kullanicilara gondermeyin.",
                "AI confidence < 0.5 olan mesajlari reddedin.",
                "Platform reputation < 40 ise outreach durdurun.",
            ],
            "safety_tips": self.SAFETY_TIPS[:3],
            "policy_summary": list(self.POLICY_REMINDERS.values()),
        }
