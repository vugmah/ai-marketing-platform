"""
CTA Recommendations Module
===========================
Provides industry-specific CTA recommendations and conversion optimization tips.
"""

from typing import Dict, Any, List
from schemas.enums import IndustryType


def get_cta_recommendations(industry: IndustryType) -> List[Dict[str, Any]]:
    """
    Get CTA recommendations for a specific industry.
    Returns a list of actionable CTA suggestions.
    """
    recommendations = {
        IndustryType.RESTAURANT: [
            {
                "placement": "hero",
                "label": "Hemen Rezervasyon Yap",
                "style": "primary",
                "color": "#e67e22",
                "rationale": "Restoranlarda rezervasyon en önemli dönüşüm hedefidir. Turuncu renk aciliyet hissi verir.",
                "expected_ctr": "3-5%",
            },
            {
                "placement": "after_menu",
                "label": "Masanızı Ayırtın",
                "style": "secondary",
                "color": "#27ae60",
                "rationale": "Menüyü gördükten sonra rezervasyon isteği artar.",
                "expected_ctr": "2-4%",
            },
            {
                "placement": "floating",
                "label": "☎ Rezervasyon",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Mobil kullanıcılar için sabit CTA telefonla aramayı kolaylaştırır.",
                "expected_ctr": "5-8%",
            },
            {
                "placement": "navbar",
                "label": "Rezervasyon",
                "style": "outline",
                "color": "#ffffff",
                "rationale": "Navigasyonda sürekli görünür CTA kullanıcıyı hatırlatır.",
                "expected_ctr": "1-2%",
            },
        ],
        IndustryType.CAFE: [
            {
                "placement": "hero",
                "label": "Menüyü Keşfet",
                "style": "primary",
                "color": "#6f4e37",
                "rationale": "Kafelerde menü keşfi öncelikli hedeftir. Kahve rengi brand uyumu sağlar.",
                "expected_ctr": "4-6%",
            },
            {
                "placement": "floating",
                "label": "📍 Yol Tarifi",
                "style": "primary",
                "color": "#27ae60",
                "rationale": "Kafeye gelmek isteyenler için yol tarifi CTA'sı çok etkilidir.",
                "expected_ctr": "6-10%",
            },
        ],
        IndustryType.HEALTHCARE: [
            {
                "placement": "hero",
                "label": "Online Randevu Al",
                "style": "primary",
                "color": "#2980b9",
                "rationale": "Sağlık sektöründe online randevu en kritik dönüşüm hedefidir.",
                "expected_ctr": "5-8%",
            },
            {
                "placement": "navbar",
                "label": "Randevu",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Acil randevu ihtiyacı olan kullanıcılar için navigasyonda sürekli görünür.",
                "expected_ctr": "2-3%",
            },
            {
                "placement": "after_services",
                "label": "Uzmana Danışın",
                "style": "secondary",
                "color": "#2980b9",
                "rationale": "Hizmetleri gördükten sonra danışma isteği artar.",
                "expected_ctr": "3-5%",
            },
        ],
        IndustryType.FITNESS: [
            {
                "placement": "hero",
                "label": "Ücretsiz Deneme Dersi Al",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Ücretsiz deneme fitness sektöründe en etkili lead generation aracıdır.",
                "expected_ctr": "8-12%",
            },
            {
                "placement": "floating",
                "label": "🎁 Ücretsiz Dene",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Hediye ikonu ve ücretsiz kelimesi dikkat çeker.",
                "expected_ctr": "10-15%",
            },
            {
                "placement": "after_pricing",
                "label": "Hemen Üye Ol",
                "style": "primary",
                "color": "#27ae60",
                "rationale": "Fiyatları gördükten sonra üyelik kararı verilir.",
                "expected_ctr": "3-5%",
            },
        ],
        IndustryType.SALON: [
            {
                "placement": "hero",
                "label": "Randevu Al",
                "style": "primary",
                "color": "#9b59b6",
                "rationale": "Salonlarda randevu birincil dönüşüm hedefidir.",
                "expected_ctr": "5-8%",
            },
            {
                "placement": "after_services",
                "label": "Hemen Rezervasyon Yap",
                "style": "secondary",
                "color": "#e91e63",
                "rationale": "Hizmet listesini gördükten sonra CTA daha etkilidir.",
                "expected_ctr": "4-6%",
            },
        ],
        IndustryType.HOTEL: [
            {
                "placement": "hero",
                "label": "Rezervasyon Yap",
                "style": "primary",
                "color": "#f39c12",
                "rationale": "Otelde rezervasyon birincil hedeftir. Altın rengi lüks hissi verir.",
                "expected_ctr": "6-10%",
            },
            {
                "placement": "sticky_bottom",
                "label": "En İyi Fiyat Garantisi",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Fiyat garantisi CTA'sı kullanıcıyı doğrudan rezervasyona yönlendirir.",
                "expected_ctr": "4-7%",
            },
        ],
        IndustryType.RETAIL: [
            {
                "placement": "hero",
                "label": "Alışverişe Başla",
                "style": "primary",
                "color": "#e74c3c",
                "rationale": "Kırmızı renk aciliyet ve alışveriş isteği uyandırır.",
                "expected_ctr": "5-8%",
            },
            {
                "placement": "sticky_bottom",
                "label": "Sepete Git",
                "style": "primary",
                "color": "#27ae60",
                "rationale": "Sabit sepet CTA'sı alışveriş tamamlama oranını artırır.",
                "expected_ctr": "3-5%",
            },
        ],
        IndustryType.TECHNOLOGY: [
            {
                "placement": "hero",
                "label": "Ücretsiz Demo İste",
                "style": "primary",
                "color": "#3498db",
                "rationale": "B2B teknolojide demo talebi en değerli lead'tir.",
                "expected_ctr": "4-7%",
            },
            {
                "placement": "floating",
                "label": "💬 Canlı Destek",
                "style": "primary",
                "color": "#25d366",
                "rationale": "Teknoloji ürünlerinde canlı destek CTA'sı dönüşümü artırır.",
                "expected_ctr": "3-5%",
            },
        ],
        IndustryType.CONSULTING: [
            {
                "placement": "hero",
                "label": "Ücretsiz İlk Görüşme",
                "style": "primary",
                "color": "#2c3e50",
                "rationale": "Danışmanlıkta ücretsiz ilk görüşme güven oluşturur.",
                "expected_ctr": "5-8%",
            },
        ],
        IndustryType.CONSTRUCTION: [
            {
                "placement": "hero",
                "label": "Ücretsiz Fiyat Teklifi Al",
                "style": "primary",
                "color": "#e67e22",
                "rationale": "İnşaatta ücretsiz teklif en etkili lead magnet'tir.",
                "expected_ctr": "6-10%",
            },
        ],
        IndustryType.GENERIC: [
            {
                "placement": "hero",
                "label": "Bize Ulaşın",
                "style": "primary",
                "color": "#3498db",
                "rationale": "Genel işletmelerde iletişim birincil hedeftir.",
                "expected_ctr": "3-5%",
            },
            {
                "placement": "before_footer",
                "label": "Daha Fazla Bilgi",
                "style": "secondary",
                "color": "#7f8c8d",
                "rationale": "Footer öncesi son CTA fırsatıdır.",
                "expected_ctr": "2-3%",
            },
        ],
    }

    return recommendations.get(industry, recommendations[IndustryType.GENERIC])


def get_industry_cta_strategy(industry: IndustryType) -> Dict[str, Any]:
    """
    Get a comprehensive CTA strategy for an industry.
    Returns recommended labels, placements, and optimization tips.
    """
    recommendations = get_cta_recommendations(industry)

    return {
        "industry": industry.value,
        "primary_cta": recommendations[0] if recommendations else None,
        "secondary_cta": recommendations[1] if len(recommendations) > 1 else None,
        "floating_cta": next((r for r in recommendations if r["placement"] == "floating"), None),
        "all_recommendations": recommendations,
        "general_tips": get_conversion_tips(),
    }


def get_conversion_tips() -> List[str]:
    """Get general conversion optimization tips for CTAs."""
    return [
        "CTA butonları en az 44px yüksekliğinde ve kolay tıklanabilir olmalı.",
        "Bir sayfada birden fazla CTA varsa, birincil CTA en belirgin olmalı.",
        "Buton metninde eylem kelimeleri kullanın: 'Başla', 'Keşfet', 'Al', 'Dene'.",
        "Aciliyet duygusu eklemek ('Sınırlı', 'Son Gün') dönüşümü %20-30 artırabilir.",
        "Sosyal kanıt ('500+ müşteri') güven oluşturur ve dönüşümü artırır.",
        "Mobil cihazlarda sticky/floating CTA kullanımı dönüşümü %40 artırabilir.",
        "CTA rengi sayfa arka planıyla kontrastlı olmalı.",
        "A/B testi yaparak farklı CTA metinleri ve renkleri deneyin.",
        "Navbar'da sürekli görünür CTA kullanıcıyı hatırlatır.",
        "Form gönderme sonrası teşekkür mesajı ve ek CDA gösterin.",
        "Exit-intent popup ile çıkış yapan kullanıcılara son teklif sunun.",
        "CTA etrafında beyaz alan bırakın, kalabalık CTA dikkati dağıtır.",
        "Kişiselleştirilmiş CTA metinleri ('Senin için hazırladık') daha etkilidir.",
        "Microcopy kullanın: Buton altına küçük güven mesajları ekleyin.",
        "FOMO (Fear Of Missing Out) teknikleri: '3 kişi bakıyor', 'Son 2 oda'.",
    ]
