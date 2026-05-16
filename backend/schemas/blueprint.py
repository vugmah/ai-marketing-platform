"""
AI Website Blueprint Schema
============================
Defines the JSON structure used by AI to generate complete website specifications.
This is the primary interface between AI reasoning and the website builder.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .enums import (
    IndustryType,
    BusinessSize,
    ColorScheme,
    FontPair,
    AnimationLevel,
    DeviceTarget,
    SectionType,
)


class BlueprintSection(BaseModel):
    """A section specification within an AI blueprint."""
    section_type: SectionType = Field(..., description="Type of section to create")
    name: Optional[str] = Field(None, description="Human-readable name")
    purpose: Optional[str] = Field(None, description="AI-generated purpose description")
    position: int = Field(0, description="Order on the page")
    layout_variant: str = Field("default", description="Named layout variant")
    content_guidelines: Optional[str] = Field(None, description="AI content generation hints")
    style_overrides: Optional[Dict[str, Any]] = Field(None, description="Section-specific style")
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Section-specific config")
    required_data: Optional[List[str]] = Field(None, description="Data fields needed")
    estimated_tokens: int = Field(0, description="Estimated content generation tokens")

    class Config:
        extra = "allow"


class BlueprintPage(BaseModel):
    """A page specification within an AI blueprint."""
    page_id: str = Field(..., description="Unique page identifier")
    page_name: str = Field(..., description="Human-readable page name")
    slug: str = Field(..., description="URL path")
    is_homepage: bool = Field(False)
    meta_title: Optional[str] = Field(None)
    meta_description: Optional[str] = Field(None)
    purpose: Optional[str] = Field(None, description="Why this page exists")
    sections: List[BlueprintSection] = Field(default_factory=list)
    navigation: Optional[Dict[str, Any]] = Field(None)

    class Config:
        extra = "allow"


class BlueprintRecommendation(BaseModel):
    """AI-generated recommendation for website improvement."""
    category: str = Field(..., description="seo, conversion, ux, accessibility, performance, content")
    priority: str = Field(..., description="critical, high, medium, low")
    title: str = Field(..., description="Short recommendation title")
    description: str = Field(..., description="Detailed explanation")
    actionable_steps: Optional[List[str]] = Field(None)
    expected_impact: Optional[str] = Field(None)
    auto_applicable: bool = Field(False, description="Can be auto-applied by AI")

    class Config:
        extra = "allow"


class Blueprint(BaseModel):
    """
    The complete AI-generated website blueprint.
    This is the top-level structure that AI fills out to specify a website.
    """
    # Blueprint metadata
    blueprint_version: str = Field("2.0.0")
    generated_by: str = Field("ai", description="ai, template, user, import")
    generation_prompt: Optional[str] = Field(None, description="Original user prompt")
    confidence_score: float = Field(1.0, ge=0.0, le=1.0, description="AI confidence")

    # Business context
    industry: IndustryType = Field(...)
    business_size: BusinessSize = Field(BusinessSize.SMALL)
    business_name: Optional[str] = Field(None)
    business_description: Optional[str] = Field(None)
    target_audience: Optional[str] = Field(None)
    tone_of_voice: Optional[str] = Field(None, description="professional, friendly, luxury, playful...")

    # Design specification
    color_scheme: ColorScheme = Field(ColorScheme.CORPORATE_BLUE)
    custom_colors: Optional[Dict[str, str]] = Field(None, description="Specific hex colors")
    font_pair: FontPair = Field(FontPair.MODERN_SANS)
    animation_level: AnimationLevel = Field(AnimationLevel.SUBTLE)
    device_target: DeviceTarget = Field(DeviceTarget.ALL_DEVICES)

    # Page structure
    pages: List[BlueprintPage] = Field(default_factory=list)

    # Global sections (shared across pages)
    global_header: Optional[BlueprintSection] = Field(None)
    global_footer: Optional[BlueprintSection] = Field(None)
    global_cta: Optional[BlueprintSection] = Field(None)

    # CTA Strategy
    primary_cta: Optional[str] = Field(None, description="Main call-to-action text")
    primary_cta_link: Optional[str] = Field(None)
    secondary_cta: Optional[str] = Field(None)
    cta_locations: Optional[List[str]] = Field(None, description="Where CTAs appear")

    # AI Recommendations
    recommendations: List[BlueprintRecommendation] = Field(default_factory=list)

    # Feature flags
    features: Dict[str, bool] = Field(default_factory=lambda: {
        "contact_form": True,
        "appointment_booking": False,
        "ecommerce": False,
        "blog": False,
        "multilingual": False,
        "dark_mode": False,
        "live_chat": False,
        "newsletter": False,
        "social_feed": False,
        "search": False,
        "reservations": False,
        "reviews": True,
    })

    class Config:
        extra = "allow"

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    def to_json(self, indent: Optional[int] = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Blueprint":
        return cls(**data)

    # ── Factory ────────────────────────────────────────────────

    @classmethod
    def create(cls, industry: IndustryType, business_name: str, **kwargs) -> "Blueprint":
        """Factory method for quick blueprint creation."""
        return cls(industry=industry, business_name=business_name, **kwargs)

    # ── Utility Methods ────────────────────────────────────────

    def add_page(self, page: BlueprintPage) -> "Blueprint":
        self.pages.append(page)
        return self

    def add_recommendation(self, rec: BlueprintRecommendation) -> "Blueprint":
        self.recommendations.append(rec)
        return self

    def get_total_sections(self) -> int:
        """Count total sections across all pages."""
        return sum(len(p.sections) for p in self.pages)

    def get_featured_pages(self) -> List[BlueprintPage]:
        """Get pages ordered by importance (homepage first)."""
        return sorted(self.pages, key=lambda p: (not p.is_homepage, p.page_id))

    def enable_feature(self, feature: str) -> "Blueprint":
        """Enable a feature flag."""
        self.features[feature] = True
        return self

    def disable_feature(self, feature: str) -> "Blueprint":
        """Disable a feature flag."""
        self.features[feature] = False
        return self
