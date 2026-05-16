"""
Site schema - top-level container for the entire website.
Contains global config, all pages, and cross-cutting concerns.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

from .page import Page, PageMeta, PageNavigation
from .section import Section
from .enums import (
    IndustryType,
    BusinessSize,
    ColorScheme,
    FontPair,
    AnimationLevel,
    DeviceTarget,
)


class SiteAnalytics(BaseModel):
    """Analytics and tracking configuration."""
    google_analytics_id: Optional[str] = None
    google_tag_manager_id: Optional[str] = None
    facebook_pixel_id: Optional[str] = None
    hotjar_id: Optional[str] = None
    custom_scripts: Optional[List[str]] = None
    cookie_consent_enabled: bool = True
    privacy_policy_url: Optional[str] = None

    class Config:
        extra = "allow"


class SiteNavigation(BaseModel):
    """Global navigation settings."""
    style: str = Field("horizontal", description="horizontal, vertical, hamburger, mega")
    sticky: bool = Field(True, description="Fixed position on scroll")
    transparent_on_top: bool = Field(False)
    logo_position: str = Field("left", description="left, center, right")
    search_enabled: bool = Field(False)
    language_switcher: bool = Field(False)
    cta_button_text: Optional[str] = None
    cta_button_link: Optional[str] = None
    mobile_breakpoint: str = Field("768px")
    dropdown_animation: str = Field("fade", description="fade, slide, none")

    class Config:
        extra = "allow"


class SiteMeta(BaseModel):
    """Global site metadata."""
    site_name: str = Field(..., description="Website name/title")
    tagline: Optional[str] = None
    favicon_url: Optional[str] = None
    logo_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    primary_language: str = Field("tr", description="ISO 639-1 language code")
    supported_languages: List[str] = Field(default_factory=lambda: ["tr"])
    timezone: str = Field("Europe/Istanbul")
    currency: str = Field("TRY", description="ISO 4217 currency code")
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict, description="platform -> URL")

    class Config:
        extra = "allow"


class SiteConfig(BaseModel):
    """Global site configuration and design tokens."""
    # Industry & business
    industry: IndustryType = Field(IndustryType.GENERIC)
    business_size: BusinessSize = Field(BusinessSize.SMALL)

    # Design tokens
    color_scheme: ColorScheme = Field(ColorScheme.CORPORATE_BLUE)
    primary_color: str = Field("#2563eb", description="Brand primary color")
    secondary_color: str = Field("#1e40af", description="Brand secondary color")
    accent_color: str = Field("#f59e0b", description="Accent/CTA color")
    background_color: str = Field("#ffffff")
    surface_color: str = Field("#f8fafc", description="Card/section background")
    text_primary_color: str = Field("#1e293b")
    text_secondary_color: str = Field("#64748b")
    border_color: str = Field("#e2e8f0")

    # Typography
    font_pair: FontPair = Field(FontPair.MODERN_SANS)
    heading_font: Optional[str] = None
    body_font: Optional[str] = None
    base_font_size: str = Field("16px")
    heading_scale: float = Field(1.25, description="Heading size multiplier")

    # Layout
    max_content_width: str = Field("1280px")
    content_padding: str = Field("1.5rem")
    grid_columns: int = Field(12)
    gutter_width: str = Field("1.5rem")
    border_radius: str = Field("0.5rem")
    border_radius_large: str = Field("1rem")

    # Animation & Effects
    animation_level: AnimationLevel = Field(AnimationLevel.SUBTLE)
    enable_smooth_scroll: bool = Field(True)
    enable_back_to_top: bool = Field(True)
    enable_page_transitions: bool = Field(False)

    # Responsive
    device_target: DeviceTarget = Field(DeviceTarget.ALL_DEVICES)
    breakpoints: Dict[str, str] = Field(default_factory=lambda: {
        "xs": "0px",
        "sm": "576px",
        "md": "768px",
        "lg": "992px",
        "xl": "1200px",
        "xxl": "1400px",
    })

    # Advanced
    enable_dark_mode: bool = Field(False)
    dark_mode_default: bool = Field(False)
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None

    class Config:
        extra = "allow"


class Site(BaseModel):
    """
    The root container for an entire website.
    Contains all pages, global config, navigation, and metadata.
    """
    id: str = Field(..., description="Unique site identifier")
    version: str = Field("1.0.0", description="Schema version")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: str = Field("draft", description="draft, published, archived")

    # Global settings
    config: SiteConfig = Field(default_factory=lambda: SiteConfig(industry=IndustryType.GENERIC))
    meta: SiteMeta = Field(default_factory=lambda: SiteMeta(site_name="My Website"))
    navigation: SiteNavigation = Field(default_factory=SiteNavigation)
    analytics: SiteAnalytics = Field(default_factory=SiteAnalytics)

    # Pages
    pages: List[Page] = Field(default_factory=list)

    # Shared/Reusable sections (headers, footers, CTAs)
    shared_sections: Dict[str, Section] = Field(default_factory=dict)

    # Branch-specific overrides
    branch_overrides: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="branch_id -> override config"
    )

    class Config:
        extra = "allow"

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize site to plain dict."""
        return self.model_dump(mode="json", exclude_none=True)

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize site to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Site":
        """Create Site from a dictionary."""
        pages_data = data.pop("pages", [])
        shared_data = data.pop("shared_sections", {})
        pages = [Page.from_dict(p) for p in pages_data]
        shared = {k: Section.from_dict(v) for k, v in shared_data.items()}
        return cls(pages=pages, shared_sections=shared, **data)

    # ── Factory ────────────────────────────────────────────────

    @classmethod
    def create(cls, site_id: str, site_name: str, industry: IndustryType = IndustryType.GENERIC, **kwargs) -> "Site":
        """Factory method for quick site creation."""
        return cls(
            id=site_id,
            meta=SiteMeta(site_name=site_name),
            config=SiteConfig(industry=industry),
            **kwargs
        )

    # ── Page Management ────────────────────────────────────────

    def add_page(self, page: Page) -> "Site":
        """Add a page to the site."""
        self.pages.append(page)
        return self

    def get_page(self, page_id: str) -> Optional[Page]:
        """Get page by ID."""
        for page in self.pages:
            if page.id == page_id:
                return page
        return None

    def get_page_by_slug(self, slug: str) -> Optional[Page]:
        """Get page by slug."""
        for page in self.pages:
            if page.slug == slug:
                return page
        return None

    def get_homepage(self) -> Optional[Page]:
        """Get the homepage."""
        for page in self.pages:
            if page.is_homepage:
                return page
        return self.pages[0] if self.pages else None

    def remove_page(self, page_id: str) -> bool:
        """Remove a page by ID."""
        for i, page in enumerate(self.pages):
            if page.id == page_id:
                self.pages.pop(i)
                return True
        return False

    def get_nav_pages(self) -> List[Page]:
        """Get pages that should appear in navigation."""
        nav_pages = [p for p in self.pages if p.navigation.show_in_nav and p.is_visible]
        return sorted(nav_pages, key=lambda p: p.navigation.nav_order)

    # ── Shared Sections ────────────────────────────────────────

    def set_shared_section(self, key: str, section: Section) -> "Site":
        """Set a shared/reusable section."""
        self.shared_sections[key] = section
        return self

    def get_shared_section(self, key: str) -> Optional[Section]:
        """Get a shared section by key."""
        return self.shared_sections.get(key)

    # ── Branch Overrides ───────────────────────────────────────

    def set_branch_override(self, branch_id: str, overrides: Dict[str, Any]) -> "Site":
        """Set branch-specific configuration overrides."""
        self.branch_overrides[branch_id] = overrides
        return self

    def get_branch_override(self, branch_id: str) -> Optional[Dict[str, Any]]:
        """Get branch-specific overrides."""
        return self.branch_overrides.get(branch_id)

    def apply_branch_overrides(self, branch_id: str) -> "Site":
        """Apply branch overrides to the current site config."""
        overrides = self.branch_overrides.get(branch_id)
        if overrides:
            if "config" in overrides:
                for key, value in overrides["config"].items():
                    setattr(self.config, key, value)
            if "meta" in overrides:
                for key, value in overrides["meta"].items():
                    setattr(self.meta, key, value)
        return self
