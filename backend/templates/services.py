"""
Services Section Templates
==========================
Pre-defined content for services, products, and features sections.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def _get_services_defaults(industry: IndustryType) -> List[Dict[str, Any]]:
    """Get industry-aware service items."""
    defaults = {
        IndustryType.RESTAURANT: [
            {
                "title": "Açık Büfe Kahvaltı",
                "description": "Her gün taze hazırlanan 50'den fazla çeşit ile zengin kahvaltı menümüz.",
                "icon": "coffee",
                "price": "150 TL",
            },
            {
                "title": "Özel Akşam Yemekleri",
                "description": "Şefimizin özel hazırladığı akşam menüsü, her akşam farklı bir lezzet.",
                "icon": "utensils",
                "price": "450 TL",
            },
            {
                "title": "Özel Organizasyon",
                "description": "Doğum günü, nişan, kutlama ve özel etkinlikler için profesyonel organizasyon.",
                "icon": "calendar",
                "price": "Talep üzerine",
            },
            {
                "title": "Paket Servis",
                "description": "Ev ve ofis adresinize sıcak ve taze yemek teslimatı.",
                "icon": "truck",
                "price": "Ücretsiz",
            },
        ],
        IndustryType.CAFE: [
            {
                "title": "Özel Kahve Demleme",
                "description": "V60, Chemex, Aeropress ve French Press ile kahve deneyimi.",
                "icon": "coffee",
            },
            {
                "title": "Taze Pastalar",
                "description": "Günlük yapılan taze ve lezzetli pastalar, tatlılar.",
                "icon": "cake",
            },
            {
                "title": "Kahve Eğitimleri",
                "description": "Kahve hazırlama ve demleme teknikleri hakkında eğitimler.",
                "icon": "graduation-cap",
            },
            {
                "title": "Toplantı ve Çalışma Alanı",
                "description": "WiFi ve priz erişimi olan rahat çalışma alanları.",
                "icon": "laptop",
            },
        ],
        IndustryType.HEALTHCARE: [
            {
                "title": "Genel Muayene",
                "description": "Uzman hekimlerimiz tarafından kapsamlı sağlık kontrolleri.",
                "icon": "stethoscope",
            },
            {
                "title": "Laboratuvar Hizmetleri",
                "description": "Modern laboratuvarımızda hızlı ve güvenilir test sonuçları.",
                "icon": "flask",
            },
            {
                "title": "Görüntüleme",
                "description": "Röntgen, ultrason, MR ve tomografi hizmetleri.",
                "icon": "x-ray",
            },
            {
                "title": "Evde Sağlık",
                "description": "Hareket kısıtlılığı olan hastalar için evde bakım hizmetleri.",
                "icon": "home-heart",
            },
        ],
        IndustryType.FITNESS: [
            {
                "title": "Kişisel Antrenman",
                "description": "Sertifikalı eğitmenlerle birebir antrenman programları.",
                "icon": "dumbbell",
                "price": "500 TL/ay",
            },
            {
                "title": "Grup Dersleri",
                "description": "Yoga, pilates, spinning ve zumba gibi grup dersleri.",
                "icon": "users",
                "price": "300 TL/ay",
            },
            {
                "title": "Beslenme Danışmanlığı",
                "description": "Uzman diyetisyenlerle kişiselleştirilmiş beslenme programları.",
                "icon": "apple-alt",
                "price": "400 TL/ay",
            },
            {
                "title": "Yüzme Havuzu",
                "description": "Olimpik standartlarda yarı olimpik yüzme havuzu.",
                "icon": "swimmer",
                "price": "Üyelik dahil",
            },
        ],
        IndustryType.SALON: [
            {
                "title": "Saç Kesim",
                "description": "Yüz şeklinize uygun modern ve klasik saç kesimleri.",
                "icon": "cut",
                "price": "200 TL'den",
            },
            {
                "title": "Saç Boyama",
                "description": "Premium boya markalarıyla profesyonel renk ve uygulama.",
                "icon": "palette",
                "price": "400 TL'den",
            },
            {
                "title": "Cilt Bakımı",
                "description": "Cilt tipinize özel bakım ve tedavi uygulamaları.",
                "icon": "spa",
                "price": "350 TL'den",
            },
            {
                "title": "Manikür & Pedikür",
                "description": "Profesyonel el ve ayak bakım hizmetleri.",
                "icon": "hand-sparkles",
                "price": "150 TL'den",
            },
        ],
        IndustryType.HOTEL: [
            {
                "title": "Standart Oda",
                "description": "Konforlu ve modern döşenmiş standart odalar.",
                "icon": "bed",
                "price": "800 TL/gece",
            },
            {
                "title": "Suit Oda",
                "description": "Geniş yaşam alanı ve özel olanaklarla suit odalar.",
                "icon": "hotel",
                "price": "1,500 TL/gece",
            },
            {
                "title": "SPA & Wellness",
                "description": "Masaj, sauna, hamam ve rahatlama hizmetleri.",
                "icon": "spa",
                "price": "250 TL'den",
            },
            {
                "title": "Toplantı Salonu",
                "description": "İş toplantıları ve etkinlikler için donanımlı salonlar.",
                "icon": "presentation",
                "price": "Talep üzerine",
            },
        ],
        IndustryType.TECHNOLOGY: [
            {
                "title": "Web Geliştirme",
                "description": "Modern ve ölçeklenebilir web uygulamaları geliştirme.",
                "icon": "code",
            },
            {
                "title": "Mobil Uygulama",
                "description": "iOS ve Android platformları için native ve cross-platform uygulamalar.",
                "icon": "mobile-alt",
            },
            {
                "title": "Bulut Çözümleri",
                "description": "AWS, Azure ve Google Cloud entegrasyon ve danışmanlık.",
                "icon": "cloud",
            },
            {
                "title": "UI/UX Tasarım",
                "description": "Kullanıcı odaklı modern arayüz ve deneyim tasarımı.",
                "icon": "paint-brush",
            },
        ],
        IndustryType.CONSTRUCTION: [
            {
                "title": "Konut İnşaatı",
                "description": "Modern ve kaliteli malzemelerle konut projeleri.",
                "icon": "home",
            },
            {
                "title": "Ticari Yapılar",
                "description": "Ofis, mağaza ve ticari kompleks inşaatları.",
                "icon": "building",
            },
            {
                "title": "Renovasyon",
                "description": "Mevcut yapıların modernizasyon ve tadilat hizmetleri.",
                "icon": "tools",
            },
            {
                "title": "Proje Yönetimi",
                "description": "İnşaat projelerinin planlamadan teslimata yönetimi.",
                "icon": "clipboard-list",
            },
        ],
    }
    return defaults.get(industry, [
        {
            "title": "Profesyonel Hizmet",
            "description": "Uzman ekibimizle en yüksek kalitede hizmet sunuyoruz.",
            "icon": "star",
        },
        {
            "title": "7/24 Destek",
            "description": "Her zaman yanınızda, kesintisiz destek hizmeti.",
            "icon": "headset",
        },
        {
            "title": "Garanti",
            "description": "Tüm hizmetlerimizde müşteri memnuniyeti garantisi.",
            "icon": "shield-alt",
        },
    ])


SERVICES_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_icon": True,
            "show_button": False,
            "item_count": 6,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "grid": {
        "config": {
            "layout_variant": "grid",
            "alignment": "center",
            "columns": 4,
            "show_title": True,
            "show_subtitle": True,
            "show_icon": True,
            "show_border": True,
            "show_shadow": True,
            "item_count": 8,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "cards": {
        "config": {
            "layout_variant": "cards",
            "alignment": "left",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_icon": True,
            "show_border": True,
            "show_shadow": True,
            "hover_effect": True,
            "item_count": 6,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "tabs": {
        "config": {
            "layout_variant": "tabs",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_icon": True,
            "item_count": 5,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
    },
}


def get_services_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete services section template."""
    template = SERVICES_TEMPLATES.get(variant, SERVICES_TEMPLATES["default"]).copy()

    title_defaults = {
        IndustryType.RESTAURANT: ("Menümüzden Seçmeler", "Lezzetli Yemekler"),
        IndustryType.CAFE: ("Neler Sunuyoruz?", "Kahve ve Dahası"),
        IndustryType.HEALTHCARE: ("Hizmetlerimiz", "Sağlık Çözümleri"),
        IndustryType.FITNESS: ("Programlarımız", "Fitness Seçenekleri"),
        IndustryType.SALON: ("Hizmetlerimiz", "Güzellik Hizmetleri"),
        IndustryType.HOTEL: ("Olanaklarımız", "Konforlu Hizmetler"),
        IndustryType.TECHNOLOGY: ("Hizmetlerimiz", "Teknoloji Çözümleri"),
        IndustryType.CONSTRUCTION: ("Hizmetlerimiz", "İnşaat Çözümleri"),
    }
    titles = title_defaults.get(industry, ("Hizmetlerimiz", "Neler Yapıyoruz?"))

    content = {
        "title": titles[0],
        "subtitle": titles[1],
        "description": "İhtiyaçlarınıza özel çözümler sunuyoruz.",
        "items": _get_services_defaults(industry),
        "show_pricing": False,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
