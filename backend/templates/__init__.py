"""
Website Section Templates Package
==================================
Pre-defined content templates and defaults for all supported section types.
Each template provides industry-aware content structure and default values.
"""

from .hero import get_hero_template, HERO_TEMPLATES
from .about import get_about_template, ABOUT_TEMPLATES
from .services import get_services_template, SERVICES_TEMPLATES
from .contact import get_contact_template, CONTACT_TEMPLATES
from .gallery import get_gallery_template, GALLERY_TEMPLATES
from .menu_templates import get_menu_template, MENU_TEMPLATES
from .testimonials import get_testimonials_template, TESTIMONIALS_TEMPLATES
from .pricing import get_pricing_template, PRICING_TEMPLATES
from .cta_sections import get_cta_template, CTA_TEMPLATES
from .footer import get_footer_template, FOOTER_TEMPLATES
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
from .template_registry import (
    TemplateRegistry,
    get_template_registry,
    get_default_content,
    get_industry_defaults,
)

__all__ = [
    "get_hero_template",
    "HERO_TEMPLATES",
    "get_about_template",
    "ABOUT_TEMPLATES",
    "get_services_template",
    "SERVICES_TEMPLATES",
    "get_contact_template",
    "CONTACT_TEMPLATES",
    "get_gallery_template",
    "GALLERY_TEMPLATES",
    "get_menu_template",
    "MENU_TEMPLATES",
    "get_testimonials_template",
    "TESTIMONIALS_TEMPLATES",
    "get_pricing_template",
    "PRICING_TEMPLATES",
    "get_cta_template",
    "CTA_TEMPLATES",
    "get_footer_template",
    "FOOTER_TEMPLATES",
    "get_reservation_template",
    "get_appointment_template",
    "get_faq_template",
    "get_team_template",
    "get_stats_template",
    "get_partners_template",
    "get_process_steps_template",
    "get_newsletter_template",
    "get_trust_badges_template",
    "get_location_template",
    "TemplateRegistry",
    "get_template_registry",
    "get_default_content",
    "get_industry_defaults",
]
