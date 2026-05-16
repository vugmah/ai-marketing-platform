"""Governance Dashboard Expansion v12

Aggregates all governance intelligence into unified dashboard views.
No new DB tables — pure analytics aggregator.
"""

import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.followers.governance_intelligence import (
    AdaptiveCadenceEngine,
    CrossPlatformReputationAnalyzer,
    OutreachROIAnalyzer,
    TenantTrustScorer,
)


class GovernanceDashboard:
    """Unified governance dashboard aggregator.

    Combines reputation, cadence, trust, ROI, fatigue, and operator
    metrics into comprehensive dashboard views.
    """

    def __init__(self) -> None:
        self.reputation = CrossPlatformReputationAnalyzer()
        self.cadence = AdaptiveCadenceEngine()
        self.trust = TenantTrustScorer()
        self.roi = OutreachROIAnalyzer()

    def get_executive_dashboard(
        self,
        platform_scores: Dict[str, float],
        tenant_trust_scores: List[Dict[str, Any]],
        campaign_results: List[Dict[str, Any]],
        fatigue_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get executive governance dashboard.

        Returns:
            High-level governance health overview.
        """
        # Cross-platform reputation
        reputation = self.reputation.analyze_cross_platform_risk(platform_scores)

        # Trust distribution
        trust_dist = self.trust.get_trust_distribution(tenant_trust_scores)

        # ROI summary
        best_types = self.roi.get_best_outreach_types(campaign_results)
        ineffective = self.roi.detect_ineffective_outreach(campaign_results)

        # Fatigue summary
        fatigued_pct = (
            sum(1 for f in fatigue_data if f.get("fatigue_score", 0) >= 0.5)
            / len(fatigue_data) * 100 if fatigue_data else 0
        )

        # Calculate overall governance score (0-100)
        rep_health = reputation["overall_health"]["average_score"]
        trust_health = trust_dist["average_trust_score"]
        roi_health = (
            best_types["ranked_types"][0]["avg_effectiveness"] if best_types["ranked_types"] else 50
        )
        fatigue_health = max(0, 100 - fatigued_pct)

        governance_score = (
            rep_health * 0.25 +
            trust_health * 0.30 +
            roi_health * 0.25 +
            fatigue_health * 0.20
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "governance_score": round(governance_score, 1),
            "health_status": (
                "HEALTHY" if governance_score >= 75
                else "CAUTION" if governance_score >= 50
                else "AT_RISK"
            ),
            "components": {
                "reputation_health": round(rep_health, 1),
                "trust_health": round(trust_health, 1),
                "roi_health": round(roi_health, 1),
                "fatigue_health": round(fatigue_health, 1),
            },
            "platforms": {
                "safest": reputation.get("safest_platform"),
                "riskiest": reputation.get("riskiest_platform"),
                "safe_count": reputation["overall_health"]["safe_platforms"],
                "total_count": reputation["overall_health"]["total_platforms"],
            },
            "tenants": {
                "total": trust_dist["total_tenants"],
                "trusted": trust_dist["tier_distribution"].get("trusted", 0),
                "ready_for_rollout": trust_dist["rollout_ready_count"],
                "avg_trust_score": trust_dist["average_trust_score"],
            },
            "outreach": {
                "best_campaign_type": best_types["best_type"]["campaign_type"] if best_types["best_type"] else None,
                "best_effectiveness": best_types["best_type"]["avg_effectiveness"] if best_types["best_type"] else 0,
                "ineffective_campaigns": len(ineffective),
            },
            "fatigue": {
                "fatigued_recipient_percentage": round(fatigued_pct, 1),
                "status": "concerning" if fatigued_pct > 30 else "acceptable" if fatigued_pct > 15 else "healthy",
            },
            "alerts": self._generate_alerts(reputation, trust_dist, ineffective, fatigued_pct),
        }

    def get_platform_dashboard(
        self,
        platform_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """Get platform-specific governance dashboard.

        Returns:
            Per-platform risk and fallback information.
        """
        reputation = self.reputation.analyze_cross_platform_risk(platform_scores)

        platforms = []
        for platform, assessment in reputation["platform_assessments"].items():
            # Get fallback plan if risky
            fallback = None
            if not assessment["safe_for_outreach"]:
                fallback = self.reputation.get_platform_fallback_plan(
                    platform, platform_scores
                )

            platforms.append({
                "platform": platform,
                "reputation_score": assessment["score"],
                "status": assessment["status"],
                "safe_for_outreach": assessment["safe_for_outreach"],
                "fallback_available": fallback.get("fallback_available", False) if fallback else False,
                "fallback_target": fallback.get("recommended_target") if fallback else None,
                "rank": self.reputation.PLATFORM_SAFETY_RANK.get(platform, 80),
            })

        # Sort by score (safest first)
        platforms.sort(key=lambda p: -p["reputation_score"])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platforms": platforms,
            "contagion_alerts": reputation["contagion_alerts"],
            "overall_health": reputation["overall_health"],
            "recommendation": (
                "All platforms safe" if all(p["safe_for_outreach"] for p in platforms)
                else "Fallback plans active for risky platforms"
            ),
        }

    def get_tenant_dashboard(
        self,
        trust_scores: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get tenant trust and safety dashboard.

        Returns:
            Per-tenant trust scores with rollout readiness.
        """
        distribution = self.trust.get_trust_distribution(trust_scores)

        tenants = []
        for ts in trust_scores:
            tenants.append({
                "company_id": ts["company_id"],
                "tenant_name": ts["tenant_name"],
                "trust_score": ts["trust_score"],
                "tier": ts["tier"],
                "quota_multiplier": ts["quota_multiplier"],
                "rollout_allowed": ts["rollout_allowed"],
                "weakest_component": ts["weakest_component"],
            })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "distribution": distribution,
            "tenants": tenants,
            "scaling_recommendation": (
                "Safe to scale" if distribution["trusted_percentage"] >= 70
                else "Scale cautiously" if distribution["trusted_percentage"] >= 40
                else "Do not scale — address trust issues first"
            ),
        }

    def get_roi_dashboard(
        self,
        campaign_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get outreach ROI dashboard.

        Returns:
            Campaign effectiveness and ROI analysis.
        """
        best_types = self.roi.get_best_outreach_types(campaign_results)
        ineffective = self.roi.detect_ineffective_outreach(campaign_results)
        branch_comparison = self.roi.get_branch_roi_comparison(campaign_results)

        # Overall ROI
        if campaign_results:
            avg_roi = statistics.mean([c.get("roi_percentage", 0) for c in campaign_results])
            avg_effectiveness = statistics.mean([c.get("effectiveness_score", 0) for c in campaign_results])
            total_sent = sum(c.get("messages_sent", 0) for c in campaign_results)
        else:
            avg_roi = 0
            avg_effectiveness = 0
            total_sent = 0

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_campaigns": len(campaign_results),
                "total_messages_sent": total_sent,
                "average_roi": round(avg_roi, 1),
                "average_effectiveness": round(avg_effectiveness, 1),
            },
            "best_performers": best_types["ranked_types"][:3],
            "worst_performers": best_types["ranked_types"][-3:] if len(best_types["ranked_types"]) >= 3 else best_types["ranked_types"],
            "ineffective_campaigns": ineffective[:5],
            "branch_comparison": branch_comparison[:5],
        }

    def get_risk_escalation_dashboard(
        self,
        platform_scores: Dict[str, float],
        trust_scores: List[Dict[str, Any]],
        fatigue_data: List[Dict[str, Any]],
        ineffective_campaigns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get risk escalation dashboard.

        Returns:
            All active risks with severity and actions.
        """
        risks = []

        # Platform risks
        for platform, score in platform_scores.items():
            if score < 60:
                risks.append({
                    "category": "platform_reputation",
                    "severity": "critical" if score < 40 else "high",
                    "source": platform,
                    "detail": f"Platform reputation: {score:.1f}",
                    "action": "Pause outreach" if score < 40 else "Reduce volume 50%",
                })

        # Tenant risks
        for ts in trust_scores:
            if ts["tier"] == "blocked":
                risks.append({
                    "category": "tenant_trust",
                    "severity": "critical",
                    "source": ts["tenant_name"],
                    "detail": f"Trust score: {ts['trust_score']:.1f}",
                    "action": "PAUSE all outreach",
                })
            elif ts["tier"] == "restricted":
                risks.append({
                    "category": "tenant_trust",
                    "severity": "high",
                    "source": ts["tenant_name"],
                    "detail": f"Trust score: {ts['trust_score']:.1f}",
                    "action": "Restrict volume by 50%",
                })

        # Fatigue risks
        fatigued_count = sum(1 for f in fatigue_data if f.get("fatigue_score", 0) >= 0.7)
        if fatigued_count > 0:
            risks.append({
                "category": "recipient_fatigue",
                "severity": "medium",
                "source": f"{fatigued_count} recipients",
                "detail": f"Recipients with critical fatigue",
                "action": "Apply extended cooldown (30 days)",
            })

        # Campaign risks
        for ic in ineffective_campaigns[:3]:
            risks.append({
                "category": "campaign_effectiveness",
                "severity": "medium",
                "source": ic["campaign_id"],
                "detail": f"Effectiveness: {ic['effectiveness_score']:.1f}. Issues: {', '.join(ic['issues'])}",
                "action": ic["recommendation"],
            })

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        risks.sort(key=lambda r: severity_order.get(r["severity"], 4))

        critical_count = sum(1 for r in risks if r["severity"] == "critical")
        high_count = sum(1 for r in risks if r["severity"] == "high")

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_risks": len(risks),
            "critical": critical_count,
            "high": high_count,
            "medium": len(risks) - critical_count - high_count,
            "risks": risks,
            "status": (
                "CRITICAL" if critical_count > 0
                else "ELEVATED" if high_count > 0
                else "MONITORING" if len(risks) > 0
                else "CLEAR"
            ),
        }

    def _generate_alerts(
        self,
        reputation: Dict[str, Any],
        trust_dist: Dict[str, Any],
        ineffective: List[Dict[str, Any]],
        fatigued_pct: float,
    ) -> List[Dict[str, Any]]:
        """Generate consolidated alerts."""
        alerts = []

        if reputation["overall_health"]["health_status"] == "critical":
            alerts.append({
                "severity": "critical",
                "message": "Platform reputation critical — pause outreach",
            })

        if trust_dist["trusted_percentage"] < 50:
            alerts.append({
                "severity": "high",
                "message": f"Only {trust_dist['trusted_percentage']:.0f}% tenants trusted",
            })

        if len(ineffective) > 3:
            alerts.append({
                "severity": "medium",
                "message": f"{len(ineffective)} ineffective campaigns detected",
            })

        if fatigued_pct > 30:
            alerts.append({
                "severity": "high",
                "message": f"{fatigued_pct:.0f}% recipients fatigued",
            })

        if reputation["contagion_alerts"]:
            for alert in reputation["contagion_alerts"][:2]:
                alerts.append({
                    "severity": alert["severity"],
                    "message": alert["message"],
                })

        if not alerts:
            alerts.append({
                "severity": "info",
                "message": "All governance indicators within safe ranges",
            })

        return alerts

    def get_full_dashboard(
        self,
        platform_scores: Dict[str, float],
        tenant_trust_scores: List[Dict[str, Any]],
        campaign_results: List[Dict[str, Any]],
        fatigue_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get complete governance dashboard (all views combined).

        Returns:
            Unified dashboard with all governance metrics.
        """
        executive = self.get_executive_dashboard(
            platform_scores, tenant_trust_scores, campaign_results, fatigue_data
        )
        platform = self.get_platform_dashboard(platform_scores)
        tenant = self.get_tenant_dashboard(tenant_trust_scores)
        roi = self.get_roi_dashboard(campaign_results)
        risk = self.get_risk_escalation_dashboard(
            platform_scores, tenant_trust_scores, fatigue_data,
            roi.get("ineffective_campaigns", [])
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "v12",
            "executive": executive,
            "platform": platform,
            "tenant": tenant,
            "roi": roi,
            "risk": risk,
            "disclaimer": (
                "All metrics are estimates based on available data. "
                "ROI calculations use simplified models. "
                "Trust scores require 7+ days of operational data for accuracy."
            ),
        }
