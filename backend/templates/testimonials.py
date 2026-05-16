"""
Testimonials Section Templates
===============================
Pre-defined content for customer testimonials and reviews.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def _get_testimonial_defaults(industry: IndustryType) -> List[Dict[str, Any]]:
    """Get industry-aware testimonial items."""
    base = [
        {
            "name": "Ahmet Yılmaz",
            "role": "Müşteri",
            "rating": 5,
            "text": "Harika bir deneyimdi! Kesinlikle tekrar geleceğim. Personel çok ilgili ve profesyoneldi.",
            "avatar": None,
            "verified": True,
        },
        {
            "name": "Selin Kaya",
            "role": "Müşteri",
            "rating": 5,
            "text": "Kalite ve hizmet mükemmel. Beklentilerimin çok üzerinde bir deneyim yaşadım. Herkese tavsiye ederim.",
            "avatar": None,
            "verified": True,
        },
        {
            "name": "Mehmet Demir",
            "role": "Müşteri",
            "rating": 4,
            "text": "Çok memnun kaldım. Fiyat-performans açısından çok iyi. Personel güleryüzlü ve yardımcı.",
            "avatar": None,
            "verified": True,
        },
    ]

    industry_specific = {
        IndustryType.RESTAURANT: [
            {
                "name": "Ayşe Yılmaz",
                "role": "Gurme Blogger",
                "rating": 5,
                "text": "Sunum ve lezzet muhteşem! Özellikle fırında levreklerini kesinlikle denemelisiniz. Servis çok hızlı ve personel oldukça ilgili.",
                "verified": True,
            },
            {
                "name": "Can Kaya",
                "role": "Yerel Müşteri",
                "rating": 5,
                "text": "Ailecek geldiğimiz favori mekanımız. Açık büfe kahvaltısı çok zengin, her şey taze. Özellikle manzarası eşsiz.",
                "verified": True,
            },
            {
                "name": "Elif Şahin",
                "role": "İş İnsanı",
                "rating": 5,
                "text": "İş yemekleri için mükemmel bir adres. Özel salonları sayesinde toplantı sonrası akşam yemeği çok keyifli geçti.",
                "verified": True,
            },
        ],
        IndustryType.CAFE: [
            {
                "name": "Burak Tekin",
                "role": "Öğrenci",
                "rating": 5,
                "text": "Ders çalışmak için en ideal mekan. WiFi hızlı, priz var, kahve muazzam! Flat white'larını çok seviyorum.",
                "verified": True,
            },
            {
                "name": "Zeynep Aydın",
                "role": "Freelancer",
                "rating": 5,
                "text": "Her sabah geldiğim kahvem. Baristalar gerçekten işini biliyor. Pastalar da günlük taze, tiramisuya bayılıyorum.",
                "verified": True,
            },
            {
                "name": "Deniz Özdemir",
                "role": "Tasarımcı",
                "rating": 4,
                "text": "Ambiyans çok güzel, kahve kaliteli. Hafta sonları biraz kalabalık olabiliyor ama yine de favorim.",
                "verified": True,
            },
        ],
        IndustryType.HEALTHCARE: [
            {
                "name": "Fatma Kılıç",
                "role": "Hasta",
                "rating": 5,
                "text": "Dr. Ahmet Bey'e teşekkürler. Çok ilgili ve detaylı bir muayene geçirdim. Artık aile hekimimiz.",
                "verified": True,
            },
            {
                "name": "Hakan Demirtaş",
                "role": "Hasta",
                "rating": 5,
                "text": "Modern cihazlar, temiz ortam ve güler yüzlü personel. Randevu sistemleri çok pratik, bekleme süresi çok kısa.",
                "verified": True,
            },
            {
                "name": "Seda Yıldız",
                "role": "Anne",
                "rating": 5,
                "text": "Çocuk doktoru çok sabırlı ve tatlı. Kızım artık doktordan korkmuyor. Çok teşekkür ederiz.",
                "verified": True,
            },
        ],
        IndustryType.FITNESS: [
            {
                "name": "Kerem Aksoy",
                "role": "Üye - 2 Yıl",
                "rating": 5,
                "text": "2 yılda 20 kilo verdim! Eğitmenlerim sayesinde hedeflerime ulaştım. Ekipmanlar sürekli yenileniyor.",
                "verified": True,
            },
            {
                "name": "Leyla Çelik",
                "role": "Üye - 6 Ay",
                "rating": 5,
                "text": "Grup dersleri çok eğlenceli! Zumba ve pilates derslerine bayılıyorum. Motive edici bir ortam.",
                "verified": True,
            },
            {
                "name": "Oğuz Kurt",
                "role": "Üye - 1 Yıl",
                "rating": 4,
                "text": "Beslenme danışmanlığı hizmeti çok faydalı oldu. Spor salonu geniş ve temiz. Tavsiye ederim.",
                "verified": True,
            },
        ],
    }

    return industry_specific.get(industry, base)


TESTIMONIALS_TEMPLATES = {
    "default": {
        "config": {
            "layout_variant": "default",
            "alignment": "center",
            "columns": 3,
            "show_title": True,
            "show_subtitle": True,
            "show_rating": True,
            "show_avatar": True,
            "item_count": 3,
            "heading_tag": "h2",
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
            "show_rating": True,
            "show_avatar": True,
            "item_count": 6,
            "heading_tag": "h2",
            "carousel_enabled": True,
            "carousel_autoplay": True,
            "carousel_interval": 6000,
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
            "show_rating": True,
            "show_avatar": True,
            "show_border": True,
            "show_shadow": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
    },
}


def get_testimonials_template(
    variant: str = "default",
    industry: IndustryType = IndustryType.GENERIC,
    custom_content: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get a complete testimonials section template."""
    template = TESTIMONIALS_TEMPLATES.get(variant, TESTIMONIALS_TEMPLATES["default"]).copy()

    title_defaults = {
        IndustryType.RESTAURANT: ("Misafirlerimiz Ne Diyor?", "Yorumlar"),
        IndustryType.CAFE: ("Kahve Severlerden", "Değerlendirmeler"),
        IndustryType.HEALTHCARE: ("Hasta Yorumları", "Deneyimler"),
        IndustryType.FITNESS: ("Başarı Hikayeleri", "Üyelerimizden"),
        IndustryType.SALON: ("Müşteri Yorumları", "Güzellik Deneyimleri"),
        IndustryType.HOTEL: ("Misafir Yorumları", "Konaklama Deneyimleri"),
    }
    titles = title_defaults.get(industry, ("Müşteri Yorumları", "Bizi Değerlendirin"))

    content = {
        "title": titles[0],
        "subtitle": titles[1],
        "description": "Müşterilerimizin bizimle ilgili deneyimleri.",
        "testimonials": _get_testimonial_defaults(industry),
        "average_rating": 4.8,
        "total_reviews": 150,
        "show_stars": True,
        "show_verified_badge": True,
    }

    if custom_content:
        content.update(custom_content)

    template["content"] = content
    return template
