"""
Pricing Section Templates
==========================
Pre-defined content for pricing tables and comparison sections.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def _get_pricing_defaults(industry: IndustryType) -> List[Dict[str, Any]]:
    """Get industry-aware pricing plans."""
    fitness_plans = [
        {
            "name": "Başlangıç",
            "price": "299",
            "period": "ay",
            "currency": "₺",
            "description": "Fitness yolculuğunuza başlayın",
            "features": [
                "Spor salonu kullanımı",
                "Kilitli dolap",
                "Duş olanakları",
                "Temel ekipmanlar",
            ],
            "not_included": [
                "Grup dersleri",
                "Kişisel antrenman",
                "Beslenme danışmanlığı",
                "SPA kullanımı",
            ],
            "cta_text": "Başla",
            "popular": False,
        },
        {
            "name": "Premium",
            "price": "499",
            "period": "ay",
            "currency": "₺",
            "description": "En popüler seçim",
            "features": [
                "Spor salonu kullanımı",
                "Kilitli dolap",
                "Duş olanakları",
                "Tüm ekipmanlar",
                "Sınırsız grup dersleri",
                "1 Aylık kişisel antrenman",
            ],
            "not_included": [
                "Beslenme danışmanlığı",
                "SPA kullanımı",
            ],
            "cta_text": "Premium'a Geç",
            "popular": True,
        },
        {
            "name": "Platinum",
            "price": "799",
            "period": "ay",
            "currency": "₺",
            "description": "Tüm olanaklar, limitsiz",
            "features": [
                "Spor salonu kullanımı",
                "Kilitli dolap",
                "Duş olanakları",
                "Tüm ekipmanlar",
                "Sınırsız grup dersleri",
                "Haftalık kişisel antrenman",
                "Aylık beslenme danışmanlığı",
                "Sınırsız SPA kullanımı",
            ],
            "not_included": [],
            "cta_text": "Platinum'a Geç",
            "popular": False,
        },
    ]

    salon_plans = [
        {
            "name": "Temel Bakım",
            "price": "199",
            "period": "seans",
            "currency": "₺",
            "description": "Temel güzellik bakımı",
            "features": [
                "Saç kesim",
                "Fön",
                "Kaş düzenleme",
            ],
            "cta_text": "Randevu Al",
            "popular": False,
        },
        {
            "name": "Komple Bakım",
            "price": "449",
            "period": "paket",
            "currency": "₺",
            "description": "Tüm ihtiyaçlarınız için",
            "features": [
                "Saç kesim ve boyama",
                "Manikür & Pedikür",
                "Yüz bakımı",
                "Kaş & Kirpik",
            ],
            "cta_text": "Randevu Al",
            "popular": True,
        },
        {
            "name": "Özel Gün",
            "price": "899",
            "period": "paket",
            "currency": "₺",
            "description": "Düğün ve özel günler",
            "features": [
                "Gelin saçı ve makyajı",
                "Manikür & Pedikür",
                "Cilt bakımı",
                "Prova seansı",
            ],
            "cta_text": "Randevu Al",
            "popular": False,
        },
    ]

    tech_plans = [
        {
            "name": "Başlangıç",
            "price": "2,999",
            "period": "proje",
            "currency": "₺",
            "description": "Küçük projeler için",
            "features": [
                "5 sayfaya kadar",
                "Mobil uyumlu tasarım",
                "Temel SEO",
                "İletişim formu",
                "1 ay destek",
            ],
            "cta_text": "Başla",
            "popular": False,
        },
        {
            "name": "Profesyonel",
            "price": "7,999",
            "period": "proje",
            "currency": "₺",
            "description": "Orta ölçekli projeler",
            "features": [
                "Sınırsız sayfa",
                "Özel tasarım",
                "Gelişmiş SEO",
                "CMS entegrasyonu",
                "Çok dilli destek",
                "6 ay destek",
            ],
            "cta_text": "Başla",
            "popular": True,
        },
        {
            "name": "Kurumsal",
            "price": "Özel",
            "period": "",
            "currency": "",
            "description": "Büyük ölçekli çözümler",
            "features": [
                "Her şey dahil",
                "Özel geliştirme",
                "API entegrasyonları",
                "7/24 destek",
                "Özel eğitim",
                "1 yıl garanti",
            ],
            "cta_text": "Teklif Al",
            "popular": False,
        },
    ]

    defaults = {
        IndustryType.FITNESS: fitness_plans,
        IndustryType.SALON: salon_plans,
        IndustryType.TECHNOLOGY: tech_plans,
    }
    return defaults.get(industry, fitness_plans)


PRICING_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "item_count": 3,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "tables": {
        "config": {
            "layout_variant": "tables",
            "alignment": "center",
            "show_title": True,
            "show_description": True,
            "show_checkmarks": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
    },
    "toggle": {
        "config": {
            "layout_variant": "toggle",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "item_count": 3,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
}


def get_pricing_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete pricing section template."""
    template = PRICING_TEMPLATES.get(variant, PRICING_TEMPLATES["default"]).copy()

    title_defaults = {
        IndustryType.FITNESS: ("Üyelik Paketleri", "Size Uygun Planı Seçin"),
        IndustryType.SALON: ("Hizmet Paketleri", "Bakım Planları"),
        IndustryType.TECHNOLOGY: ("Fiyatlandırma", "Size Uygun Paketi Seçin"),
        IndustryType.HOTEL: ("Oda Fiyatları", "Konaklama Seçenekleri"),
        IndustryType.HEALTHCARE: ("Paketler", "Sağlık Planları"),
    }
    titles = title_defaults.get(industry, ("Fiyatlandırma", "Paketlerimiz"))

    content = {
        "title": titles[0],
        "subtitle": titles[1],
        "description": "İhtiyaçlarınıza en uygun paketi seçin.",
        "plans": _get_pricing_defaults(industry),
        "show_toggle": False,
        "toggle_labels": {"monthly": "Aylık", "yearly": "Yıllık"},
        "note": "Tüm fiyatlara KDV dahildir. İptal politikası için bize ulaşın.",
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
