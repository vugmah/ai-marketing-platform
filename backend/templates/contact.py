"""
Contact Section Templates
==========================
Pre-defined content for contact form, info, and map sections.
"""

from typing import Dict, Any, Optional
from schemas.enums import IndustryType


def _get_contact_defaults(industry: IndustryType) -> Dict[str, Any]:
    """Get industry-aware contact defaults."""
    base = {
        "title": "Bize Ulaşın",
        "subtitle": "Sorularınız mı var?",
        "description": "Size en kısa sürede dönüş yapacağız.",
        "address": "İstanbul, Türkiye",
        "phone": "+90 (212) 555 00 00",
        "email": "info@ornek.com",
        "working_hours": "Pazartesi - Cumartesi: 09:00 - 18:00",
        "form_title": "Mesaj Gönderin",
        "form_fields": [
            {"name": "name", "label": "Adınız", "type": "text", "required": True},
            {"name": "email", "label": "E-posta", "type": "email", "required": True},
            {"name": "phone", "label": "Telefon", "type": "tel", "required": False},
            {"name": "subject", "label": "Konu", "type": "text", "required": True},
            {"name": "message", "label": "Mesajınız", "type": "textarea", "required": True},
        ],
        "submit_button_text": "Gönder",
        "map_embed_url": None,
        "map_lat": 41.0082,
        "map_lng": 28.9784,
        "social_links": {},
    }

    industry_overrides = {
        IndustryType.RESTAURANT: {
            "description": "Rezervasyon ve özel etkinlikler için bize ulaşın.",
            "working_hours": "Her gün: 10:00 - 23:00",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "guest_count", "label": "Kişi Sayısı", "type": "number", "required": True},
                {"name": "date", "label": "Tarih", "type": "date", "required": True},
                {"name": "time", "label": "Saat", "type": "time", "required": True},
                {"name": "message", "label": "Özel İstekler", "type": "textarea", "required": False},
            ],
            "submit_button_text": "Rezervasyon İste",
        },
        IndustryType.CAFE: {
            "description": "Kahve siparişleri ve özel etkinlikler için ulaşın.",
            "working_hours": "Pazartesi - Cumartesi: 07:00 - 22:00 | Pazar: 08:00 - 20:00",
            "submit_button_text": "Gönder",
        },
        IndustryType.HEALTHCARE: {
            "description": "Randevu ve sağlık sorularınız için bize ulaşın.",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "department", "label": "Bölüm", "type": "select", "required": True,
                 "options": ["Genel Cerrahi", "Kardiyoloji", "Ortopedi", "Dahiliye", "Diğer"]},
                {"name": "date", "label": "Tercih Edilen Tarih", "type": "date", "required": False},
                {"name": "message", "label": "Şikayet/Not", "type": "textarea", "required": True},
            ],
            "submit_button_text": "Randevu İste",
        },
        IndustryType.FITNESS: {
            "description": "Üyelik ve program bilgileri için bize ulaşın.",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "goal", "label": "Fitness Hedefi", "type": "select", "required": True,
                 "options": ["Kilo Verme", "Kas Kazanma", "Genel Form", "Rehabilitasyon"]},
                {"name": "message", "label": "Mesaj", "type": "textarea", "required": False},
            ],
            "submit_button_text": "Bilgi İste",
        },
        IndustryType.HOTEL: {
            "description": "Rezervasyon ve konaklama bilgileri için ulaşın.",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "checkin", "label": "Giriş Tarihi", "type": "date", "required": True},
                {"name": "checkout", "label": "Çıkış Tarihi", "type": "date", "required": True},
                {"name": "guests", "label": "Kişi Sayısı", "type": "number", "required": True},
                {"name": "room_type", "label": "Oda Tipi", "type": "select", "required": True,
                 "options": ["Standart", "Deluxe", "Suit", "Aile Odası"]},
                {"name": "message", "label": "Özel İstekler", "type": "textarea", "required": False},
            ],
            "submit_button_text": "Rezervasyon İste",
        },
    }

    overrides = industry_overrides.get(industry, {})
    base.update(overrides)
    return base


CONTACT_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "columns": 2,
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "form_only": {
        "config": {
            "layout_variant": "form_only",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "700px",
        },
    },
    "info_only": {
        "config": {
            "layout_variant": "info_only",
            "alignment": "center",
            "columns": 3,
            "show_icon": True,
            "show_title": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
            "background_color": "#f8fafc",
        },
    },
    "with_map": {
        "config": {
            "layout_variant": "with_map",
            "alignment": "left",
            "columns": 2,
            "show_title": True,
            "show_subtitle": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "0",
            "padding_bottom": "0",
            "full_width": True,
        },
    },
}


def get_contact_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete contact section template."""
    template = CONTACT_TEMPLATES.get(variant, CONTACT_TEMPLATES["default"]).copy()
    defaults = _get_contact_defaults(industry)

    content = {k: v for k, v in defaults.items()}

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
