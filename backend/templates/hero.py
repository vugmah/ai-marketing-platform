"""
Hero Section Templates
======================
Pre-defined content and config for hero section variants.
"""

from typing import Dict, Any, Optional
from schemas.enums import IndustryType


def _get_hero_defaults(industry: IndustryType) -> Dict[str, Any]:
    """Get industry-aware hero defaults."""
    defaults = {
        IndustryType.RESTAURANT: {
            "headline": "Lezzetin Adresi",
            "subheadline": "Taze malzemeler, unutulmaz tatlar. Her yemek bir sanat eseri.",
            "primary_cta": "Menüyü Keşfet",
            "secondary_cta": "Rezervasyon Yap",
            "background_style": "image",
        },
        IndustryType.CAFE: {
            "headline": "Gününüze Lezzet Katın",
            "subheadline": "Özenle seçilmiş çekirdekler, ustalıkla hazırlanan kahveler.",
            "primary_cta": "Menüyü Gör",
            "secondary_cta": "Bizi Ziyaret Edin",
            "background_style": "image",
        },
        IndustryType.RETAIL: {
            "headline": "Stilinizi Keşfedin",
            "subheadline": "Binlerce ürün, en uygun fiyatlarla kapınızda.",
            "primary_cta": "Alışverişe Başla",
            "secondary_cta": "Kampanyalar",
            "background_style": "gradient",
        },
        IndustryType.HEALTHCARE: {
            "headline": "Sağlığınız Bizim Önceliğimiz",
            "subheadline": "Uzman kadromuz ve modern teknolojimizle yanınızdayız.",
            "primary_cta": "Randevu Al",
            "secondary_cta": "Hizmetlerimiz",
            "background_style": "gradient",
        },
        IndustryType.FITNESS: {
            "headline": "Daha Güçlü Bir Sen",
            "subheadline": "Profesyonel ekipmanlar, uzman eğitmenler, sınırsız motivasyon.",
            "primary_cta": "Ücretsiz Deneme",
            "secondary_cta": "Paketleri İncele",
            "background_style": "video",
        },
        IndustryType.SALON: {
            "headline": "Tarzınızı Yenileyin",
            "subheadline": "Profesyonel ekibimizle yeni bir görünüme kavuşun.",
            "primary_cta": "Randevu Al",
            "secondary_cta": "Hizmetler",
            "background_style": "image",
        },
        IndustryType.HOTEL: {
            "headline": "Konforun Yeni Adı",
            "subheadline": "Unutulmaz bir konaklama deneyimi sizi bekliyor.",
            "primary_cta": "Rezervasyon Yap",
            "secondary_cta": "Odaları İncele",
            "background_style": "slider",
        },
        IndustryType.TECHNOLOGY: {
            "headline": "Geleceği İnşa Ediyoruz",
            "subheadline": "Yenilikçi çözümlerle işinizi bir üst seviyeye taşıyoruz.",
            "primary_cta": "Demo İste",
            "secondary_cta": "Daha Fazla Bilgi",
            "background_style": "gradient",
        },
        IndustryType.CONSULTING: {
            "headline": "Başarıya Giden Yol",
            "subheadline": "Uzman danışmanlığıyla işinizi büyütün.",
            "primary_cta": "Ücretsiz Danışma",
            "secondary_cta": "Referanslar",
            "background_style": "gradient",
        },
        IndustryType.CONSTRUCTION: {
            "headline": "Hayallerinizi İnşa Ediyoruz",
            "subheadline": "Kaliteli malzeme, güvenli inşaat, zamanında teslimat.",
            "primary_cta": "Proje Başlat",
            "secondary_cta": "Portfolyo",
            "background_style": "image",
        },
    }
    return defaults.get(industry, {
        "headline": "Hoş Geldiniz",
        "subheadline": "Kaliteli hizmet ve uzman kadromuzla yanınızdayız.",
        "primary_cta": "Daha Fazla Bilgi",
        "secondary_cta": "Bize Ulaşın",
        "background_style": "gradient",
    })


HERO_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_button": True,
            "heading_tag": "h1",
            "full_width": True,
        },
        "style": {
            "padding_top": "120px",
            "padding_bottom": "120px",
            "text_color": "#ffffff",
            "max_width": "800px",
        },
    },
    "split": {
        "config": {
            "layout_variant": "split",
            "columns": 2,
            "alignment": "left",
            "show_title": True,
            "show_subtitle": True,
            "show_button": True,
            "show_image": True,
            "heading_tag": "h1",
        },
        "style": {
            "padding_top": "100px",
            "padding_bottom": "100px",
            "max_width": "1200px",
        },
    },
    "minimal": {
        "config": {
            "layout_variant": "minimal",
            "alignment": "center",
            "show_subtitle": False,
            "show_button": False,
            "heading_tag": "h1",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
        },
    },
    "video": {
        "config": {
            "layout_variant": "video",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_button": True,
            "heading_tag": "h1",
            "full_width": True,
        },
        "style": {
            "padding_top": "150px",
            "padding_bottom": "150px",
            "text_color": "#ffffff",
        },
    },
    "slider": {
        "config": {
            "layout_variant": "slider",
            "alignment": "center",
            "carousel_enabled": True,
            "carousel_autoplay": True,
            "carousel_interval": 6000,
            "heading_tag": "h1",
            "full_width": True,
            "item_count": 3,
        },
        "style": {
            "padding_top": "120px",
            "padding_bottom": "120px",
            "text_color": "#ffffff",
        },
    },
}


def get_hero_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get a complete hero section template.

    Args:
        variant: Template variant name
        industry: Business industry for contextual defaults
        custom_content: Override content fields

    Returns:
        Dict with config, style, and content keys
    """
    template = HERO_TEMPLATES.get(variant, HERO_TEMPLATES["default"]).copy()
    defaults = _get_hero_defaults(industry)

    content = {
        "headline": defaults["headline"],
        "subheadline": defaults["subheadline"],
        "primary_cta": defaults["primary_cta"],
        "primary_cta_link": "#cta",
        "secondary_cta": defaults["secondary_cta"],
        "secondary_cta_link": "#contact",
        "background_image": None,
        "background_video": None,
        "overlay_opacity": 0.4,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
