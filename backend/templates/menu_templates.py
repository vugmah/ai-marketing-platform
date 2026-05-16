"""
Menu Section Templates
======================
Pre-defined content for restaurant/cafe menu sections and menu boards.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def _get_menu_defaults(industry: IndustryType) -> List[Dict[str, Any]]:
    """Get industry-aware menu categories and items."""
    restaurant_menu = [
        {
            "category": "Başlangıçlar",
            "items": [
                {"name": "Klasik Meze Tabagi", "description": "8 çeşit meze", "price": "180 TL", "badge": "Popüler"},
                {"name": "Karisik Kızartma", "description": "Kabak, patlican, biber", "price": "150 TL"},
                {"name": "Paçanga Böregi", "description": "Pastirma, kasar, biber", "price": "160 TL"},
                {"name": "Kalamar Tava", "description": "Taze kalamar, tartar sos", "price": "220 TL", "badge": "Chef Önerisi"},
            ],
        },
        {
            "category": "Ana Yemekler",
            "items": [
                {"name": "Izgara Köfte", "description": "Domates, biber, pilav ile", "price": "280 TL", "badge": "Popüler"},
                {"name": "Adana Kebap", "description": "Orfinarya lavaş, közlenmiş domates", "price": "320 TL"},
                {"name": "Karışık Izgara", "description": "Köfte, tavuk, kuzu şiş, Adana", "price": "450 TL", "badge": "2 Kişilik"},
                {"name": "Fırında Levrek", "description": "Taze baharatlar, mevsim sebzeleri", "price": "380 TL", "badge": "Chef Önerisi"},
            ],
        },
        {
            "category": "Tatlılar",
            "items": [
                {"name": "Künefe", "description": "Antep fıstıklı, kaymaklı", "price": "120 TL", "badge": "Popüler"},
                {"name": "Sütlaç", "description": "Fırın sütlaç, tarçın", "price": "80 TL"},
                {"name": "Baklava", "description": "4 adet, Antep fıstıklı", "price": "140 TL"},
            ],
        },
        {
            "category": "İçecekler",
            "items": [
                {"name": "Ev Yapımı Limonata", "description": "Taze sıkılmış", "price": "60 TL"},
                {"name": "Ayran", "description": "Yayık ayran", "price": "35 TL"},
                {"name": "Çay", "description": "Demli Türk çayı", "price": "15 TL"},
                {"name": "Türk Kahvesi", "description": "Geleneksel", "price": "40 TL"},
            ],
        },
    ]

    cafe_menu = [
        {
            "category": "Espresso Bazlı",
            "items": [
                {"name": "Espresso", "description": "Tek/Çift shot", "price": "45/55 TL"},
                {"name": "Americano", "description": "Sıcak veya soğuk", "price": "60 TL"},
                {"name": "Latte", "description": "Espresso, buharlı süt", "price": "70 TL", "badge": "Popüler"},
                {"name": "Cappuccino", "description": "Espresso, köpüklü süt", "price": "70 TL"},
                {"name": "Flat White", "description": "Çift ristretto, mikro köpük", "price": "75 TL", "badge": "Önerilen"},
            ],
        },
        {
            "category": "Filtre Kahve",
            "items": [
                {"name": "V60", "description": "Etiyopya, Yirgacheffe", "price": "85 TL", "badge": "Popüler"},
                {"name": "Chemex", "description": "Kolombiya, Huila", "price": "90 TL"},
                {"name": "French Press", "description": "Brezilya, Santos", "price": "80 TL"},
                {"name": "Cold Brew", "description": "12 saat demlenmiş", "price": "75 TL"},
            ],
        },
        {
            "category": "Tatlılar",
            "items": [
                {"name": "Cheesecake", "description": "Frambuaz soslu", "price": "85 TL"},
                {"name": "Tiramisu", "description": "Geleneksel İtalyan", "price": "90 TL", "badge": "Popüler"},
                {"name": "Brownie", "description": "Sıcak, vanilyalı dondurma ile", "price": "80 TL"},
                {"name": "Kruvasan", "description": "Tereyağlı, katmer", "price": "55 TL"},
            ],
        },
    ]

    if industry == IndustryType.RESTAURANT:
        return restaurant_menu
    elif industry == IndustryType.CAFE:
        return cafe_menu
    else:
        return restaurant_menu  # Default to restaurant menu


MENU_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_prices": True,
            "show_badges": True,
            "show_images": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
    },
    "board": {
        "config": {
            "layout_variant": "board",
            "alignment": "center",
            "show_title": True,
            "show_prices": True,
            "show_badges": True,
            "show_images": False,
            "columns": 2,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "60px",
            "padding_bottom": "60px",
            "max_width": "1200px",
            "background_color": "#1a1a1a",
            "text_color": "#ffffff",
        },
    },
    "tabs": {
        "config": {
            "layout_variant": "tabs",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_prices": True,
            "show_badges": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
    },
    "grid": {
        "config": {
            "layout_variant": "grid",
            "alignment": "left",
            "columns": 2,
            "show_title": True,
            "show_prices": True,
            "show_images": True,
            "show_badges": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
}


def get_menu_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete menu section template."""
    template = MENU_TEMPLATES.get(variant, MENU_TEMPLATES["default"]).copy()

    title_defaults = {
        IndustryType.RESTAURANT: ("Menümüz", "Lezzetli Seçenekler"),
        IndustryType.CAFE: ("Menümüz", "Kahve ve Lezzetler"),
    }
    titles = title_defaults.get(industry, ("Menü", "Ürünlerimiz"))

    content = {
        "title": titles[0],
        "subtitle": titles[1],
        "description": "En taze malzemelerle hazırlanan özel menümüz.",
        "categories": _get_menu_defaults(industry),
        "show_currency": True,
        "currency_symbol": "₺",
        "note": "Fiyatlara KDV dahildir. Tüm ürünler günlük taze malzemelerden hazırlanır.",
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
