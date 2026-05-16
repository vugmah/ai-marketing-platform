"""
Example: Restaurant Website Generation
=======================================
Demonstrates the complete flow from business description to generated site.
"""

import sys
sys.path.insert(0, '/mnt/agents/output/app/backend')

from schemas.enums import IndustryType, BusinessSize, ColorScheme, FontPair
from schemas.blueprint import Blueprint
from schemas.site import Site

from ai_builder.blueprint_generator import BlueprintGenerator, GenerationContext
from ai_builder.site_assembler import SiteAssembler, AssemblyConfig
from ai_builder.validation import get_blueprint_validator
from ai_builder.content_generator import ContentGenerationRequest, get_content_generator

from cta.cta_engine import get_cta_engine
from layouts.industry_layouts import get_industry_layout


def main():
    """Generate a complete restaurant website."""

    # 1. Define business context
    context = GenerationContext(
        business_name="Lezzet Sofrası",
        business_description="2005 yılından beri İstanbul Beşiktaş'ta hizmet veren aile restoranı. Geleneksel Türk mutfağı ve modern sunumlar.",
        target_audience="Aileler, iş insanları, yemekseverler",
        tone_of_voice="professional",
        language="tr",
    )

    # 2. Generate blueprint
    print("=" * 60)
    print("1. BLUEPRINT GENERATION")
    print("=" * 60)

    generator = BlueprintGenerator()
    blueprint = generator.generate_blueprint(
        industry=IndustryType.RESTAURANT,
        context=context,
        color_scheme=ColorScheme.WARM_NEUTRAL,
        font_pair=FontPair.CLASSIC_SERIF,
    )

    print(f"Industry: {blueprint.industry.value}")
    print(f"Business: {blueprint.business_name}")
    print(f"Pages: {len(blueprint.pages)}")
    print(f"Total Sections: {blueprint.get_total_sections()}")
    print(f"Primary CTA: {blueprint.primary_cta}")
    print(f"Features: {len([v for v in blueprint.features.values() if v])} enabled")

    # Print page structure
    for page in blueprint.pages:
        print(f"\n  Page: {page.page_name} (/{page.slug})")
        for sec in page.sections:
            print(f"    [{sec.position}] {sec.section_type.value} - {sec.name}")

    # 3. Validate blueprint
    print("\n" + "=" * 60)
    print("2. BLUEPRINT VALIDATION")
    print("=" * 60)

    validator = get_blueprint_validator()
    result = validator.validate_blueprint(blueprint)
    print(f"Valid: {result.is_valid}")
    print(f"Issues: {result.total_issues}")
    for issue in result.issues:
        print(f"  [{issue.severity.value}] {issue.message}")
        if issue.suggestion:
            print(f"    -> {issue.suggestion}")

    # 4. Generate CTA strategy
    print("\n" + "=" * 60)
    print("3. CTA STRATEGY")
    print("=" * 60)

    cta_engine = get_cta_engine()
    cta_strategy = cta_engine.generate_strategy(
        page_id="home",
        industry=IndustryType.RESTAURANT,
        enable_ab_test=True,
    )
    print(f"Primary CTA: {cta_strategy.primary_label}")
    print(f"Placements: {[p.value for p in cta_strategy.primary_placements]}")
    print(f"Variants: {len(cta_strategy.primary_variants)}")
    for v in cta_strategy.primary_variants:
        print(f"  {v.variant_id}: '{v.label}' (style={v.style})")

    tips = cta_engine.get_optimization_tips(cta_strategy.strategy_id)
    print(f"\nOptimization Tips:")
    for tip in tips[:3]:
        print(f"  - {tip}")

    # 5. Assemble site
    print("\n" + "=" * 60)
    print("4. SITE ASSEMBLY")
    print("=" * 60)

    assembler = SiteAssembler()
    config = AssemblyConfig(
        generate_content=True,
        apply_templates=True,
        validate_output=True,
    )
    site = assembler.assemble(blueprint, config)

    print(f"Site ID: {site.id}")
    print(f"Pages: {len(site.pages)}")
    print(f"Shared Sections: {list(site.shared_sections.keys())}")

    for page in site.pages:
        print(f"\n  Page: {page.name} ({page.slug})")
        print(f"    Sections: {len(page.sections)}")
        for s in page.sections:
            content_preview = str(s.content)[:80] + "..." if len(str(s.content)) > 80 else str(s.content)
            print(f"      - {s.type.value}: {content_preview}")

    # 6. Generate content prompts
    print("\n" + "=" * 60)
    print("5. CONTENT GENERATION PROMPTS")
    print("=" * 60)

    content_gen = get_content_generator()
    prompt = content_gen.generate_prompt(ContentGenerationRequest(
        section_type=SectionType.HERO,
        industry=IndustryType.RESTAURANT,
        business_name="Lezzet Sofrası",
        business_description=context.business_description,
        max_length=200,
    ))
    print(f"Hero Content Prompt:\n{prompt[:500]}...")

    # 7. Get industry layout
    print("\n" + "=" * 60)
    print("6. INDUSTRY LAYOUT")
    print("=" * 60)

    layout = get_industry_layout(IndustryType.RESTAURANT)
    print(f"Layout: {layout['description']}")
    print(f"Pages: {len(layout['pages'])}")
    for p in layout['pages']:
        print(f"\n  Page: {p['page_name']} ({p['slug']})")
        print(f"    Sections: {len(p['sections'])}")

    # 8. Export to JSON
    print("\n" + "=" * 60)
    print("7. JSON EXPORT")
    print("=" * 60)

    blueprint_json = blueprint.to_json(indent=2)
    print(f"Blueprint JSON: {len(blueprint_json)} chars")

    site_dict = site.to_dict()
    print(f"Site dict keys: {list(site_dict.keys())}")

    print("\n" + "=" * 60)
    print("GENERATION COMPLETE!")
    print("=" * 60)

    return site, blueprint


if __name__ == "__main__":
    site, blueprint = main()
