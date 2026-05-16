"""
Footer Section Templates
==========================
Pre-defined content and config for footer sections.
"""

from typing import Dict, Any, Optional
from schemas.enums import IndustryType


def _get_footer_defaults(industry: IndustryType) -> Dict[str, Any]:
    """Get industry-aware footer defaults."""
    base = {
        "logo_text": "Şirket Adı",
        "tagline": "Kaliteli hizmet, güvenilir çözümler.",
        "columns": [
            {
                "title": "Hızlı Linkler",
                "links": [
                    {"label": "Ana Sayfa", "url": "/"},
                    {"label": "Hakkımızda", "url": "/about"},
                    {"label": "Hizmetler", "url": "/services"},
                    {"label": "İletişim", "url": "/contact"},
                ],
            },
            {
                "title": "Hizmetler",
                "links": [
                    {"label": "Hizmet 1", "url": "#"},
                    {"label": "Hizmet 2", "url": "#"},
                    {"label": "Hizmet 3", "url": "#"},
                    {"label": "Hizmet 4", "url": "#"},
                ],
            },
            {
                "title": "İletişim",
                "contact_info": {
                    "address": "İstanbul, Türkiye",
                    "phone": "+90 (212) 555 00 00",
                    "email": "info@ornek.com",
                },
            },
        ],
        "social_links": {
            "facebook": "#",
            "instagram": "#",
            "twitter": "#",
            "youtube": "#",
        },
        "bottom_bar": {
            "copyright": "© 2024 Tüm Hakları Saklıdır.",
            "links": [
                {"label": "Gizlilik Politikası", "url": "/privacy"},
                {"label": "Kullanım Koşulları", "url": "/terms"},
            ],
        },
        "newsletter": {
            "enabled": True,
            "title": "Bültenimize Abone Olun",
            "description": "Kampanya ve duyurulardan haberdar olun.",
            "placeholder": "E-posta adresiniz",
            "button_text": "Abone Ol",
        },
    }

    industry_overrides = {
        IndustryType.RESTAURANT: {
            "tagline": "Lezzetli yemekler, unutulmaz anlar.",
            "columns": [
                {
                    "title": "Restoran",
                    "links": [
                        {"label": "Ana Sayfa", "url": "/"},
                        {"label": "Menü", "url": "/menu"},
                        {"label": "Hakkımızda", "url": "/about"},
                        {"label": "Rezervasyon", "url": "/reservation"},
                    ],
                },
                {
                    "title": "Menü",
                    "links": [
                        {"label": "Başlangıçlar", "url": "/menu#starters"},
                        {"label": "Ana Yemekler", "url": "/menu#mains"},
                        {"label": "Tatlılar", "url": "/menu#desserts"},
                        {"label": "İçecekler", "url": "/menu#drinks"},
                    ],
                },
                {
                    "title": "İletişim",
                    "contact_info": {
                        "address": "Beşiktaş, İstanbul",
                        "phone": "+90 (212) 555 00 00",
                        "email": "info@restoran.com",
                        "working_hours": "Her gün: 10:00 - 23:00",
                    },
                },
            ],
            "social_links": {
                "facebook": "#",
                "instagram": "#",
                "tripadvisor": "#",
            },
        },
        IndustryType.CAFE: {
            "tagline": "Her fincanda bir hikaye.",
            "columns": [
                {
                    "title": "Kafe",
                    "links": [
                        {"label": "Ana Sayfa", "url": "/"},
                        {"label": "Menü", "url": "/menu"},
                        {"label": "Hakkımızda", "url": "/about"},
                        {"label": "İletişim", "url": "/contact"},
                    ],
                },
                {
                    "title": "Kahve",
                    "links": [
                        {"label": "Espresso Bazlı", "url": "/menu#espresso"},
                        {"label": "Filtre Kahve", "url": "/menu#filter"},
                        {"label": "Tatlılar", "url": "/menu#desserts"},
                    ],
                },
                {
                    "title": "İletişim",
                    "contact_info": {
                        "address": "Kadıköy, İstanbul",
                        "phone": "+90 (216) 555 00 00",
                        "email": "info@kafe.com",
                        "working_hours": "Pzt-Cmt: 07:00 - 22:00 | Paz: 08:00 - 20:00",
                    },
                },
            ],
        },
        IndustryType.FITNESS: {
            "tagline": "Daha sağlıklı bir yaşam için.",
            "columns": [
                {
                    "title": "Spor Salonu",
                    "links": [
                        {"label": "Ana Sayfa", "url": "/"},
                        {"label": "Programlar", "url": "/programs"},
                        {"label": "Eğitmenler", "url": "/trainers"},
                        {"label": "Fiyatlar", "url": "/pricing"},
                    ],
                },
                {
                    "title": "Programlar",
                    "links": [
                        {"label": "Kişisel Antrenman", "url": "#"},
                        {"label": "Grup Dersleri", "url": "#"},
                        {"label": "Yüzme", "url": "#"},
                        {"label": "Pilates", "url": "#"},
                    ],
                },
                {
                    "title": "İletişim",
                    "contact_info": {
                        "address": "Levent, İstanbul",
                        "phone": "+90 (212) 555 00 00",
                        "email": "info@fitness.com",
                        "working_hours": "Pzt-Paz: 06:00 - 23:00",
                    },
                },
            ],
        },
        IndustryType.HOTEL: {
            "tagline": "Konforun yeni adresi.",
            "columns": [
                {
                    "title": "Otel",
                    "links": [
                        {"label": "Ana Sayfa", "url": "/"},
                        {"label": "Odalar", "url": "/rooms"},
                        {"label": "SPA", "url": "/spa"},
                        {"label": "Rezervasyon", "url": "/reservation"},
                    ],
                },
                {
                    "title": "Oda Tipleri",
                    "links": [
                        {"label": "Standart Oda", "url": "#"},
                        {"label": "Deluxe Oda", "url": "#"},
                        {"label": "Suit Oda", "url": "#"},
                        {"label": "Aile Odası", "url": "#"},
                    ],
                },
                {
                    "title": "İletişim",
                    "contact_info": {
                        "address": "Taksim, İstanbul",
                        "phone": "+90 (212) 555 00 00",
                        "email": "info@otel.com",
                        "reservation": "+90 (212) 555 00 01",
                    },
                },
            ],
        },
    }

    overrides = industry_overrides.get(industry, {})
    base.update(overrides)
    return base


FOOTER_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "columns": 4,
            "show_logo": True,
            "show_social": True,
            "show_newsletter": True,
            "show_bottom_bar": True,
            "heading_tag": "h3",
        },
        "style": {
            "padding_top": "60px",
            "padding_bottom": "30px",
            "background_color": "#1e293b",
            "text_color": "#94a3b8",
            "full_width": True,
        },
    },
    "minimal": {
        "config": {
            "layout_variant": "minimal",
            "show_logo": True,
            "show_social": True,
            "show_newsletter": False,
            "show_bottom_bar": True,
        },
        "style": {
            "padding_top": "30px",
            "padding_bottom": "30px",
            "background_color": "#0f172a",
            "text_color": "#94a3b8",
            "full_width": True,
        },
    },
    "mega": {
        "config": {
            "layout_variant": "mega",
            "columns": 5,
            "show_logo": True,
            "show_social": True,
            "show_newsletter": True,
            "show_bottom_bar": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "40px",
            "background_color": "#1e293b",
            "text_color": "#94a3b8",
            "full_width": True,
        },
    },
}


def get_footer_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete footer section template."""
    template = FOOTER_TEMPLATES.get(variant, FOOTER_TEMPLATES["default"]).copy()
    defaults = _get_footer_defaults(industry)

    if custom_content:
        defaults.update(custom_content)

    template["content"] = defaults
    return template
