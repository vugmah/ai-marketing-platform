"""
CTA (Call-to-Action) Section Templates
========================================
Pre-defined content and config for CTA sections.
"""

from typing import Dict, Any, Optional
from schemas.enums import IndustryType


def _get_cta_defaults(industry: IndustryType) -> Dict[str, Any]:
    """Get industry-aware CTA defaults."""
    defaults = {
        IndustryType.RESTAURANT: {
            "headline": "Lezzetli Bir Deneyim Sizi Bekliyor",
            "description": "Rezervasyon yapın, özel menümüzü keşfedin. Unutulmaz bir akşam yemeği için hemen yer ayırtın.",
            "primary_cta": "Rezervasyon Yap",
            "primary_link": "#reservation",
            "secondary_cta": "Menüyü Gör",
            "secondary_link": "#menu",
        },
        IndustryType.CAFE: {
            "headline": "Taze Kahve Sizi Bekliyor",
            "description": "Özenle seçilmiş çekirdeklerden hazırlanan kahvelerimizi deneyin. Her gün yeni bir lezzet keşfedin.",
            "primary_cta": "Menüyü Gör",
            "primary_link": "#menu",
            "secondary_cta": "Konumumuz",
            "secondary_link": "#location",
        },
        IndustryType.HEALTHCARE: {
            "headline": "Sağlığınız İçin Hemen Randevu Alın",
            "description": "Uzman doktorlarımız ve modern tesislerimizle size en iyi hizmeti sunuyoruz.",
            "primary_cta": "Randevu Al",
            "primary_link": "#appointment",
            "secondary_cta": "Hizmetlerimiz",
            "secondary_link": "#services",
        },
        IndustryType.FITNESS: {
            "headline": "Bugün Başlayın, Yarın Farkı Görün",
            "description": "Ücretsiz deneme dersine katılın. Sertifikalı eğitmenlerimiz ve modern ekipmanlarımızla hedeflerinize ulaşın.",
            "primary_cta": "Ücretsiz Deneme",
            "primary_link": "#trial",
            "secondary_cta": "Paketleri İncele",
            "secondary_link": "#pricing",
        },
        IndustryType.SALON: {
            "headline": "Yeni Bir Görünüm İçin Randevu Alın",
            "description": "Profesyonel ekibimiz ve premium ürünlerimizle tarzınızı yenileyin.",
            "primary_cta": "Randevu Al",
            "primary_link": "#appointment",
            "secondary_cta": "Hizmetlerimiz",
            "secondary_link": "#services",
        },
        IndustryType.HOTEL: {
            "headline": "Hayalinizdeki Tatil Bir Tık Uzağınızda",
            "description": "Özel fırsatlar ve indirimli fiyatlarla konaklamanızı şimdi planlayın.",
            "primary_cta": "Rezervasyon Yap",
            "primary_link": "#reservation",
            "secondary_cta": "Odaları İncele",
            "secondary_link": "#rooms",
        },
        IndustryType.TECHNOLOGY: {
            "headline": "Projenizi Hayata Geçirelim",
            "description": "Ücretsiz keşif toplantısı ile projenizi değerlendirelim. Size özel çözüm önerilerimizi sunalım.",
            "primary_cta": "Ücretsiz Danışma",
            "primary_link": "#consultation",
            "secondary_cta": "Projelerimiz",
            "secondary_link": "#portfolio",
        },
        IndustryType.CONSTRUCTION: {
            "headline": "Projenizi Ücretsiz Değerlendirelim",
            "description": "Hayalinizdeki yapıyı birlikte inşa edelim. Ücretsiz keşif ve fiyat teklifi alın.",
            "primary_cta": "Teklif Al",
            "primary_link": "#quote",
            "secondary_cta": "Projelerimiz",
            "secondary_link": "#projects",
        },
    }
    return defaults.get(industry, {
        "headline": "Hemen Başlayın",
        "description": "Size en iyi hizmeti sunmak için buradayız. Hemen iletişime geçin.",
        "primary_cta": "Bize Ulaşın",
        "primary_link": "#contact",
        "secondary_cta": "Daha Fazla Bilgi",
        "secondary_link": "#about",
    })


CTA_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "show_title": True,
            "show_description": True,
            "show_button": True,
            "full_width": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "text_color": "#ffffff",
            "max_width": "800px",
        },
    },
    "banner": {
        "config": {
            "layout_variant": "banner",
            "alignment": "center",
            "show_title": True,
            "show_button": True,
            "full_width": True,
        },
        "style": {
            "padding_top": "40px",
            "padding_bottom": "40px",
            "text_color": "#ffffff",
        },
    },
    "split": {
        "config": {
            "layout_variant": "split",
            "columns": 2,
            "alignment": "left",
            "show_title": True,
            "show_description": True,
            "show_button": True,
            "show_image": True,
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "floating": {
        "config": {
            "layout_variant": "floating",
            "alignment": "center",
            "show_title": False,
            "show_button": True,
        },
        "style": {
            "padding_top": "0",
            "padding_bottom": "0",
            "position": "fixed",
            "bottom": "20px",
            "right": "20px",
        },
    },
}


def get_cta_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete CTA section template."""
    template = CTA_TEMPLATES.get(variant, CTA_TEMPLATES["default"]).copy()
    defaults = _get_cta_defaults(industry)

    content = {
        "headline": defaults["headline"],
        "description": defaults["description"],
        "primary_cta": defaults["primary_cta"],
        "primary_link": defaults["primary_link"],
        "secondary_cta": defaults.get("secondary_cta"),
        "secondary_link": defaults.get("secondary_link"),
        "show_secondary": True,
        "urgency_text": None,
        "countdown_target": None,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
