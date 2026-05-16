"""
Gallery Section Templates
==========================
Pre-defined content for image gallery, masonry, and carousel sections.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def _get_gallery_defaults(industry: IndustryType) -> List[Dict[str, str]]:
    """Get industry-aware gallery items."""
    defaults = {
        IndustryType.RESTAURANT: [
            {"title": "Özel Yemekler", "description": "Şefimizin özel hazırladığı lezzetler"},
            {"title": "Restoran İç Mekan", "description": "Şık ve konforlu ortamımız"},
            {"title": "Açık Mutfak", "description": "Yemeklerin hazırlandığı alan"},
            {"title": "Özel Davet", "description": "Özel etkinlik organizasyonları"},
            {"title": "Teras", "description": "Açık hava yemek alanı"},
            {"title": "Detaylar", "description": "Özenle hazırlanan her tabak"},
        ],
        IndustryType.CAFE: [
            {"title": "Latte Art", "description": "Baristalarımızın sanatı"},
            {"title": "Pastalarımız", "description": "Günlük taze pastalar"},
            {"title": "Mekan", "description": "Sıcak ve samimi atmosfer"},
            {"title": "Kahve Demleme", "description": "Özel demleme yöntemleri"},
            {"title": "Köşe", "description": "Rahat çalışma alanları"},
            {"title": "Kahve Çekirdekleri", "description": "Özenle seçilmiş çekirdekler"},
        ],
        IndustryType.SALON: [
            {"title": "Saç Kesim", "description": "Modern kesim stilleri"},
            {"title": "Renklendirme", "description": "Profesyonel boyama"},
            {"title": "Salonumuz", "description": "Lüks ve modern mekan"},
            {"title": "Cilt Bakımı", "description": "Yüz bakım uygulamaları"},
            {"title": "Makyaj", "description": "Özel gün makyajı"},
            {"title": "Damat Paketi", "description": "Gelin ve damat hazırlığı"},
        ],
        IndustryType.HOTEL: [
            {"title": "Lobi", "description": "Karşılama alanı"},
            {"title": "Standart Oda", "description": "Konforlu konaklama"},
            {"title": "Suit Oda", "description": "Lüks yaşam alanı"},
            {"title": "Havuz", "description": "Olimpik yüzme havuzu"},
            {"title": "SPA", "description": "Rahatlama merkezi"},
            {"title": "Restoran", "description": "Açık büfe restoran"},
        ],
        IndustryType.CONSTRUCTION: [
            {"title": "Konut Projesi", "description": "Tamamlanan konut projemiz"},
            {"title": "Ticari Bina", "description": "Modern ofis kompleksi"},
            {"title": "Renovasyon", "description": "Yenileme çalışması"},
            {"title": "İnşaat Süreci", "description": "Projeden sonuç alanına"},
            {"title": "İç Mekan", "description": "Tasarım ve uygulama"},
            {"title": "Teslimat", "description": "Zamanında teslim garantisi"},
        ],
    }
    return defaults.get(industry, [
        {"title": "Görsel 1", "description": "Açıklama"},
        {"title": "Görsel 2", "description": "Açıklama"},
        {"title": "Görsel 3", "description": "Açıklama"},
        {"title": "Görsel 4", "description": "Açıklama"},
        {"title": "Görsel 5", "description": "Açıklama"},
        {"title": "Görsel 6", "description": "Açıklama"},
    ])


def _get_gallery_titles(industry: IndustryType) -> tuple:
    """Get industry-aware gallery section titles."""
    titles = {
        IndustryType.RESTAURANT: ("Galeri", "Mekanımızdan Kareler"),
        IndustryType.CAFE: ("Galeri", "Karelerimiz"),
        IndustryType.SALON: ("Galeri", "Çalışmalarımız"),
        IndustryType.HOTEL: ("Galeri", "Otelimizden Görüntüler"),
        IndustryType.CONSTRUCTION: ("Projelerimiz", "İnşa Ettiklerimiz"),
        IndustryType.FITNESS: ("Galeri", "Spor Salonumuz"),
    }
    return titles.get(industry, ("Galeri", "Görsellerimiz"))


GALLERY_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "item_count": 6,
            "heading_tag": "h2",
            "clickable": True,
            "hover_effect": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "masonry": {
        "config": {
            "layout_variant": "masonry",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "item_count": 9,
            "heading_tag": "h2",
            "clickable": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "carousel": {
        "config": {
            "layout_variant": "carousel",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "item_count": 8,
            "heading_tag": "h2",
            "carousel_enabled": True,
            "carousel_autoplay": True,
            "carousel_interval": 4000,
        },
        "style": {
            "padding_top": "60px",
            "padding_bottom": "60px",
            "max_width": "1200px",
        },
    },
    "grid": {
        "config": {
            "layout_variant": "grid",
            "alignment": "center",
            "columns": 4,
            "show_title": True,
            "item_count": 8,
            "heading_tag": "h2",
            "clickable": True,
            "hover_effect": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
}


def get_gallery_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete gallery section template."""
    template = GALLERY_TEMPLATES.get(variant, GALLERY_TEMPLATES["default"]).copy()
    titles = _get_gallery_titles(industry)
    items = _get_gallery_defaults(industry)

    content = {
        "title": titles[0],
        "subtitle": titles[1],
        "description": "Çalışmalarımızdan örnekler.",
        "items": items,
        "show_lightbox": True,
        "show_captions": True,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
