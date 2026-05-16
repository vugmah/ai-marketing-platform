"""
Site Assembler
===============
Assembles a complete Site from a Blueprint by resolving templates,
generating content, and composing pages with sections.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from schemas.enums import IndustryType, SectionType
from schemas.site import Site, SiteConfig, SiteMeta, SiteNavigation, SiteAnalytics
from schemas.page import Page, PageMeta, PageNavigation
from schemas.section import Section, SectionConfig, SectionStyle
from schemas.blueprint import Blueprint, BlueprintPage, BlueprintSection

from templates.template_registry import get_template_registry, get_industry_defaults


class AssemblyConfig(BaseModel):
    """Configuration for site assembly."""
    generate_content: bool = True
    apply_templates: bool = True
    validate_output: bool = True
    include_shared_sections: bool = True
    enable_animations: bool = True

    class Config:
        extra = "allow"


class SiteAssembler:
    """
    Assembles a complete Site instance from a Blueprint.
    Orchestrates template resolution, content generation, and page composition.
    """

    def __init__(self):
        self._template_registry = get_template_registry()

    def assemble(self, blueprint: Blueprint, config: Optional[AssemblyConfig] = None) -> Site:
        """
        Assemble a complete Site from a Blueprint.

        Args:
            blueprint: The AI-generated website blueprint
            config: Assembly configuration options

        Returns:
            A complete Site instance with all pages and sections
        """
        cfg = config or AssemblyConfig()

        # 1. Create base site configuration
        site_config = self._build_site_config(blueprint)
        site_meta = self._build_site_meta(blueprint)

        # 2. Create shared sections (navbar, footer, CTA)
        shared_sections: Dict[str, Section] = {}
        if cfg.include_shared_sections:
            shared_sections = self._build_shared_sections(blueprint)

        # 3. Build pages from blueprint
        pages: List[Page] = []
        for bp_page in blueprint.pages:
            page = self._build_page(bp_page, blueprint, cfg)
            pages.append(page)

        # 4. Set homepage if not set
        if pages and not any(p.is_homepage for p in pages):
            pages[0].is_homepage = True

        # 5. Compose the site
        site = Site(
            id=f"site_{blueprint.industry.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            version="1.0.0",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status="draft",
            config=site_config,
            meta=site_meta,
            shared_sections=shared_sections,
            pages=pages,
        )

        # 6. Validate if requested
        if cfg.validate_output:
            issues = self._validate_site(site)
            if issues:
                # Store validation issues in meta
                site.meta_info = {"validation_issues": issues}

        return site

    def _build_site_config(self, blueprint: Blueprint) -> SiteConfig:
        """Build site configuration from blueprint."""
        config = SiteConfig(
            industry=blueprint.industry,
            business_size=blueprint.business_size,
            color_scheme=blueprint.color_scheme,
            font_pair=blueprint.font_pair,
            animation_level=blueprint.animation_level,
            device_target=blueprint.device_target,
        )

        # Apply custom colors if provided
        if blueprint.custom_colors:
            if "primary" in blueprint.custom_colors:
                config.primary_color = blueprint.custom_colors["primary"]
            if "secondary" in blueprint.custom_colors:
                config.secondary_color = blueprint.custom_colors["secondary"]
            if "accent" in blueprint.custom_colors:
                config.accent_color = blueprint.custom_colors["accent"]

        return config

    def _build_site_meta(self, blueprint: Blueprint) -> SiteMeta:
        """Build site metadata from blueprint."""
        return SiteMeta(
            site_name=blueprint.business_name or f"{blueprint.industry.value.title()} Web Sitesi",
            tagline=None,
            primary_language="tr",
        )

    def _build_shared_sections(self, blueprint: Blueprint) -> Dict[str, Section]:
        """Build shared/reusable sections."""
        shared: Dict[str, Section] = {}

        # Navbar
        nav_template = self._template_registry.get_template(
            SectionType.NAVBAR,
            industry=blueprint.industry,
        )
        shared["navbar"] = Section(
            type=SectionType.NAVBAR,
            name="Navigasyon",
            order=0,
            config=SectionConfig(**nav_template.get("config", {})),
            style=SectionStyle(**nav_template.get("style", {})),
            content=nav_template.get("content", {}),
        )

        # Footer
        footer_template = self._template_registry.get_template(
            SectionType.FOOTER,
            industry=blueprint.industry,
        )
        shared["footer"] = Section(
            type=SectionType.FOOTER,
            name="Footer",
            order=999,
            config=SectionConfig(**footer_template.get("config", {})),
            style=SectionStyle(**footer_template.get("style", {})),
            content=footer_template.get("content", {}),
        )

        # Global CTA if defined
        if blueprint.primary_cta:
            cta_template = self._template_registry.get_template(
                SectionType.CTA,
                industry=blueprint.industry,
            )
            cta_content = cta_template.get("content", {})
            cta_content["primary_cta"] = blueprint.primary_cta
            cta_content["primary_link"] = blueprint.primary_cta_link
            if blueprint.secondary_cta:
                cta_content["secondary_cta"] = blueprint.secondary_cta

            shared["cta"] = Section(
                type=SectionType.CTA,
                name="CTA",
                order=500,
                config=SectionConfig(**cta_template.get("config", {})),
                style=SectionStyle(**cta_template.get("style", {})),
                content=cta_content,
            )

        return shared

    def _build_page(self, bp_page: BlueprintPage, blueprint: Blueprint, config: AssemblyConfig) -> Page:
        """Build a Page from a BlueprintPage."""
        sections: List[Section] = []

        for bp_section in bp_page.sections:
            section = self._build_section(bp_section, blueprint, config)
            if section:
                sections.append(section)

        # Sort sections by position
        sections.sort(key=lambda s: s.order)

        return Page(
            id=bp_page.page_id,
            name=bp_page.page_name,
            slug=bp_page.slug,
            is_homepage=bp_page.is_homepage,
            sections=sections,
            meta=PageMeta(
                title=bp_page.meta_title or bp_page.page_name,
                description=bp_page.meta_description,
            ),
            navigation=PageNavigation(
                label=bp_page.page_name,
                show_in_nav=not bp_page.is_homepage,
                nav_order=0 if bp_page.is_homepage else 1,
            ),
        )

    def _build_section(
        self,
        bp_section: BlueprintSection,
        blueprint: Blueprint,
        config: AssemblyConfig,
    ) -> Optional[Section]:
        """Build a Section from a BlueprintSection."""
        try:
            # Get template for this section type
            template = self._template_registry.get_template(
                bp_section.section_type,
                variant=bp_section.layout_variant,
                industry=blueprint.industry,
            )

            # Apply style overrides from blueprint
            style = SectionStyle(**template.get("style", {}))
            if bp_section.style_overrides:
                for key, value in bp_section.style_overrides.items():
                    setattr(style, key, value)

            # Apply config overrides from blueprint
            section_config = SectionConfig(**template.get("config", {}))
            if bp_section.config_overrides:
                for key, value in bp_section.config_overrides.items():
                    setattr(section_config, key, value)

            # Build content
            content = template.get("content", {})
            if bp_section.content_guidelines:
                content["_ai_guidelines"] = bp_section.content_guidelines

            return Section(
                id=f"sec_{bp_section.section_type.value}_{bp_section.position}",
                type=bp_section.section_type,
                name=bp_section.name or bp_section.section_type.value,
                order=bp_section.position,
                config=section_config,
                style=style,
                content=content,
            )

        except Exception as e:
            # Return a fallback section on error
            return Section(
                id=f"sec_{bp_section.section_type.value}_{bp_section.position}",
                type=bp_section.section_type,
                name=bp_section.name or bp_section.section_type.value,
                order=bp_section.position,
                content={
                    "title": bp_section.name or bp_section.section_type.value,
                    "_error": str(e),
                    "_guidelines": bp_section.content_guidelines,
                },
            )

    def _validate_site(self, site: Site) -> List[str]:
        """Validate an assembled site. Returns list of issues."""
        issues = []

        # Check for empty pages
        for page in site.pages:
            if not page.sections:
                issues.append(f"Page '{page.id}' has no sections")

        # Check for homepage
        if not any(p.is_homepage for p in site.pages):
            issues.append("No homepage defined")

        # Check for navbar/footer
        if "navbar" not in site.shared_sections:
            issues.append("No shared navbar section")
        if "footer" not in site.shared_sections:
            issues.append("No shared footer section")

        # Check section order consistency
        for page in site.pages:
            orders = [s.order for s in page.sections]
            if len(orders) != len(set(orders)):
                issues.append(f"Page '{page.id}' has duplicate section orders")

        # Check for empty content
        for page in site.pages:
            for section in page.sections:
                if not section.content:
                    issues.append(f"Section '{section.id}' on page '{page.id}' has empty content")

        return issues


# Singleton
_assembler_instance: Optional[SiteAssembler] = None


def get_site_assembler() -> SiteAssembler:
    """Get the singleton SiteAssembler instance."""
    global _assembler_instance
    if _assembler_instance is None:
        _assembler_instance = SiteAssembler()
    return _assembler_instance
