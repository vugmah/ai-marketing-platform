"""Campaign Learning Module.

Kampanya analizleri ve basari faktoru ogrenme motoru.
- Kampanya metrik analizi
- Basari/fail faktoru cikarimi
- Kitle analizi
- Icerik analizi
- Zamanlama analizi
- Strateji onerileri
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Kampanya Basari Kriterleri
# =============================================================================

# Platform bazli benchmark degerleri (endustri ortalamasi)
PLATFORM_BENCHMARKS = {
    "facebook": {"ctr": 0.9, "engagement_rate": 0.09, "roas": 4.0, "cpa": 15.0},
    "instagram": {"ctr": 1.2, "engagement_rate": 1.22, "roas": 3.5, "cpa": 20.0},
    "google": {"ctr": 3.17, "engagement_rate": 0.05, "roas": 5.0, "cpa": 25.0},
    "twitter": {"ctr": 0.86, "engagement_rate": 0.045, "roas": 2.5, "cpa": 30.0},
    "linkedin": {"ctr": 0.6, "engagement_rate": 0.35, "roas": 3.0, "cpa": 50.0},
    "tiktok": {"ctr": 1.5, "engagement_rate": 5.96, "roas": 3.0, "cpa": 10.0},
    "youtube": {"ctr": 0.5, "engagement_rate": 0.5, "roas": 4.0, "cpa": 20.0},
    "whatsapp": {"ctr": 15.0, "engagement_rate": 2.0, "roas": 6.0, "cpa": 5.0},
}

# Kampanya tipi bazli basari faktorleri
CAMPAIGN_TYPE_FACTORS = {
    "awareness": ["reach", "impressions", "engagement_rate"],
    "consideration": ["ctr", "landing_page_views", "time_on_site"],
    "conversion": ["conversions", "roas", "cpa", "revenue"],
    "retention": ["repeat_purchases", "engagement_rate", "lifetime_value"],
    "lead_generation": ["leads", "cost_per_lead", "conversion_rate"],
    "traffic": ["clicks", "ctr", "bounce_rate"],
    "engagement": ["engagement_rate", "comments", "shares"],
    "app_install": ["installs", "cost_per_install", "retention_rate"],
}


@dataclass
class CampaignMetrics:
    """Kampanya metrikleri."""

    reach: int = 0
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    engagement_rate: float = 0.0
    ctr: float = 0.0
    roas: float = 0.0
    cpa: float = 0.0

    @property
    def cpc(self) -> float:
        """Maliyet tiklama basina."""
        return self.spend / self.clicks if self.clicks > 0 else 0.0

    @property
    def cpm(self) -> float:
        """Maliyet bin gosterim basina."""
        return self.spend / self.impressions * 1000 if self.impressions > 0 else 0.0

    @property
    def conversion_rate(self) -> float:
        """Donusum orani."""
        return self.conversions / self.clicks * 100 if self.clicks > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reach": self.reach,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": self.spend,
            "revenue": self.revenue,
            "engagement_rate": self.engagement_rate,
            "ctr": self.ctr,
            "roas": self.roas,
            "cpa": self.cpa,
            "cpc": self.cpc,
            "cpm": self.cpm,
            "conversion_rate": self.conversion_rate,
        }


@dataclass
class CampaignScore:
    """Kampanya skoru."""

    overall_score: float = 0.0  # 0-100
    roas_score: float = 0.0
    engagement_score: float = 0.0
    efficiency_score: float = 0.0
    reach_score: float = 0.0
    platform_comparison: Dict[str, float] = field(default_factory=dict)


class CampaignAnalyzer:
    """Kampanya analiz motoru.

    Kampanya metriklerini analiz eder, basari faktorlerini cikarir.
    """

    def __init__(self, platform: Optional[str] = None) -> None:
        self.platform = platform

    def analyze_metrics(self, metrics: CampaignMetrics) -> CampaignScore:
        """Metrikleri analiz et ve skor uret.

        Args:
            metrics: Kampanya metrikleri.

        Returns:
            CampaignScore.
        """
        score = CampaignScore()
        benchmarks = PLATFORM_BENCHMARKS.get(self.platform or "", {}) if self.platform else {}

        # ROAS skoru (0-25)
        if metrics.roas > 0:
            roas_benchmark = benchmarks.get("roas", 4.0) if benchmarks else 4.0
            score.roas_score = min(metrics.roas / roas_benchmark * 25, 25)
        else:
            score.roas_score = 0

        # Etkilesim skoru (0-25)
        if metrics.engagement_rate > 0:
            eng_benchmark = benchmarks.get("engagement_rate", 0.1) if benchmarks else 0.1
            score.engagement_score = min(metrics.engagement_rate / eng_benchmark * 25, 25)
        elif metrics.ctr > 0:
            ctr_benchmark = benchmarks.get("ctr", 1.0) if benchmarks else 1.0
            score.engagement_score = min(metrics.ctr / ctr_benchmark * 25, 25)
        else:
            score.engagement_score = 0

        # Verimlilik skoru (0-25)
        if metrics.cpa > 0:
            cpa_benchmark = benchmarks.get("cpa", 20.0) if benchmarks else 20.0
            score.efficiency_score = max(0, min((cpa_benchmark / metrics.cpa) * 25, 25))
        else:
            score.efficiency_score = 12.5  # Neutral

        # Erisim skoru (0-25)
        if metrics.reach > 0:
            score.reach_score = min(metrics.reach / 10000 * 25, 25)  # 10K reach = max
        else:
            score.reach_score = 0

        # Genel skor
        score.overall_score = (
            score.roas_score + score.engagement_score +
            score.efficiency_score + score.reach_score
        )

        # Platform karsilastirma
        if self.platform:
            score.platform_comparison = {
                "ctr_vs_benchmark": round(metrics.ctr / benchmarks.get("ctr", 1) * 100, 2) if benchmarks else 0,
                "engagement_vs_benchmark": round(metrics.engagement_rate / benchmarks.get("engagement_rate", 0.1) * 100, 2) if benchmarks else 0,
                "roas_vs_benchmark": round(metrics.roas / benchmarks.get("roas", 4) * 100, 2) if benchmarks else 0,
            }

        return score

    def extract_success_factors(self, metrics: CampaignMetrics, score: CampaignScore) -> List[str]:
        """Basari faktorlerini cikar.

        Args:
            metrics: Kampanya metrikleri.
            score: Kampanya skoru.

        Returns:
            Basari faktoru listesi.
        """
        factors = []

        if score.overall_score >= 75:
            factors.append("Mukemmel performans - tum metrikler hedef ustu")
        if score.overall_score >= 50:
            factors.append("Basarili kampanya - hedefler karsilandi")

        if metrics.roas > 5:
            factors.append("Cok yuksek donusum: ROAS 5x ustu")
        elif metrics.roas > 3:
            factors.append("Yuksek donusum: ROAS 3x ustu")

        if metrics.engagement_rate > 2:
            factors.append("Cok yuksek etkilesim orani")
        elif metrics.engagement_rate > 0.5:
            factors.append("Yuksek etkilesim orani")

        if metrics.ctr > 2:
            factors.append("Yuksek tiklama orani (CTR)")

        if metrics.conversion_rate > 5:
            factors.append("Yuksek donusum orani")

        if metrics.revenue > metrics.spend * 3:
            factors.append("Maliyetin 3 kati gelir uretildi")

        return factors

    def extract_failure_factors(self, metrics: CampaignMetrics, score: CampaignScore) -> List[str]:
        """Basarisizlik faktorlerini cikar.

        Args:
            metrics: Kampanya metrikleri.
            score: Kampanya skoru.

        Returns:
            Basarisizlik faktoru listesi.
        """
        factors = []

        if score.overall_score < 25:
            factors.append("Dusuk genel performans")

        if metrics.ctr < 0.3:
            factors.append("Dusuk tiklama orani (CTR)")

        if metrics.engagement_rate < 0.05:
            factors.append("Cok dusuk etkilesim orani")

        if metrics.roas < 1 and metrics.spend > 0:
            factors.append("ROAS 1x altinda - zarar")

        if metrics.cpa > 50:
            factors.append("Yuksek maliyet basina edinme (CPA)")

        if metrics.conversions == 0 and metrics.clicks > 0:
            factors.append("Tiklama var ama donusum yok")

        if metrics.reach < 100 and metrics.spend > 0:
            factors.append("Cok dusuk erisim")

        return factors

    def analyze_audience(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Kitle analizi yap.

        Args:
            campaign_data: Kampanya verisi.

        Returns:
            Kitle analizi sonucu.
        """
        insights = {}

        # Yas dagilimi
        age_data = campaign_data.get("age_breakdown", {})
        if age_data:
            top_age = max(age_data.items(), key=lambda x: x[1])
            insights["primary_age_group"] = top_age[0]
            insights["age_distribution"] = age_data

        # Cinsiyet
        gender_data = campaign_data.get("gender_breakdown", {})
        if gender_data:
            insights["gender_distribution"] = gender_data
            if gender_data.get("female", 0) > gender_data.get("male", 0) * 1.5:
                insights["gender_insight"] = "Kadin agirlikli kitle"
            elif gender_data.get("male", 0) > gender_data.get("female", 0) * 1.5:
                insights["gender_insight"] = "Erkek agirlikli kitle"
            else:
                insights["gender_insight"] = "Dengeli cinsiyet dagilimi"

        # Lokasyon
        location_data = campaign_data.get("location_breakdown", {})
        if location_data:
            top_locations = sorted(location_data.items(), key=lambda x: x[1], reverse=True)[:5]
            insights["top_locations"] = top_locations

        # Cihaz
        device_data = campaign_data.get("device_breakdown", {})
        if device_data:
            insights["device_distribution"] = device_data
            mobile_pct = device_data.get("mobile", 0)
            if mobile_pct > 70:
                insights["device_insight"] = "Mobil agirlikli kitle"

        # Zaman
        hour_data = campaign_data.get("hourly_breakdown", {})
        if hour_data:
            peak_hours = sorted(hour_data.items(), key=lambda x: x[1], reverse=True)[:3]
            insights["peak_hours"] = peak_hours

        return insights

    def analyze_content(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Icerik analizi yap.

        Args:
            campaign_data: Kampanya verisi.

        Returns:
            Icerik analizi sonucu.
        """
        insights = {}

        # Icerik tipi performansi
        content_types = campaign_data.get("content_type_breakdown", {})
        if content_types:
            best_type = max(content_types.items(), key=lambda x: x[1])
            insights["best_performing_content_type"] = best_type[0]
            insights["content_type_performance"] = content_types

        # Format performansi
        format_data = campaign_data.get("format_breakdown", {})
        if format_data:
            insights["format_performance"] = format_data

        # Gorsel/metin orani
        creative_data = campaign_data.get("creative_analysis", {})
        if creative_data:
            insights.update(creative_data)

        # Mesaj vurgusu
        messaging = campaign_data.get("messaging", {})
        if messaging:
            insights["messaging_effectiveness"] = messaging

        return insights

    def analyze_timing(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Zamanlama analizi yap.

        Args:
            campaign_data: Kampanya verisi.

        Returns:
            Zamanlama analizi sonucu.
        """
        insights = {}

        # Gunluk performans
        daily_data = campaign_data.get("daily_breakdown", {})
        if daily_data:
            best_day = max(daily_data.items(), key=lambda x: x[1])
            insights["best_performing_day"] = best_day[0]
            insights["daily_performance"] = daily_data

        # Saatlik performans
        hourly_data = campaign_data.get("hourly_breakdown", {})
        if hourly_data:
            peak_hours = sorted(hourly_data.items(), key=lambda x: x[1], reverse=True)[:3]
            insights["peak_hours"] = peak_hours

        # Kampanya suresi
        duration = campaign_data.get("duration_days", 0)
        if duration > 0:
            insights["campaign_duration_days"] = duration
            if duration < 7:
                insights["duration_insight"] = "Kisa sureli kampanya"
            elif duration > 30:
                insights["duration_insight"] = "Uzun sureli kampanya"
            else:
                insights["duration_insight"] = "Orta sureli kampanya"

        return insights

    def recommend_strategies(
        self,
        campaigns: List[Dict[str, Any]],
        success_factors: List[str],
        failure_factors: List[str],
    ) -> List[str]:
        """Strateji onerileri uret.

        Args:
            campaigns: Kampanya listesi.
            success_factors: Basari faktorleri.
            failure_factors: Basarisizlik faktorleri.

        Returns:
            Strateji onerileri listesi.
        """
        recommendations = []

        # Basari faktorlerine dayali oneriler
        if any("ROAS" in f for f in success_factors):
            recommendations.append("Basarili donusum stratejisi diger kampanyalara uygulanmali")

        if any("etkilesim" in f for f in success_factors):
            recommendations.append("Yuksek etkilesimli icerik formati devam etmeli")

        if any("CTR" in f for f in success_factors):
            recommendations.append("Cagri metni (CTA) stratejisi basarili - korunmali")

        # Basarisizlik faktorlerine dayali oneriler
        if any("dusuk tiklama" in f for f in failure_factors):
            recommendations.append("Cagri metni (CTA) ve basliklar iyilestirilmeli")

        if any("etkilesim" in f for f in failure_factors):
            recommendations.append("Daha ilgi cekici gorsel icerik kullanilmali")

        if any("ROAS" in f for f in failure_factors):
            recommendations.append("Hedefleme ve donusum hunisi optimize edilmeli")

        if any("CPA" in f for f in failure_factors):
            recommendations.append("Daha spesifik hedef kitle secilmeli")

        if any("donusum yok" in f for f in failure_factors):
            recommendations.append("Landing page deneyimi iyilestirilmeli")

        # Genel oneriler
        if len(campaigns) > 3:
            recommendations.append("A/B testleri ile en iyi performansli ogeler belirlenmeli")

        recommendations.append("Kampanya verileri duzenli izlenmeli ve optimize edilmeli")

        return recommendations


class CampaignLearner:
    """Kampanya ogrenme motoru.

    Birden fazla kampanyayi analiz ederek ogrenilenleri cikarir.
    """

    def __init__(self) -> None:
        self.analyzer = CampaignAnalyzer()

    def learn(
        self,
        campaigns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Kampanyalardan ogren.

        Args:
            campaigns: Kampanya veri listesi.
                Her kampanya:
                {
                    "name": str,
                    "platform": str,
                    "type": str,
                    "metrics": CampaignMetrics dict,
                    ...
                }

        Returns:
            Ogrenme sonucu dict.
        """
        if not campaigns:
            return {}

        all_success_factors = []
        all_failure_factors = []
        all_scores = []
        all_roas = []
        all_ctr = []
        all_engagement = []

        for campaign in campaigns:
            metrics_data = campaign.get("metrics", {})
            metrics = CampaignMetrics(**metrics_data)
            platform = campaign.get("platform")

            analyzer = CampaignAnalyzer(platform=platform)
            score = analyzer.analyze_metrics(metrics)

            success = analyzer.extract_success_factors(metrics, score)
            failure = analyzer.extract_failure_factors(metrics, score)

            all_success_factors.extend(success)
            all_failure_factors.extend(failure)
            all_scores.append(score.overall_score)
            all_roas.append(metrics.roas)
            all_ctr.append(metrics.ctr)
            all_engagement.append(metrics.engagement_rate)

        # Istatistiksel analiz
        avg_score = statistics.mean(all_scores) if all_scores else 0
        avg_roas = statistics.mean(all_roas) if all_roas else 0
        avg_ctr = statistics.mean(all_ctr) if all_ctr else 0
        avg_engagement = statistics.mean(all_engagement) if all_engagement else 0

        # En iyi kampanya
        best_campaign = max(campaigns, key=lambda c: c.get("metrics", {}).get("roas", 0)) if campaigns else None

        return {
            "campaigns_analyzed": len(campaigns),
            "average_score": round(avg_score, 2),
            "average_roas": round(avg_roas, 2),
            "average_ctr": round(avg_ctr, 2),
            "average_engagement_rate": round(avg_engagement, 2),
            "best_campaign": best_campaign.get("name") if best_campaign else None,
            "best_roas": round(max(all_roas), 2) if all_roas else 0,
            "success_factors": list(set(all_success_factors)),
            "failure_factors": list(set(all_failure_factors)),
            "recommended_strategies": self._generate_recommendations(
                campaigns, list(set(all_success_factors)), list(set(all_failure_factors))
            ),
        }

    def _generate_recommendations(
        self,
        campaigns: List[Dict[str, Any]],
        success_factors: List[str],
        failure_factors: List[str],
    ) -> List[str]:
        """Oneriler uret."""
        analyzer = CampaignAnalyzer()
        return analyzer.recommend_strategies(campaigns, success_factors, failure_factors)

    def compare_platforms(
        self,
        campaigns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Platform bazli karsilastirma.

        Args:
            campaigns: Kampanya listesi.

        Returns:
            Platform karsilastirmasi.
        """
        platform_data: Dict[str, List[CampaignMetrics]] = {}

        for campaign in campaigns:
            platform = campaign.get("platform", "unknown")
            metrics = CampaignMetrics(**campaign.get("metrics", {}))
            if platform not in platform_data:
                platform_data[platform] = []
            platform_data[platform].append(metrics)

        comparison = {}
        for platform, metrics_list in platform_data.items():
            avg_roas = statistics.mean([m.roas for m in metrics_list if m.roas > 0]) or 0
            avg_ctr = statistics.mean([m.ctr for m in metrics_list if m.ctr > 0]) or 0
            avg_engagement = statistics.mean([m.engagement_rate for m in metrics_list if m.engagement_rate > 0]) or 0
            total_spend = sum(m.spend for m in metrics_list)
            total_revenue = sum(m.revenue for m in metrics_list)

            comparison[platform] = {
                "campaign_count": len(metrics_list),
                "avg_roas": round(avg_roas, 2),
                "avg_ctr": round(avg_ctr, 2),
                "avg_engagement_rate": round(avg_engagement, 2),
                "total_spend": round(total_spend, 2),
                "total_revenue": round(total_revenue, 2),
                "roi": round((total_revenue - total_spend) / total_spend * 100, 2) if total_spend > 0 else 0,
            }

        # En iyi platformu belirle
        if comparison:
            best_platform = max(comparison.items(), key=lambda x: x[1]["avg_roas"])
            comparison["best_platform"] = best_platform[0]

        return comparison
