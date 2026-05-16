"""Governance Intelligence Layer v12

Four integrated intelligence modules:
1. CrossPlatformReputationAnalyzer — Platform risk correlation + fallback
2. AdaptiveCadenceEngine — Behavior-based outreach timing
3. TenantTrustScorer — 8-component operational trust score
4. OutreachROIAnalyzer — Recovery/retention/conversion impact

Pure analytics layer — no new DB tables. Uses existing data.
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# P1: Cross-Platform Reputation Intelligence
# =============================================================================

class CrossPlatformReputationAnalyzer:
    """Analyze reputation across all platforms with risk correlation.

    Detects cross-platform risk contagion and recommends safe platform
    fallbacks when one platform degrades.
    """

    # Platform safety ranking (higher = safer)
    PLATFORM_SAFETY_RANK = {
        "whatsapp": 95,
        "telegram": 92,
        "facebook": 90,
        "instagram": 85,
        "tiktok": 75,
    }

    # Risk correlation matrix — how risk on one platform affects others
    # Values: 0.0 = no correlation, 1.0 = full contagion
    RISK_CORRELATION = {
        ("instagram", "facebook"): 0.3,   # Meta platforms slightly correlated
        ("facebook", "instagram"): 0.3,
        ("whatsapp", "facebook"): 0.1,    # WhatsApp less correlated with FB
        ("tiktok", "instagram"): 0.2,     # Visual platforms slightly correlated
        ("telegram", "whatsapp"): 0.15,   # Messaging apps slightly correlated
    }

    def analyze_cross_platform_risk(
        self,
        platform_scores: Dict[str, float],  # platform -> reputation score
    ) -> Dict[str, Any]:
        """Analyze cross-platform risk with correlation.

        Args:
            platform_scores: Dict of platform -> reputation score (0-100).

        Returns:
            Risk analysis with contagion detection and fallback recommendations.
        """
        if not platform_scores:
            return {"note": "No platform data available."}

        # Individual platform assessments
        platform_assessments = {}
        for platform, score in platform_scores.items():
            if score >= 80:
                status = "safe"
                action = "Continue normal operations"
            elif score >= 60:
                status = "caution"
                action = "Reduce volume by 25%"
            elif score >= 40:
                status = "risky"
                action = "Reduce volume by 50%, enable extra approvals"
            else:
                status = "critical"
                action = "PAUSE outreach immediately"

            platform_assessments[platform] = {
                "score": round(score, 1),
                "status": status,
                "action": action,
                "safe_for_outreach": score >= 60,
            }

        # Cross-platform risk contagion
        contagion_alerts = []
        affected_platforms = set()

        for (src, dst), correlation in self.RISK_CORRELATION.items():
            if src not in platform_scores or dst not in platform_scores:
                continue

            src_score = platform_scores[src]
            dst_score = platform_scores[dst]

            # If source is risky, predict impact on destination
            if src_score < 60 and dst_score >= 60:
                predicted_impact = (60 - src_score) * correlation
                predicted_dst = max(0, dst_score - predicted_impact)

                if predicted_dst < 60:
                    contagion_alerts.append({
                        "source_platform": src,
                        "target_platform": dst,
                        "correlation": correlation,
                        "current_target_score": round(dst_score, 1),
                        "predicted_target_score": round(predicted_dst, 1),
                        "severity": "high" if predicted_dst < 50 else "medium",
                        "message": f"{src} degradation may spread to {dst} (predicted: {predicted_dst:.1f})",
                    })
                    affected_platforms.add(dst)

        # Find safest alternative for each risky platform
        fallback_recommendations = {}
        for platform, assessment in platform_assessments.items():
            if not assessment["safe_for_outreach"]:
                # Find safest alternative
                alternatives = {
                    p: s for p, s in platform_scores.items()
                    if p != platform and s >= 70
                }
                if alternatives:
                    best_alt = max(alternatives, key=alternatives.get)
                    fallback_recommendations[platform] = {
                        "recommended_fallback": best_alt,
                        "fallback_score": round(alternatives[best_alt], 1),
                        "transfer_volume_pct": 50 if assessment["status"] == "critical" else 25,
                    }
                else:
                    fallback_recommendations[platform] = {
                        "recommended_fallback": None,
                        "message": "No safe alternative available. Pause all outreach.",
                    }

        # Overall cross-platform health
        avg_score = statistics.mean(platform_scores.values()) if platform_scores else 0
        safe_count = sum(1 for a in platform_assessments.values() if a["safe_for_outreach"])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "platform_assessments": platform_assessments,
            "contagion_alerts": contagion_alerts,
            "affected_platforms": list(affected_platforms),
            "fallback_recommendations": fallback_recommendations,
            "overall_health": {
                "average_score": round(avg_score, 1),
                "safe_platforms": safe_count,
                "total_platforms": len(platform_scores),
                "health_status": (
                    "healthy" if avg_score >= 75 and safe_count == len(platform_scores)
                    else "degraded" if avg_score >= 50
                    else "critical"
                ),
            },
            "safest_platform": max(platform_scores, key=platform_scores.get) if platform_scores else None,
            "riskiest_platform": min(platform_scores, key=platform_scores.get) if platform_scores else None,
        }

    def get_platform_fallback_plan(
        self,
        source_platform: str,
        platform_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """Get specific fallback plan when a platform degrades.

        Example: Instagram reputation drops → shift to WhatsApp.
        """
        if source_platform not in platform_scores:
            return {"error": f"Platform {source_platform} not in scores"}

        source_score = platform_scores[source_platform]

        # Find best alternative
        alternatives = {
            p: {"score": s, "rank": self.PLATFORM_SAFETY_RANK.get(p, 80)}
            for p, s in platform_scores.items()
            if p != source_platform and s >= 60
        }

        if not alternatives:
            return {
                "source_platform": source_platform,
                "source_score": round(source_score, 1),
                "fallback_available": False,
                "action": "PAUSE all outreach. No safe alternative.",
            }

        # Rank by safety score
        ranked = sorted(alternatives.items(), key=lambda x: -x[1]["score"])

        return {
            "source_platform": source_platform,
            "source_score": round(source_score, 1),
            "fallback_available": True,
            "recommended_target": ranked[0][0],
            "target_score": round(ranked[0][1]["score"], 1),
            "transfer_plan": {
                "volume_transfer_pct": 75 if source_score < 40 else 50,
                "message_type_adjustment": "Focus on welcome and reward messages",
                "cadence_adjustment": "Use target platform's optimal cadence",
            },
            "all_alternatives": [
                {"platform": p, "score": round(d["score"], 1)}
                for p, d in ranked
            ],
            "confidence": 0.8 if ranked[0][1]["score"] >= 80 else 0.6,
        }


# =============================================================================
# P2: Adaptive Cadence Intelligence
# =============================================================================

class AdaptiveCadenceEngine:
    """Optimize outreach timing based on user behavior patterns.

    Learns from response speed, frequency, and fatigue to recommend
    the optimal next contact time.
    """

    # Response time quality tiers (hours)
    RESPONSE_TIME_TIERS = {
        "fast": (0, 6),
        "normal": (6, 24),
        "slow": (24, 72),
        "very_slow": (72, 168),
        "no_response": (168, float("inf")),
    }

    # Day-of-week effectiveness (0=Monday, 6=Sunday)
    DOW_EFFECTIVENESS = {
        0: 0.85,  # Monday
        1: 0.90,  # Tuesday
        2: 0.92,  # Wednesday
        3: 0.88,  # Thursday
        4: 0.80,  # Friday
        5: 0.50,  # Saturday
        6: 0.45,  # Sunday
    }

    # Hour effectiveness (business hours weighted)
    HOUR_EFFECTIVENESS = {
        9: 0.85, 10: 0.90, 11: 0.88,      # Morning
        13: 0.87, 14: 0.85, 15: 0.82,     # Afternoon
        17: 0.78, 18: 0.75, 19: 0.70,     # Evening
    }

    def calculate_optimal_timing(
        self,
        avg_response_time_hours: Optional[float],
        response_rate: float,
        engagement_frequency: float,
        fatigue_score: float,
        platform: str,
        branch_timezone: str = "Europe/Istanbul",
    ) -> Dict[str, Any]:
        """Calculate optimal next contact timing.

        Returns:
            Optimal date/time with confidence and reasoning.
        """
        if fatigue_score >= 0.7:
            return {
                "recommended_action": "DO NOT CONTACT",
                "next_contact_date": None,
                "cooldown_days": 30,
                "reason": f"Fatigue score too high ({fatigue_score:.2f}). User needs extended cooldown.",
                "confidence": 0.95,
            }

        if fatigue_score >= 0.5:
            base_delay_days = 14
        elif fatigue_score >= 0.3:
            base_delay_days = 7
        else:
            base_delay_days = 3

        # Adjust based on response behavior
        if avg_response_time_hours is not None:
            if avg_response_time_hours <= 6:
                base_delay_days = max(2, base_delay_days - 1)
            elif avg_response_time_hours <= 24:
                pass  # Keep base
            elif avg_response_time_hours <= 72:
                base_delay_days += 2
            else:
                base_delay_days += 5

        # Adjust based on response rate
        if response_rate >= 0.5:
            base_delay_days = max(2, base_delay_days - 1)
        elif response_rate >= 0.2:
            pass
        elif response_rate > 0:
            base_delay_days += 3
        else:
            base_delay_days += 7

        # Adjust based on engagement frequency
        if engagement_frequency >= 3:
            base_delay_days = max(2, int(base_delay_days * 0.7))
        elif engagement_frequency >= 1:
            base_delay_days = int(base_delay_days * 1.0)
        else:
            base_delay_days = int(base_delay_days * 1.5)

        # Cap delay
        base_delay_days = max(2, min(30, base_delay_days))

        # Calculate target date
        target = datetime.now(timezone.utc) + timedelta(days=base_delay_days)

        # Skip weekends for business platforms
        if platform in ["whatsapp", "facebook"] and target.weekday() >= 5:
            days_to_add = 7 - target.weekday()
            target += timedelta(days=days_to_add)

        # Find best hour
        best_hour = self._find_best_hour(target.weekday())

        # Confidence
        confidence = 0.5
        if avg_response_time_hours is not None:
            confidence += min(0.3, 1.0 / (1 + avg_response_time_hours / 24))
        if response_rate > 0:
            confidence += min(0.2, response_rate * 0.3)

        confidence = min(0.95, confidence)

        # Cadence recommendation
        cadence = self._recommend_cadence(
            response_rate, engagement_frequency, fatigue_score
        )

        return {
            "optimal_contact_date": target.strftime("%Y-%m-%d"),
            "optimal_contact_hour": best_hour,
            "optimal_contact_datetime": target.replace(hour=best_hour).isoformat(),
            "delay_days": base_delay_days,
            "confidence": round(confidence, 3),
            "cadence_recommendation": cadence,
            "reasoning": {
                "fatigue_adjustment": f"{fatigue_score:.2f} fatigue -> {base_delay_days} day base",
                "response_time_hours": avg_response_time_hours,
                "response_rate": response_rate,
                "engagement_frequency": engagement_frequency,
                "platform": platform,
            },
            "note": "Timing optimized based on user behavior patterns. Not guaranteed.",
        }

    def _find_best_hour(self, weekday: int) -> int:
        """Find best hour for the given weekday."""
        dow_eff = self.DOW_EFFECTIVENESS.get(weekday, 0.7)

        if dow_eff < 0.6:  # Weekend
            return 11  # Late morning for weekends

        # Find best hour from effectiveness map
        best_hour = 10
        best_eff = 0
        for hour, eff in self.HOUR_EFFECTIVENESS.items():
            if eff > best_eff:
                best_eff = eff
                best_hour = hour

        return best_hour

    def _recommend_cadence(
        self,
        response_rate: float,
        engagement_frequency: float,
        fatigue_score: float,
    ) -> Dict[str, Any]:
        """Recommend safe cadence for this user."""
        if response_rate >= 0.3 and fatigue_score < 0.3:
            return {
                "frequency": "weekly",
                "max_per_week": 2,
                "min_hours_between": 48,
                "classification": "responsive",
            }
        elif response_rate >= 0.1 and fatigue_score < 0.5:
            return {
                "frequency": "bi_weekly",
                "max_per_week": 1,
                "min_hours_between": 96,
                "classification": "moderate",
            }
        else:
            return {
                "frequency": "monthly",
                "max_per_week": 1,
                "min_hours_between": 168,
                "classification": "conservative",
            }

    def analyze_cadence_effectiveness(
        self,
        historical_contacts: List[Dict[str, Any]],  # List of {date, got_response, response_delay_hours}
    ) -> Dict[str, Any]:
        """Analyze effectiveness of past cadence.

        Returns:
            Cadence effectiveness analysis.
        """
        if not historical_contacts:
            return {"note": "No contact history available."}

        total = len(historical_contacts)
        responded = sum(1 for c in historical_contacts if c.get("got_response"))
        response_rate = responded / total if total > 0 else 0

        response_delays = [
            c["response_delay_hours"] for c in historical_contacts
            if c.get("response_delay_hours") is not None
        ]
        avg_delay = statistics.mean(response_delays) if response_delays else None

        # Time-between-contacts analysis
        if len(historical_contacts) >= 2:
            sorted_contacts = sorted(historical_contacts, key=lambda x: x["date"])
            gaps = []
            for i in range(1, len(sorted_contacts)):
                gap = (sorted_contacts[i]["date"] - sorted_contacts[i-1]["date"]).total_seconds() / 3600
                gaps.append(gap)
            avg_gap_hours = statistics.mean(gaps) if gaps else 0
        else:
            avg_gap_hours = 0

        return {
            "total_contacts": total,
            "responses_received": responded,
            "response_rate": round(response_rate * 100, 1),
            "average_response_delay_hours": round(avg_delay, 1) if avg_delay else None,
            "average_gap_between_contacts_hours": round(avg_gap_hours, 1),
            "effectiveness": (
                "high" if response_rate >= 0.3
                else "medium" if response_rate >= 0.1
                else "low"
            ),
            "recommendation": (
                "Maintain current cadence" if response_rate >= 0.2
                else "Increase gap between contacts" if response_rate >= 0.05
                else "Stop outreach, user not responsive"
            ),
        }


# =============================================================================
# P3: Tenant Trust & Safety Scoring
# =============================================================================

class TenantTrustScorer:
    """Calculate 8-component operational trust score per tenant.

    Components:
    1. Spam-risk score (low = good)
    2. Operator override rate (low = good)
    3. Report/block rate (low = good)
    4. Policy violation count (low = good)
    5. AI safety score (high = good)
    6. Outreach quality score (high = good)
    7. Fatigue management score (high = good)
    8. Approval discipline score (high = good)
    """

    # Component weights (must sum to 1.0)
    COMPONENT_WEIGHTS = {
        "spam_risk": 0.20,
        "operator_override": 0.10,
        "report_block_rate": 0.20,
        "policy_violations": 0.15,
        "ai_safety": 0.10,
        "outreach_quality": 0.10,
        "fatigue_management": 0.10,
        "approval_discipline": 0.05,
    }

    def calculate_trust_score(
        self,
        company_id: int,
        tenant_name: str,
        # Component inputs (all 0-100, higher = better except where noted)
        spam_risk_score: float,         # Inverted: lower risk = higher score
        operator_override_rate: float,  # Inverted: lower override = higher score
        report_block_rate: float,       # Inverted: lower rate = higher score
        policy_violation_count: int,    # Inverted: fewer violations = higher score
        ai_safety_score: float,         # Direct: higher = better
        outreach_quality_score: float,  # Direct: higher = better
        fatigue_management_score: float, # Direct: higher = better
        approval_discipline_score: float, # Direct: higher = better
    ) -> Dict[str, Any]:
        """Calculate composite trust score.

        Args:
            All scores are 0-100.

        Returns:
            Trust score with component breakdown.
        """
        # Inverted components (lower input = higher score)
        spam_component = max(0, 100 - spam_risk_score)
        override_component = max(0, 100 - operator_override_rate)
        report_block_component = max(0, 100 - report_block_rate)

        # Policy violations: exponential decay (0=100, 5=50, 10=25, 20=0)
        if policy_violation_count <= 0:
            policy_component = 100
        elif policy_violation_count >= 20:
            policy_component = 0
        else:
            policy_component = 100 * (0.95 ** policy_violation_count)

        # Direct components
        ai_component = ai_safety_score
        quality_component = outreach_quality_score
        fatigue_component = fatigue_management_score
        discipline_component = approval_discipline_score

        # Calculate weighted score
        components = {
            "spam_risk": round(spam_component, 1),
            "operator_override": round(override_component, 1),
            "report_block_rate": round(report_block_component, 1),
            "policy_violations": round(policy_component, 1),
            "ai_safety": round(ai_component, 1),
            "outreach_quality": round(quality_component, 1),
            "fatigue_management": round(fatigue_component, 1),
            "approval_discipline": round(discipline_component, 1),
        }

        trust_score = sum(
            components[name] * self.COMPONENT_WEIGHTS[name]
            for name in components
        )
        trust_score = max(0, min(100, trust_score))

        # Classification
        if trust_score >= 80:
            tier = "trusted"
            quota_multiplier = 1.5
            rollout_allowed = True
        elif trust_score >= 60:
            tier = "standard"
            quota_multiplier = 1.0
            rollout_allowed = True
        elif trust_score >= 40:
            tier = "restricted"
            quota_multiplier = 0.5
            rollout_allowed = False
        else:
            tier = "blocked"
            quota_multiplier = 0.0
            rollout_allowed = False

        # Identify weakest component
        weakest = min(components, key=components.get)

        return {
            "company_id": company_id,
            "tenant_name": tenant_name,
            "trust_score": round(trust_score, 1),
            "tier": tier,
            "components": components,
            "weakest_component": {
                "name": weakest,
                "score": components[weakest],
            },
            "quota_multiplier": quota_multiplier,
            "rollout_allowed": rollout_allowed,
            "recommendation": (
                f"Scale outreach" if tier == "trusted"
                else f"Maintain current level" if tier == "standard"
                else f"Restrict and monitor" if tier == "restricted"
                else f"PAUSE outreach, address {weakest}"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def batch_calculate_trust(
        self,
        tenant_metrics: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Calculate trust scores for multiple tenants.

        Returns:
            List of trust score results sorted by score (highest first).
        """
        results = []
        for tm in tenant_metrics:
            result = self.calculate_trust_score(
                company_id=tm["company_id"],
                tenant_name=tm["tenant_name"],
                spam_risk_score=tm.get("spam_risk_score", 50),
                operator_override_rate=tm.get("operator_override_rate", 50),
                report_block_rate=tm.get("report_block_rate", 50),
                policy_violation_count=tm.get("policy_violation_count", 0),
                ai_safety_score=tm.get("ai_safety_score", 50),
                outreach_quality_score=tm.get("outreach_quality_score", 50),
                fatigue_management_score=tm.get("fatigue_management_score", 50),
                approval_discipline_score=tm.get("approval_discipline_score", 50),
            )
            results.append(result)

        results.sort(key=lambda r: r["trust_score"], reverse=True)
        return results

    def get_trust_distribution(
        self,
        trust_scores: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get distribution of trust tiers across tenants."""
        tiers = {"trusted": 0, "standard": 0, "restricted": 0, "blocked": 0}
        for ts in trust_scores:
            tiers[ts["tier"]] = tiers.get(ts["tier"], 0) + 1

        total = len(trust_scores)
        avg_score = statistics.mean([ts["trust_score"] for ts in trust_scores]) if trust_scores else 0

        return {
            "total_tenants": total,
            "tier_distribution": tiers,
            "trusted_percentage": round(tiers["trusted"] / total * 100, 1) if total else 0,
            "average_trust_score": round(avg_score, 1),
            "rollout_ready_count": sum(1 for ts in trust_scores if ts["rollout_allowed"]),
        }


# =============================================================================
# P4: Outreach ROI Intelligence
# =============================================================================

class OutreachROIAnalyzer:
    """Analyze outreach effectiveness and ROI.

    Tracks re-engagement recovery, retention improvement,
    conversion impact, and campaign effectiveness.
    """

    def calculate_campaign_roi(
        self,
        campaign_id: str,
        campaign_type: str,
        platform: str,
        messages_sent: int,
        responses_received: int,
        re_engagements: int,        # Users who re-engaged after message
        conversions: int,
        estimated_recovery_value: float,  # Monetary value in local currency
        cost_per_message: float = 0.01,   # Approximate cost
    ) -> Dict[str, Any]:
        """Calculate ROI for a specific campaign.

        Returns:
            ROI metrics with effectiveness classification.
        """
        total_cost = messages_sent * cost_per_message

        if messages_sent == 0:
            return {
                "campaign_id": campaign_id,
                "note": "No messages sent.",
                "roi": 0.0,
            }

        response_rate = responses_received / messages_sent
        re_engagement_rate = re_engagements / messages_sent
        conversion_rate = conversions / messages_sent

        # ROI calculation
        if total_cost > 0:
            roi = (estimated_recovery_value - total_cost) / total_cost * 100
        else:
            roi = 0.0

        # Effectiveness score (0-100)
        effectiveness = (
            response_rate * 100 * 0.25 +
            re_engagement_rate * 100 * 0.35 +
            conversion_rate * 100 * 0.25 +
            min(100, max(0, roi)) * 0.15
        )

        # Classification
        if effectiveness >= 60 and roi > 0:
            tier = "effective"
        elif effectiveness >= 35:
            tier = "moderate"
        elif effectiveness >= 15:
            tier = "low_impact"
        else:
            tier = "ineffective"

        return {
            "campaign_id": campaign_id,
            "campaign_type": campaign_type,
            "platform": platform,
            "messages_sent": messages_sent,
            "total_cost": round(total_cost, 2),
            "estimated_recovery_value": round(estimated_recovery_value, 2),
            "response_rate": round(response_rate * 100, 1),
            "re_engagement_rate": round(re_engagement_rate * 100, 1),
            "conversion_rate": round(conversion_rate * 100, 1),
            "roi_percentage": round(roi, 1),
            "effectiveness_score": round(effectiveness, 1),
            "tier": tier,
            "recommendation": (
                "Scale this campaign type" if tier == "effective"
                else "Optimize and retry" if tier == "moderate"
                else "Redesign approach" if tier == "low_impact"
                else "Pause and reassess"
            ),
            "confidence": min(1.0, messages_sent / 50),
        }

    def analyze_retention_impact(
        self,
        outreach_group_retention: float,  # Retention rate of users who received outreach
        control_group_retention: float,    # Retention rate of users who did NOT receive outreach
        outreach_group_size: int,
        control_group_size: int,
    ) -> Dict[str, Any]:
        """Analyze whether outreach improved retention.

        Returns:
            Retention impact analysis with lift calculation.
        """
        retention_lift = outreach_group_retention - control_group_retention

        if control_group_retention > 0:
            lift_percentage = (retention_lift / control_group_retention) * 100
        else:
            lift_percentage = 0.0

        # Statistical significance estimate (simplified)
        if outreach_group_size >= 30 and control_group_size >= 30:
            confidence = 0.7
        elif outreach_group_size >= 10 and control_group_size >= 10:
            confidence = 0.5
        else:
            confidence = 0.3

        return {
            "outreach_group_retention": round(outreach_group_retention, 2),
            "control_group_retention": round(control_group_retention, 2),
            "retention_lift_absolute": round(retention_lift, 3),
            "retention_lift_percentage": round(lift_percentage, 1),
            "outreach_group_size": outreach_group_size,
            "control_group_size": control_group_size,
            "statistical_confidence": confidence,
            "outreach_worked": retention_lift > 0,
            "recommendation": (
                "Outreach significantly improves retention" if lift_percentage > 20
                else "Outreach moderately improves retention" if lift_percentage > 5
                else "Outreach has minimal retention impact" if lift_percentage > 0
                else "Outreach may hurt retention — investigate"
            ),
            "note": "Retention impact is an estimate. Requires A/B testing for validation.",
        }

    def get_best_outreach_types(
        self,
        campaign_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Rank outreach types by effectiveness.

        Returns:
            Ranked list of outreach types with ROI.
        """
        # Group by campaign type
        by_type: Dict[str, List[Dict]] = {}
        for cr in campaign_results:
            ct = cr.get("campaign_type", "unknown")
            if ct not in by_type:
                by_type[ct] = []
            by_type[ct].append(cr)

        type_summaries = []
        for c_type, campaigns in by_type.items():
            avg_effectiveness = statistics.mean([c["effectiveness_score"] for c in campaigns])
            avg_roi = statistics.mean([c["roi_percentage"] for c in campaigns])
            avg_response = statistics.mean([c["response_rate"] for c in campaigns])
            total_sent = sum(c["messages_sent"] for c in campaigns)

            type_summaries.append({
                "campaign_type": c_type,
                "avg_effectiveness": round(avg_effectiveness, 1),
                "avg_roi": round(avg_roi, 1),
                "avg_response_rate": round(avg_response, 1),
                "total_messages_sent": total_sent,
                "campaign_count": len(campaigns),
            })

        type_summaries.sort(key=lambda x: -x["avg_effectiveness"])

        return {
            "ranked_types": type_summaries,
            "best_type": type_summaries[0] if type_summaries else None,
            "worst_type": type_summaries[-1] if type_summaries else None,
            "total_campaigns_analyzed": len(campaign_results),
        }

    def get_branch_roi_comparison(
        self,
        branch_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compare ROI across branches.

        Returns:
            Branches ranked by ROI (best first).
        """
        branches = sorted(branch_results, key=lambda b: -b.get("effectiveness_score", 0))
        return [
            {
                "branch_id": b.get("branch_id"),
                "branch_name": b.get("branch_name"),
                "effectiveness_score": b.get("effectiveness_score"),
                "roi_percentage": b.get("roi_percentage"),
                "response_rate": b.get("response_rate"),
                "messages_sent": b.get("messages_sent"),
            }
            for b in branches
        ]

    def detect_ineffective_outreach(
        self,
        campaign_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect ineffective or risky outreach patterns.

        Returns:
            List of ineffective campaigns with recommendations.
        """
        ineffective = []

        for cr in campaign_results:
            issues = []

            if cr["response_rate"] < 5:
                issues.append("Very low response rate")
            if cr.get("roi_percentage", 0) < -50:
                issues.append("Negative ROI")
            if cr.get("effectiveness_score", 100) < 15:
                issues.append("Very low effectiveness")
            if cr["messages_sent"] > 50 and cr["response_rate"] < 2:
                issues.append("High volume, no engagement (spam-like)")

            if issues:
                ineffective.append({
                    "campaign_id": cr["campaign_id"],
                    "campaign_type": cr["campaign_type"],
                    "platform": cr["platform"],
                    "issues": issues,
                    "effectiveness_score": cr.get("effectiveness_score", 0),
                    "recommendation": "Pause and redesign" if len(issues) >= 2 else "Review and optimize",
                })

        return sorted(ineffective, key=lambda x: x["effectiveness_score"])
