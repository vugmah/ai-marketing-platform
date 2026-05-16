"""
About Section Templates
=======================
Pre-defined content and config for about section variants.
"""

from typing import Dict, Any, Optional
from schemas.enums import IndustryType


def _get_about_defaults(industry: IndustryType) -> Dict[str, Any]:
    """Get industry-aware about section defaults."""
    defaults = {
        IndustryType.RESTAURANT: {
            "title": "Hikayemiz",
            "subtitle": "2010'dan Beri Lezzetin Adresi",
            "description": "Taze ve kaliteli malzemelerle hazırlanan yemeklerimiz, misafirlerimize unutulmaz bir deneyim sunuyor. Yerel üreticilerden temin ettiğimiz organik malzemelerle, geleneksel tarifleri modern dokunuşlarla buluşturuyoruz.",
            "stats": [
                {"value": "14+", "label": "Yıllık Deneyim"},
                {"value": "50K+", "label": "Mutlu Misafir"},
                {"value": "30+", "label": "Özel Tarif"},
                {"value": "15", "label": "Ödül"},
            ],
            "image_caption": "Şefimiz mutfağımızda",
        },
        IndustryType.CAFE: {
            "title": "Kahve Aşkımız",
            "subtitle": "Her Fincanda Bir Hikaye",
            "description": "Dünyanın en iyi kahve bölgelerinden özenle seçtiğimiz çekirdekleri, usta kavurmacılarımızla mükemmelleştiriyoruz. Her fincan, yılların deneyimini ve tutkusunu taşıyor.",
            "stats": [
                {"value": "8+", "label": "Yıllık Deneyim"},
                {"value": "20K+", "label": "Sunulan Kahve"},
                {"value": "12", "label": "Farklı Köken"},
                {"value": "4.9", "label": "Değerlendirme"},
            ],
            "image_caption": "Kahve demleme sanatı",
        },
        IndustryType.HEALTHCARE: {
            "title": "Hakkımızda",
            "subtitle": "Sağlığınız İçin Buradayız",
            "description": "Modern tıp teknolojileri ve deneyimli uzman kadromuzla, hastalarımıza en iyi sağlık hizmetini sunmaya kararlıyız. Hasta memnuniyeti ve güvenliği bizim için her zaman önceliklidir.",
            "stats": [
                {"value": "25+", "label": "Uzman Doktor"},
                {"value": "50K+", "label": "Yıllık Hasta"},
                {"value": "15+", "label": "Yıllık Deneyim"},
                {"value": "20+", "label": "Branş"},
            ],
            "image_caption": "Modern kliniğimiz",
        },
        IndustryType.FITNESS: {
            "title": "Neden Biz?",
            "subtitle": "Fitness Yolculuğunuz Başlıyor",
            "description": "En son teknoloji ekipmanlar, sertifikalı eğitmenler ve motive edici ortamımızla fitness hedeflerinize ulaşmanız için yanınızdayız. Her seviyeye uygun programlar sunuyoruz.",
            "stats": [
                {"value": "5K+", "label": "Aktif Üye"},
                {"value": "30+", "label": "Eğitmen"},
                {"value": "100+", "label": "Haftalık Ders"},
                {"value": "15K m²", "label": "Spor Alanı"},
            ],
            "image_caption": "Spor salonumuz",
        },
        IndustryType.TECHNOLOGY: {
            "title": "Hakkımızda",
            "subtitle": "Yenilikçi Çözümler, Güvenilir Ortaklık",
            "description": "Müşterilerimizin dijital dönüşüm yolculuklarında güvenilir bir ortak olmak için çalışıyoruz. Uzman ekibimiz ve yenilikçi yaklaşımımızla projelerinizi hayata geçiriyoruz.",
            "stats": [
                {"value": "200+", "label": "Tamamlanan Proje"},
                {"value": "50+", "label": "Uzman Çalışan"},
                {"value": "10+", "label": "Yıllık Deneyim"},
                {"value": "98%", "label": "Müşteri Memnuniyeti"},
            ],
            "image_caption": "Ekibimiz",
        },
        IndustryType.SALON: {
            "title": "Hikayemiz",
            "subtitle": "Güzelliğin Adresi",
            "description": "Profesyonel ekibimiz ve premium ürünlerimizle, her müşterimizin kendini özel hissetmesini sağlıyoruz. Saç bakımından cilt tedavilerine, kompleks güzellik hizmetleri sunuyoruz.",
            "stats": [
                {"value": "10+", "label": "Yıllık Deneyim"},
                {"value": "15K+", "label": "Mutlu Müşteri"},
                {"value": "8", "label": "Uzman Stilist"},
                {"value": "50+", "label": "Hizmet"},
            ],
            "image_caption": "Salonumuz",
        },
        IndustryType.HOTEL: {
            "title": "Otelimiz",
            "subtitle": "Konfor ve Lüksün Buluştuğu Yer",
            "description": "Şehrin kalbinde, evinizin rahatlığını aratmayan bir konaklama deneyimi sunuyoruz. Özenle tasarlanmış odalarımız ve üstün hizmet anlayışımızla fark yaratıyoruz.",
            "stats": [
                {"value": "120", "label": "Oda"},
                {"value": "20+", "label": "Yıllık Deneyim"},
                {"value": "4.8", "label": "Otel Puanı"},
                {"value": "5★", "label": "Otel Sınıfı"},
            ],
            "image_caption": "Otelimizin görünümü",
        },
    }
    return defaults.get(industry, {
        "title": "Hakkımızda",
        "subtitle": "Biz Kimiz?",
        "description": "Yılların deneyimi ve uzman kadromuzla, müşterilerimize en kaliteli hizmeti sunmaya devam ediyoruz. Müşteri memnuniyeti bizim için her zaman en önemli önceliktir.",
        "stats": [
            {"value": "10+", "label": "Yıllık Deneyim"},
            {"value": "5K+", "label": "Mutlu Müşteri"},
            {"value": "50+", "label": "Proje"},
            {"value": "20+", "label": "Uzman Çalışan"},
        ],
        "image_caption": "Ekibimiz",
    })


ABOUT_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_image": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "split": {
        "config": {
            "layout_variant": "split",
            "columns": 2,
            "alignment": "left",
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_image": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
    "stats": {
        "config": {
            "layout_variant": "stats",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_description": True,
            "show_image": False,
            "show_icon": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "background_color": "#f8fafc",
        },
    },
    "team": {
        "config": {
            "layout_variant": "team",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "show_description": False,
            "show_image": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
    },
}


def get_about_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete about section template."""
    template = ABOUT_TEMPLATES.get(variant, ABOUT_TEMPLATES["default"]).copy()
    defaults = _get_about_defaults(industry)

    content = {
        "title": defaults["title"],
        "subtitle": defaults["subtitle"],
        "description": defaults["description"],
        "image_url": None,
        "image_caption": defaults.get("image_caption", ""),
        "stats": defaults.get("stats", []),
        "years_experience": None,
        "mission": None,
        "vision": None,
        "values": None,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
