"""AI Message Performance Learning + Safe Rollout Analytics

Tracks AI message effectiveness, learns from outcomes,
and provides safe rollout analytics per tenant and platform.
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# P2: AI Message Performance Learning
# =============================================================================

class MessagePerformanceTracker:
    """Track and learn from AI message performance.

    Measures response rates, recovery rates, block rates,
    and generates template performance insights.
    """

    def calculate_template_performance(
        self,
        template_id: str,
        message_type: str,
        platform: str,
        total_sent: int,
        responses_received: int,
        blocks_received: int,
        reports_received: int,
        conversions: int,
        re_engagements: int,
    ) -> Dict[str, Any]:
        """Calculate performance metrics for a message template.

        Returns:
            Dict with response rate, recovery rate, and quality score.
        """
        if total_sent == 0:
            return {
                "template_id": template_id,
                "message_type": message_type,
                "platform": platform,
                "response_rate": 0.0,
                "recovery_rate": 0.0,
                "block_rate": 0.0,
                "report_rate": 0.0,
                "conversion_rate": 0.0,
                "quality_score": 0.0,
                "confidence": 0.0,
                "note": "No messages sent with this template.",
            }

        response_rate = responses_received / total_sent
        block_rate = blocks_received / total_sent
        report_rate = reports_received / total_sent
        conversion_rate = conversions / total_sent if conversions else 0.0
        recovery_rate = re_engagements / total_sent if re_engagements else 0.0

        # Quality score (0-100): high response + low block = high quality
        quality = (
            response_rate * 100 * 0.4 +
            (1 - block_rate) * 100 * 0.3 +
            (1 - report_rate) * 100 * 0.2 +
            conversion_rate * 100 * 0.1
        )
        quality = max(0, min(100, quality))

        # Confidence based on sample size
        confidence = min(1.0, total_sent / 30)

        # Classification
        if quality >= 70:
            tier = "high_performing"
        elif quality >= 40:
            tier = "average"
        else:
            tier = "low_performing"

        return {
            "template_id": template_id,
            "message_type": message_type,
            "platform": platform,
            "total_sent": total_sent,
            "response_rate": round(response_rate * 100, 2),
            "recovery_rate": round(recovery_rate * 100, 2),
            "block_rate": round(block_rate * 100, 2),
            "report_rate": round(report_rate * 100, 2),
            "conversion_rate": round(conversion_rate * 100, 2),
            "quality_score": round(quality, 1),
            "tier": tier,
            "confidence": round(confidence, 3),
            "recommendation": (
                "Scale usage" if tier == "high_performing"
                else "Review and improve" if tier == "low_performing"
                else "Continue monitoring"
            ),
        }

    def analyze_branch_performance(
        self,
        branch_id: int,
        branch_name: str,
        template_performances: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze messaging performance per branch.

        Returns:
            Branch-level insights and recommendations.
        """
        if not template_performances:
            return {"branch_id": branch_id, "note": "No data available."}

        avg_response = statistics.mean([t["response_rate"] for t in template_performances])
        avg_block = statistics.mean([t["block_rate"] for t in template_performances])
        avg_quality = statistics.mean([t["quality_score"] for t in template_performances])

        best = max(template_performances, key=lambda t: t["quality_score"])
        worst = min(template_performances, key=lambda t: t["quality_score"])

        return {
            "branch_id": branch_id,
            "branch_name": branch_name,
            "average_response_rate": round(avg_response, 2),
            "average_block_rate": round(avg_block, 2),
            "average_quality_score": round(avg_quality, 1),
            "best_performing_template": {
                "id": best["template_id"],
                "type": best["message_type"],
                "score": best["quality_score"],
            },
            "worst_performing_template": {
                "id": worst["template_id"],
                "type": worst["message_type"],
                "score": worst["quality_score"],
            },
            "template_count": len(template_performances),
            "insights": self._generate_branch_insights(avg_response, avg_block, avg_quality),
        }

    def _generate_branch_insights(
        self, response_rate: float, block_rate: float, quality: float
    ) -> List[str]:
        """Generate insights for branch performance."""
        insights = []
        if response_rate > 25:
            insights.append("Yuksek yanit orani. Mevcut stratejiyi surdurun.")
        elif response_rate < 10:
            insights.append("Dusuk yanit orani. Mesaj icerigini gozden gecirin.")
        if block_rate > 2:
            insights.append("Yuksek block orani! Spam riski var. Mesajlari yumusatin.")
        if quality < 40:
            insights.append("Dusuk kalite skoru. AI sablonlarini yeniden degerlendirin.")
        if not insights:
            insights.append("Performans normal. Mevcut yaklasimi koruyun.")
        return insights

    def analyze_platform_performance(
        self,
        platform: str,
        template_performances: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze messaging performance per platform."""
        if not template_performances:
            return {"platform": platform, "note": "No data available."}

        avg_response = statistics.mean([t["response_rate"] for t in template_performances])
        avg_block = statistics.mean([t["block_rate"] for t in template_performances])
        avg_quality = statistics.mean([t["quality_score"] for t in template_performances])

        # Platform safety ranking
        safety_score = 100 - avg_block * 10 - (100 - avg_response) * 0.3
        safety_score = max(0, min(100, safety_score))

        return {
            "platform": platform,
            "average_response_rate": round(avg_response, 2),
            "average_block_rate": round(avg_block, 2),
            "average_quality_score": round(avg_quality, 1),
            "safety_score": round(safety_score, 1),
            "template_count": len(template_performances),
            "classification": (
                "safe" if safety_score >= 80
                else "caution" if safety_score >= 60
                else "risky"
            ),
        }

    def get_high_performing_templates(
        self, performances: List[Dict[str, Any]], min_quality: float = 70.0
    ) -> List[Dict[str, Any]]:
        """Filter high-performing templates."""
        return [p for p in performances if p["quality_score"] >= min_quality and p["confidence"] >= 0.5]

    def get_low_performing_templates(
        self, performances: List[Dict[str, Any]], max_quality: float = 40.0
    ) -> List[Dict[str, Any]]:
        """Filter low-performing templates."""
        return [p for p in performances if p["quality_score"] <= max_quality and p["confidence"] >= 0.5]

    def calculate_operator_override_rate(
        self,
        total_ai_suggestions: int,
        operator_approved: int,
        operator_rejected: int,
        operator_modified: int,
    ) -> Dict[str, Any]:
        """Calculate how often operators override AI suggestions."""
        if total_ai_suggestions == 0:
            return {"note": "No AI suggestions to analyze."}

        approval_rate = operator_approved / total_ai_suggestions
        rejection_rate = operator_rejected / total_ai_suggestions
        modification_rate = operator_modified / total_ai_suggestions
        override_rate = rejection_rate + modification_rate

        return {
            "total_suggestions": total_ai_suggestions,
            "approval_rate": round(approval_rate * 100, 1),
            "rejection_rate": round(rejection_rate * 100, 1),
            "modification_rate": round(modification_rate * 100, 1),
            "override_rate": round(override_rate * 100, 1),
            "ai_usefulness": (
                "high" if approval_rate >= 0.75
                else "medium" if approval_rate >= 0.50
                else "low"
            ),
            "recommendation": (
                "AI suggestions are reliable" if approval_rate >= 0.75
                else "Review AI training data" if approval_rate < 0.50
                else "Monitor and adjust"
            ),
        }


# =============================================================================
# P5: Safe Rollout Analytics
# =============================================================================

class SafeRolloutAnalytics:
    """Analytics for safe pilot rollout scaling.

    Tracks tenant safety, platform performance, and generates
    safe scaling recommendations.
    """

    # Safety thresholds for scaling
    SAFE_SCALE_THRESHOLDS = {
        "max_avg_spam_risk": 0.3,
        "min_avg_response_rate": 10.0,     # 10%
        "max_avg_block_rate": 2.0,         # 2%
        "max_avg_override_rate": 50.0,     # 50%
        "min_platform_reputation": 60,
        "max_fatigued_recipient_pct": 30.0, # 30%
    }

    def analyze_tenant_safety(
        self,
        company_id: int,
        tenant_name: str,
        avg_spam_risk: float,
        avg_response_rate: float,
        avg_block_rate: float,
        avg_override_rate: float,
        platform_reputations: Dict[str, float],
        fatigued_recipient_pct: float,
        days_active: int,
    ) -> Dict[str, Any]:
        """Analyze tenant safety for rollout.

        Returns:
            Safety assessment with pass/fail criteria.
        """
        checks = []
        passed = 0
        failed = 0

        # Check 1: Spam risk
        spam_ok = avg_spam_risk <= self.SAFE_SCALE_THRESHOLDS["max_avg_spam_risk"]
        checks.append({
            "check": "spam_risk",
            "value": round(avg_spam_risk, 3),
            "threshold": self.SAFE_SCALE_THRESHOLDS["max_avg_spam_risk"],
            "passed": spam_ok,
        })
        passed += 1 if spam_ok else 0
        failed += 0 if spam_ok else 1

        # Check 2: Response rate
        response_ok = avg_response_rate >= self.SAFE_SCALE_THRESHOLDS["min_avg_response_rate"]
        checks.append({
            "check": "response_rate",
            "value": round(avg_response_rate, 1),
            "threshold": self.SAFE_SCALE_THRESHOLDS["min_avg_response_rate"],
            "passed": response_ok,
        })
        passed += 1 if response_ok else 0
        failed += 0 if response_ok else 1

        # Check 3: Block rate
        block_ok = avg_block_rate <= self.SAFE_SCALE_THRESHOLDS["max_avg_block_rate"]
        checks.append({
            "check": "block_rate",
            "value": round(avg_block_rate, 2),
            "threshold": self.SAFE_SCALE_THRESHOLDS["max_avg_block_rate"],
            "passed": block_ok,
        })
        passed += 1 if block_ok else 0
        failed += 0 if block_ok else 1

        # Check 4: Override rate
        override_ok = avg_override_rate <= self.SAFE_SCALE_THRESHOLDS["max_avg_override_rate"]
        checks.append({
            "check": "operator_override_rate",
            "value": round(avg_override_rate, 1),
            "threshold": self.SAFE_SCALE_THRESHOLDS["max_avg_override_rate"],
            "passed": override_ok,
        })
        passed += 1 if override_ok else 0
        failed += 0 if override_ok else 1

        # Check 5: Platform reputation
        min_reputation = min(platform_reputations.values()) if platform_reputations else 100
        reputation_ok = min_reputation >= self.SAFE_SCALE_THRESHOLDS["min_platform_reputation"]
        checks.append({
            "check": "platform_reputation",
            "value": round(min_reputation, 1),
            "threshold": self.SAFE_SCALE_THRESHOLDS["min_platform_reputation"],
            "passed": reputation_ok,
        })
        passed += 1 if reputation_ok else 0
        failed += 0 if reputation_ok else 1

        # Check 6: Fatigue
        fatigue_ok = fatigued_recipient_pct <= self.SAFE_SCALE_THRESHOLDS["max_fatigued_recipient_pct"]
        checks.append({
            "check": "fatigued_recipients",
            "value": round(fatigued_recipient_pct, 1),
            "threshold": self.SAFE_SCALE_THRESHOLDS["max_fatigued_recipient_pct"],
            "passed": fatigue_ok,
        })
        passed += 1 if fatigue_ok else 0
        failed += 0 if fatigue_ok else 1

        overall_pass = failed == 0
        safety_score = (passed / len(checks)) * 100 if checks else 0

        return {
            "company_id": company_id,
            "tenant_name": tenant_name,
            "days_active": days_active,
            "safety_score": round(safety_score, 1),
            "overall_passed": overall_pass,
            "checks_passed": passed,
            "checks_failed": failed,
            "checks": checks,
            "can_scale": overall_pass and days_active >= 7,
            "scaling_recommendation": (
                "Safe to scale" if overall_pass and days_active >= 7
                else "Monitor before scaling" if overall_pass
                else "FIX ISSUES before scaling"
            ),
        }

    def get_scaling_plan(
        self,
        tenant_safety_scores: List[Dict[str, Any]],
        current_tenant_count: int,
        target_tenant_count: int,
    ) -> Dict[str, Any]:
        """Generate safe scaling plan.

        Args:
            tenant_safety_scores: Safety scores for each active tenant.
            current_tenant_count: Current number of tenants.
            target_tenant_count: Target number of tenants.

        Returns:
            Scaling plan with phased approach.
        """
        safe_tenants = sum(1 for t in tenant_safety_scores if t.get("can_scale", False))
        total_tenants = len(tenant_safety_scores)

        avg_safety = (
            statistics.mean([t["safety_score"] for t in tenant_safety_scores])
            if tenant_safety_scores else 0
        )

        # Determine phase
        if avg_safety >= 90 and safe_tenants == total_tenants:
            phase = "phase_3_full"
            can_add = target_tenant_count - current_tenant_count
            max_new_per_week = 5
        elif avg_safety >= 70 and safe_tenants >= total_tenants * 0.8:
            phase = "phase_2_moderate"
            can_add = min(3, target_tenant_count - current_tenant_count)
            max_new_per_week = 2
        else:
            phase = "phase_1_cautious"
            can_add = min(1, target_tenant_count - current_tenant_count)
            max_new_per_week = 1

        return {
            "current_tenants": current_tenant_count,
            "target_tenants": target_tenant_count,
            "safe_tenants": safe_tenants,
            "average_safety_score": round(avg_safety, 1),
            "phase": phase,
            "can_add_tenants": max(0, can_add),
            "max_new_per_week": max_new_per_week,
            "weekly_plan": self._generate_weekly_plan(
                current_tenant_count, target_tenant_count, max_new_per_week, phase
            ),
            "abort_criteria": [
                "Avg spam risk > 0.5 across any tenant",
                "Block rate > 3% on any platform",
                "Platform reputation drops below 40",
                "Operator override rate > 70%",
                "More than 1 report per day per tenant",
            ],
        }

    def _generate_weekly_plan(
        self, current: int, target: int, max_new: int, phase: str
    ) -> List[Dict[str, Any]]:
        """Generate weekly tenant addition plan."""
        plan = []
        week = 1
        tenants = current
        while tenants < target and week <= 8:
            add = min(max_new, target - tenants)
            tenants += add
            plan.append({
                "week": week,
                "new_tenants": add,
                "total_tenants": tenants,
                "phase": phase if week <= 2 else "phase_3_full",
            })
            week += 1
        return plan

    def get_safe_platform_ranking(
        self, platform_performances: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank platforms by safety score.

        Returns:
            Sorted list of platforms (safest first).
        """
        ranked = sorted(
            platform_performances,
            key=lambda p: p.get("safety_score", 0),
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "platform": p["platform"],
                "safety_score": p["safety_score"],
                "response_rate": p.get("average_response_rate"),
                "block_rate": p.get("average_block_rate"),
                "classification": p.get("classification"),
            }
            for i, p in enumerate(ranked)
        ]

    def detect_risky_usage_patterns(
        self,
        tenant_metrics: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect risky usage patterns across tenants.

        Returns:
            List of detected risks with severity.
        """
        risks = []

        for tm in tenant_metrics:
            # Pattern 1: High volume + low response
            if tm.get("messages_sent", 0) > 20 and tm.get("response_rate", 0) < 5:
                risks.append({
                    "tenant_id": tm.get("company_id"),
                    "pattern": "high_volume_low_response",
                    "severity": "high",
                    "detail": f"{tm['messages_sent']} messages sent but only {tm['response_rate']:.1f}% response",
                })

            # Pattern 2: High block rate
            if tm.get("block_rate", 0) > 2:
                risks.append({
                    "tenant_id": tm.get("company_id"),
                    "pattern": "high_block_rate",
                    "severity": "critical",
                    "detail": f"Block rate {tm['block_rate']:.2f}% exceeds safe threshold",
                })

            # Pattern 3: Rapid escalation in volume
            if tm.get("volume_change_pct", 0) > 50:
                risks.append({
                    "tenant_id": tm.get("company_id"),
                    "pattern": "rapid_volume_escalation",
                    "severity": "medium",
                    "detail": f"Volume increased {tm['volume_change_pct']:.0f}% in 24h",
                })

            # Pattern 4: Concentrated messaging
            if tm.get("unique_recipients", 0) > 0:
                concentration = tm.get("total_messages", 0) / tm["unique_recipients"]
                if concentration > 3:
                    risks.append({
                        "tenant_id": tm.get("company_id"),
                        "pattern": "concentrated_messaging",
                        "severity": "medium",
                        "detail": f"{concentration:.1f} messages per recipient (too concentrated)",
                    })

        return sorted(risks, key=lambda r: {"critical": 0, "high": 1, "medium": 2}.get(r["severity"], 3))

    def get_pilot_dashboard(
        self,
        tenant_safety: List[Dict[str, Any]],
        platform_rankings: List[Dict[str, Any]],
        detected_risks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get comprehensive pilot safety dashboard."""
        critical_risks = sum(1 for r in detected_risks if r["severity"] == "critical")
        high_risks = sum(1 for r in detected_risks if r["severity"] == "high")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pilot_status": (
                "HEALTHY" if critical_risks == 0 and high_risks == 0
                else "CAUTION" if critical_risks == 0
                else "AT_RISK"
            ),
            "tenant_summary": {
                "total": len(tenant_safety),
                "safe_to_scale": sum(1 for t in tenant_safety if t.get("can_scale", False)),
                "avg_safety_score": round(
                    statistics.mean([t["safety_score"] for t in tenant_safety]), 1
                ) if tenant_safety else 0,
            },
            "platform_rankings": platform_rankings,
            "risk_summary": {
                "total_risks": len(detected_risks),
                "critical": critical_risks,
                "high": high_risks,
                "medium": len(detected_risks) - critical_risks - high_risks,
            },
            "top_risks": detected_risks[:5],
            "safest_platform": platform_rankings[0]["platform"] if platform_rankings else None,
            "riskiest_pattern": detected_risks[0]["pattern"] if detected_risks else None,
        }
