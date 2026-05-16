"""
CTA (Call-to-Action) Engine
============================
Core engine for generating and managing CTA strategies.
Provides A/B testing support, placement optimization, and conversion tracking.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from schemas.enums import IndustryType


class CTAPlacement(str, Enum):
    """Standard CTA placement locations on a page."""
    HERO = "hero"
    NAVBAR = "navbar"
    AFTER_HERO = "after_hero"
    MID_CONTENT = "mid_content"
    AFTER_SERVICES = "after_services"
    AFTER_ABOUT = "after_about"
    AFTER_PRICING = "after_pricing"
    BEFORE_FOOTER = "before_footer"
    FOOTER = "footer"
    SIDEBAR = "sidebar"
    FLOATING = "floating"
    POPUP = "popup"
    EXIT_INTENT = "exit_intent"
    STICKY_BOTTOM = "sticky_bottom"


class CTAVariant(BaseModel):
    """A single CTA variant for A/B testing."""
    variant_id: str
    label: str = ""  # Button text
    style: str = "primary"  # primary, secondary, outline, ghost
    color: Optional[str] = None
    size: str = "medium"  # small, medium, large
    icon: Optional[str] = None
    urgency_text: Optional[str] = None
    target_url: str = "#"
    conversion_rate: Optional[float] = None
    impressions: int = 0
    clicks: int = 0

    def get_ctr(self) -> float:
        """Calculate click-through rate."""
        if self.impressions == 0:
            return 0.0
        return (self.clicks / self.impressions) * 100

    class Config:
        extra = "allow"


class CTAStrategy(BaseModel):
    """A complete CTA strategy for a page or site."""
    strategy_id: str
    page_id: str
    industry: IndustryType

    # Primary CTA
    primary_label: str
    primary_url: str
    primary_placements: List[CTAPlacement]
    primary_variants: List[CTAVariant]

    # Secondary CTA
    secondary_label: Optional[str] = None
    secondary_url: Optional[str] = None
    secondary_placements: Optional[List[CTAPlacement]] = None

    # Strategy settings
    urgency_enabled: bool = False
    countdown_target: Optional[datetime] = None
    social_proof_enabled: bool = True
    scarcity_enabled: bool = False

    # Performance
    target_conversion_rate: float = 3.0  # Target CTR %
    created_at: Optional[datetime] = None

    class Config:
        extra = "allow"


class CTAEngine:
    """
    Core engine for CTA strategy generation and optimization.
    Provides industry-aware recommendations and A/B testing support.
    """

    def __init__(self):
        self._strategies: Dict[str, CTAStrategy] = {}
        self._industry_defaults: Dict[IndustryType, Dict[str, Any]] = self._load_industry_defaults()

    # ── Industry Defaults ──────────────────────────────────────

    def _load_industry_defaults(self) -> Dict[IndustryType, Dict[str, Any]]:
        """Load industry-specific CTA defaults."""
        return {
            IndustryType.RESTAURANT: {
                "primary_label": "Rezervasyon Yap",
                "primary_url": "#reservation",
                "secondary_label": "Menüyü Gör",
                "secondary_url": "#menu",
                "placements": [CTAPlacement.HERO, CTAPlacement.AFTER_ABOUT, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.CAFE: {
                "primary_label": "Menüyü Keşfet",
                "primary_url": "#menu",
                "secondary_label": "Konumumuz",
                "secondary_url": "#location",
                "placements": [CTAPlacement.HERO, CTAPlacement.AFTER_SERVICES],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.HEALTHCARE: {
                "primary_label": "Randevu Al",
                "primary_url": "#appointment",
                "secondary_label": "Hizmetlerimiz",
                "secondary_url": "#services",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_SERVICES, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.FITNESS: {
                "primary_label": "Ücretsiz Deneme",
                "primary_url": "#trial",
                "secondary_label": "Paketleri İncele",
                "secondary_url": "#pricing",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_PRICING, CTAPlacement.FLOATING],
                "urgency": True,
                "social_proof": True,
            },
            IndustryType.SALON: {
                "primary_label": "Randevu Al",
                "primary_url": "#appointment",
                "secondary_label": "Hizmetler",
                "secondary_url": "#services",
                "placements": [CTAPlacement.HERO, CTAPlacement.AFTER_SERVICES, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.HOTEL: {
                "primary_label": "Rezervasyon Yap",
                "primary_url": "#reservation",
                "secondary_label": "Odaları İncele",
                "secondary_url": "#rooms",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_ABOUT, CTAPlacement.STICKY_BOTTOM],
                "urgency": True,
                "social_proof": True,
            },
            IndustryType.RETAIL: {
                "primary_label": "Alışverişe Başla",
                "primary_url": "#shop",
                "secondary_label": "Kampanyalar",
                "secondary_url": "#deals",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_SERVICES, CTAPlacement.STICKY_BOTTOM],
                "urgency": True,
                "social_proof": True,
            },
            IndustryType.TECHNOLOGY: {
                "primary_label": "Ücretsiz Demo",
                "primary_url": "#demo",
                "secondary_label": "Daha Fazla Bilgi",
                "secondary_url": "#features",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_SERVICES, CTAPlacement.FLOATING],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.CONSULTING: {
                "primary_label": "Ücretsiz Danışma",
                "primary_url": "#consultation",
                "secondary_label": "Referanslar",
                "secondary_url": "#testimonials",
                "placements": [CTAPlacement.HERO, CTAPlacement.AFTER_ABOUT, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.CONSTRUCTION: {
                "primary_label": "Teklif Al",
                "primary_url": "#quote",
                "secondary_label": "Projelerimiz",
                "secondary_url": "#projects",
                "placements": [CTAPlacement.HERO, CTAPlacement.AFTER_SERVICES, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": True,
            },
            IndustryType.EDUCATION: {
                "primary_label": "Kayıt Ol",
                "primary_url": "#register",
                "secondary_label": "Programları İncele",
                "secondary_url": "#programs",
                "placements": [CTAPlacement.HERO, CTAPlacement.NAVBAR, CTAPlacement.AFTER_SERVICES],
                "urgency": True,
                "social_proof": True,
            },
            IndustryType.GENERIC: {
                "primary_label": "Bize Ulaşın",
                "primary_url": "#contact",
                "secondary_label": "Daha Fazla Bilgi",
                "secondary_url": "#about",
                "placements": [CTAPlacement.HERO, CTAPlacement.BEFORE_FOOTER],
                "urgency": False,
                "social_proof": False,
            },
        }

    # ── Strategy Generation ────────────────────────────────────

    def generate_strategy(
        self,
        page_id: str,
        industry: IndustryType,
        custom_label: Optional[str] = None,
        custom_url: Optional[str] = None,
        enable_ab_test: bool = False,
    ) -> CTAStrategy:
        """
        Generate a CTA strategy for a given page and industry.

        Args:
            page_id: The page identifier
            industry: Business industry type
            custom_label: Override primary CTA label
            custom_url: Override primary CTA URL
            enable_ab_test: Generate A/B test variants

        Returns:
            A complete CTAStrategy instance
        """
        defaults = self._industry_defaults.get(industry, self._industry_defaults[IndustryType.GENERIC])

        # Generate variants for A/B testing
        variants = []
        if enable_ab_test:
            variants = self._generate_ab_variants(
                custom_label or defaults["primary_label"],
                custom_url or defaults["primary_url"],
            )
        else:
            variants = [CTAVariant(
                variant_id="a",
                label=custom_label or defaults["primary_label"],
                target_url=custom_url or defaults["primary_url"],
            )]

        strategy = CTAStrategy(
            strategy_id=f"cta_{page_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            page_id=page_id,
            industry=industry,
            primary_label=custom_label or defaults["primary_label"],
            primary_url=custom_url or defaults["primary_url"],
            primary_placements=defaults["placements"],
            primary_variants=variants,
            secondary_label=defaults.get("secondary_label"),
            secondary_url=defaults.get("secondary_url"),
            urgency_enabled=defaults.get("urgency", False),
            social_proof_enabled=defaults.get("social_proof", False),
        )

        self._strategies[strategy.strategy_id] = strategy
        return strategy

    def _generate_ab_variants(self, base_label: str, base_url: str) -> List[CTAVariant]:
        """Generate A/B test variants for a CTA."""
        return [
            CTAVariant(variant_id="a", label=base_label, target_url=base_url, style="primary"),
            CTAVariant(variant_id="b", label=f"{base_label} →", target_url=base_url, style="primary", icon="arrow-right"),
            CTAVariant(variant_id="c", label=base_label, target_url=base_url, style="secondary", size="large"),
        ]

    # ── Strategy Management ────────────────────────────────────

    def get_strategy(self, strategy_id: str) -> Optional[CTAStrategy]:
        """Get a strategy by ID."""
        return self._strategies.get(strategy_id)

    def list_strategies(self) -> List[str]:
        """List all strategy IDs."""
        return list(self._strategies.keys())

    def update_strategy(self, strategy_id: str, **updates) -> Optional[CTAStrategy]:
        """Update a strategy."""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            for key, value in updates.items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)
        return strategy

    # ── Performance Tracking ───────────────────────────────────

    def record_impression(self, strategy_id: str, variant_id: str) -> None:
        """Record a CTA impression."""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            for variant in strategy.primary_variants:
                if variant.variant_id == variant_id:
                    variant.impressions += 1
                    break

    def record_click(self, strategy_id: str, variant_id: str) -> None:
        """Record a CTA click."""
        strategy = self._strategies.get(strategy_id)
        if strategy:
            for variant in strategy.primary_variants:
                if variant.variant_id == variant_id:
                    variant.clicks += 1
                    break

    def get_best_variant(self, strategy_id: str) -> Optional[CTAVariant]:
        """Get the best performing variant for a strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy or not strategy.primary_variants:
            return None
        return max(strategy.primary_variants, key=lambda v: v.get_ctr())

    # ── Optimization Tips ──────────────────────────────────────

    def get_optimization_tips(self, strategy_id: str) -> List[str]:
        """Get optimization tips for a CTA strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return []

        tips = []
        defaults = self._industry_defaults.get(strategy.industry, {})

        # Check placements
        if CTAPlacement.HERO not in strategy.primary_placements:
            tips.append("Hero bölümüne CTA eklemek dönüşümü %25 artırabilir.")

        # Check urgency
        if defaults.get("urgency") and not strategy.urgency_enabled:
            tips.append("Aciliyet duygusu eklemek ('Sınırlı Sayıda') dönüşümü artırabilir.")

        # Check social proof
        if defaults.get("social_proof") and not strategy.social_proof_enabled:
            tips.append("Sosyal kanıt (müşteri sayısı, değerlendirmeler) ekleyin.")

        # Check floating CTA
        if CTAPlacement.FLOATING not in strategy.primary_placements and CTAPlacement.STICKY_BOTTOM not in strategy.primary_placements:
            tips.append("Sabit/floating CTA eklemek mobil dönüşümü artırabilir.")

        # Check A/B testing
        if len(strategy.primary_variants) < 2:
            tips.append("A/B testi ile farklı CTA metinlerini deneyin.")

        tips.extend([
            "CTA buton rengini kontrastlı seçin (turuncu, yeşil, mavi).",
            "Buton metninde eylem kelimeleri kullanın ('Başla', 'Keşfet', 'Al').",
            "Mobil cihazlarda CTA'ların en az 44px yüksekliğinde olmasına dikkat edin.",
        ])

        return tips


# Singleton
_engine_instance: Optional[CTAEngine] = None


def get_cta_engine() -> CTAEngine:
    """Get the singleton CTAEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CTAEngine()
    return _engine_instance
