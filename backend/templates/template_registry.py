"""
Template Registry
=================
Central registry for all section templates.
Maps SectionType -> template functions and manages template resolution.
"""

from typing import Dict, Any, List, Optional, Callable
from schemas.enums import IndustryType, SectionType

from .hero import get_hero_template
from .about import get_about_template
from .services import get_services_template
from .contact import get_contact_template
from .gallery import get_gallery_template
from .menu_templates import get_menu_template
from .testimonials import get_testimonials_template
from .pricing import get_pricing_template
from .cta_sections import get_cta_template
from .footer import get_footer_template
from .specialized import (
    get_reservation_template,
    get_appointment_template,
    get_faq_template,
    get_team_template,
    get_stats_template,
    get_partners_template,
    get_process_steps_template,
    get_newsletter_template,
    get_trust_badges_template,
    get_location_template,
)


# Registry: maps section type enum to template getter function
TemplateGetter = Callable[..., Dict[str, Any]]

_TEMPLATE_REGISTRY: Dict[SectionType, TemplateGetter] = {
    # Hero
    SectionType.HERO: get_hero_template,
    SectionType.HERO_VIDEO: get_hero_template,
    SectionType.HERO_SLIDER: get_hero_template,
    SectionType.HERO_SPLIT: get_hero_template,
    SectionType.HERO_MINIMAL: get_hero_template,

    # About
    SectionType.ABOUT: get_about_template,
    SectionType.ABOUT_SPLIT: get_about_template,
    SectionType.ABOUT_TEAM: get_about_template,
    SectionType.ABOUT_STATS: get_about_template,

    # Services
    SectionType.SERVICES: get_services_template,
    SectionType.SERVICES_GRID: get_services_template,
    SectionType.SERVICES_CARDS: get_services_template,
    SectionType.PRODUCTS: get_services_template,
    SectionType.PRODUCT_SHOWCASE: get_services_template,
    SectionType.FEATURES: get_services_template,
    SectionType.FEATURES_TABS: get_services_template,

    # Contact
    SectionType.CONTACT: get_contact_template,
    SectionType.CONTACT_FORM: get_contact_template,
    SectionType.CONTACT_MAP: get_contact_template,
    SectionType.CONTACT_INFO: get_contact_template,

    # Gallery
    SectionType.GALLERY: get_gallery_template,
    SectionType.GALLERY_MASONRY: get_gallery_template,
    SectionType.GALLERY_CAROUSEL: get_gallery_template,
    SectionType.IMAGE_GRID: get_gallery_template,
    SectionType.VIDEO_SECTION: get_gallery_template,

    # Menu
    SectionType.MENU: get_menu_template,
    SectionType.MENU_BOARD: get_menu_template,

    # Testimonials
    SectionType.TESTIMONIALS: get_testimonials_template,
    SectionType.TESTIMONIALS_CAROUSEL: get_testimonials_template,
    SectionType.TESTIMONIALS_GRID: get_testimonials_template,

    # Pricing
    SectionType.PRICING: get_pricing_template,
    SectionType.PRICING_TABLES: get_pricing_template,
    SectionType.PRICING_TOGGLE: get_pricing_template,

    # CTA
    SectionType.CTA: get_cta_template,
    SectionType.CTA_BANNER: get_cta_template,
    SectionType.CTA_SPLIT: get_cta_template,
    SectionType.CTA_FLOATING: get_cta_template,

    # Footer
    SectionType.FOOTER: get_footer_template,
    SectionType.FOOTER_MINIMAL: get_footer_template,
    SectionType.FOOTER_MEGA: get_footer_template,

    # Specialized
    SectionType.RESERVATION: get_reservation_template,
    SectionType.APPOINTMENT: get_appointment_template,
    SectionType.FAQ: get_faq_template,
    SectionType.FAQ_ACCORDION: get_faq_template,
    SectionType.ABOUT_TEAM: get_team_template,
    SectionType.STATS_COUNTERS: get_stats_template,
    SectionType.PARTNERS_LOGOS: get_partners_template,
    SectionType.PROCESS_STEPS: get_process_steps_template,
    SectionType.NEWSLETTER: get_newsletter_template,
    SectionType.TRUST_BADGES: get_trust_badges_template,
    SectionType.LOCATION: get_location_template,
    SectionType.MAP: get_location_template,
}


class TemplateRegistry:
    """
    Central registry for managing and retrieving section templates.
    Singleton pattern - use get_template_registry() to get the instance.
    """

    def __init__(self):
        self._templates: Dict[SectionType, TemplateGetter] = dict(_TEMPLATE_REGISTRY)
        self._custom_templates: Dict[str, TemplateGetter] = {}

    # ── Template Retrieval ─────────────────────────────────────

    def get_template(
        self,
        section_type: SectionType,
        variant: str = "default",
        industry: IndustryType = IndustryType.GENERIC,
        custom_content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get a complete template for a section type.

        Args:
            section_type: The type of section
            variant: Template variant (e.g., 'default', 'split', 'carousel')
            industry: Business industry for contextual content
            custom_content: Override specific content fields

        Returns:
            Template dict with config, style, and content
        """
        getter = self._templates.get(section_type)
        if getter is None:
            return self._get_fallback_template(section_type)

        try:
            return getter(variant=variant, industry=industry, custom_content=custom_content)
        except TypeError:
            # Some templates don't accept variant/custom_content
            try:
                return getter(industry=industry)
            except TypeError:
                return getter()

    def has_template(self, section_type: SectionType) -> bool:
        """Check if a template exists for the given section type."""
        return section_type in self._templates

    def list_available_types(self) -> List[SectionType]:
        """List all section types with registered templates."""
        return list(self._templates.keys())

    # ── Template Registration ──────────────────────────────────

    def register_template(self, section_type: SectionType, getter: TemplateGetter) -> None:
        """Register a new template getter for a section type."""
        self._templates[section_type] = getter

    def register_custom(self, name: str, getter: TemplateGetter) -> None:
        """Register a custom template by name."""
        self._custom_templates[name] = getter

    # ── Bulk Operations ────────────────────────────────────────

    def get_templates_for_page(
        self,
        section_types: List[SectionType],
        industry: IndustryType = IndustryType.GENERIC,
    ) -> List[Dict[str, Any]]:
        """Get templates for multiple sections (for full page composition)."""
        return [
            self.get_template(st, industry=industry)
            for st in section_types
        ]

    def get_all_variants(self, section_type: SectionType) -> List[str]:
        """Get available variant names for a section type."""
        # Get from module-level constants if available
        from . import (
            HERO_TEMPLATES, ABOUT_TEMPLATES, SERVICES_TEMPLATES,
            CONTACT_TEMPLATES, GALLERY_TEMPLATES, MENU_TEMPLATES,
            TESTIMONIALS_TEMPLATES, PRICING_TEMPLATES, CTA_TEMPLATES,
            FOOTER_TEMPLATES,
        )

        variant_map = {
            SectionType.HERO: list(HERO_TEMPLATES.keys()),
            SectionType.HERO_VIDEO: list(HERO_TEMPLATES.keys()),
            SectionType.HERO_SLIDER: list(HERO_TEMPLATES.keys()),
            SectionType.HERO_SPLIT: list(HERO_TEMPLATES.keys()),
            SectionType.HERO_MINIMAL: list(HERO_TEMPLATES.keys()),
            SectionType.ABOUT: list(ABOUT_TEMPLATES.keys()),
            SectionType.ABOUT_SPLIT: list(ABOUT_TEMPLATES.keys()),
            SectionType.ABOUT_TEAM: list(ABOUT_TEMPLATES.keys()),
            SectionType.ABOUT_STATS: list(ABOUT_TEMPLATES.keys()),
            SectionType.SERVICES: list(SERVICES_TEMPLATES.keys()),
            SectionType.SERVICES_GRID: list(SERVICES_TEMPLATES.keys()),
            SectionType.SERVICES_CARDS: list(SERVICES_TEMPLATES.keys()),
            SectionType.CONTACT: list(CONTACT_TEMPLATES.keys()),
            SectionType.CONTACT_FORM: list(CONTACT_TEMPLATES.keys()),
            SectionType.CONTACT_MAP: list(CONTACT_TEMPLATES.keys()),
            SectionType.CONTACT_INFO: list(CONTACT_TEMPLATES.keys()),
            SectionType.GALLERY: list(GALLERY_TEMPLATES.keys()),
            SectionType.GALLERY_MASONRY: list(GALLERY_TEMPLATES.keys()),
            SectionType.GALLERY_CAROUSEL: list(GALLERY_TEMPLATES.keys()),
            SectionType.MENU: list(MENU_TEMPLATES.keys()),
            SectionType.MENU_BOARD: list(MENU_TEMPLATES.keys()),
            SectionType.TESTIMONIALS: list(TESTIMONIALS_TEMPLATES.keys()),
            SectionType.TESTIMONIALS_CAROUSEL: list(TESTIMONIALS_TEMPLATES.keys()),
            SectionType.PRICING: list(PRICING_TEMPLATES.keys()),
            SectionType.PRICING_TABLES: list(PRICING_TEMPLATES.keys()),
            SectionType.CTA: list(CTA_TEMPLATES.keys()),
            SectionType.CTA_BANNER: list(CTA_TEMPLATES.keys()),
            SectionType.CTA_SPLIT: list(CTA_TEMPLATES.keys()),
            SectionType.CTA_FLOATING: list(CTA_TEMPLATES.keys()),
            SectionType.FOOTER: list(FOOTER_TEMPLATES.keys()),
            SectionType.FOOTER_MINIMAL: list(FOOTER_TEMPLATES.keys()),
            SectionType.FOOTER_MEGA: list(FOOTER_TEMPLATES.keys()),
        }
        return variant_map.get(section_type, ["default"])

    # ── Private ────────────────────────────────────────────────

    def _get_fallback_template(self, section_type: SectionType) -> Dict[str, Any]:
        """Return a minimal fallback template."""
        return {
            "config": {"layout_variant": "default", "heading_tag": "h2"},
            "style": {"padding_top": "60px", "padding_bottom": "60px"},
            "content": {
                "title": f"{section_type.value} Bölümü",
                "description": "Bu bölüm için içerik hazırlanıyor.",
            },
        }


# Singleton instance
_registry_instance: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get the singleton TemplateRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = TemplateRegistry()
    return _registry_instance


# ── Convenience Functions ────────────────────────────────────

def get_default_content(
    section_type: SectionType,
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
) -> Dict[str, Any]:
    """Convenience function: get default template content for a section."""
    registry = get_template_registry()
    template = registry.get_template(section_type, variant=variant, industry=industry)
    return template.get("content", {})


def get_industry_defaults(industry: IndustryType) -> Dict[str, Any]:
    """
    Get a complete default page composition for an industry.
    Returns a dict with recommended section types and their templates.
    """
    from schemas.enums import SectionType

    section_types = SectionType.get_by_industry(industry)
    registry = get_template_registry()

    composition = {}
    for i, st_name in enumerate(section_types):
        try:
            st = SectionType(st_name)
        except ValueError:
            continue
        template = registry.get_template(st, industry=industry)
        composition[st_name] = {
            "order": i,
            "type": st_name,
            "template": template,
        }

    return {
        "industry": industry.value,
        "section_count": len(composition),
        "sections": composition,
    }
