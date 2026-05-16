"""
CTA (Call-to-Action) Recommendations Package
=============================================
AI-powered CTA strategy and recommendation engine.
Provides industry-aware, conversion-optimized CTA suggestions.
"""

from .cta_engine import (
    CTAEngine,
    get_cta_engine,
    CTAStrategy,
    CTAPlacement,
    CTAVariant,
)
from .cta_recommendations import (
    get_cta_recommendations,
    get_industry_cta_strategy,
    get_conversion_tips,
)

__all__ = [
    "CTAEngine",
    "get_cta_engine",
    "CTAStrategy",
    "CTAPlacement",
    "CTAVariant",
    "get_cta_recommendations",
    "get_industry_cta_strategy",
    "get_conversion_tips",
]
