"""
Specialized Section Templates
==============================
Pre-defined content for specialized section types.
"""

from typing import Dict, Any, List, Optional
from schemas.enums import IndustryType


def get_reservation_template(industry: IndustryType = IndustryType.RESTAURANT) -> Dict[str, Any]:
    """Get reservation/appointment booking section template."""
    title = "Rezervasyon" if industry == IndustryType.RESTAURANT else "Randevu Al"
    return {
        "config": {
            "layout_variant": "default",
            "columns": 2,
            "show_title": True,
            "show_form": True,
            "show_info": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
        "content": {
            "title": title,
            "subtitle": "Hemen Yer Ayırtın",
            "description": "Formu doldurun, size en kısa sürede dönüş yapalım.",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "guest_count", "label": "Kişi Sayısı", "type": "number", "required": True},
                {"name": "date", "label": "Tarih", "type": "date", "required": True},
                {"name": "time", "label": "Saat", "type": "time", "required": True},
                {"name": "notes", "label": "Özel İstekler", "type": "textarea", "required": False},
            ],
            "submit_button_text": "Rezervasyon Yap",
            "success_message": "Rezervasyon talebiniz alındı! En kısa sürede onaylayacağız.",
            "contact_info": {
                "phone": "+90 (212) 555 00 00",
                "email": "rezervasyon@ornek.com",
                "working_hours": "Her gün: 10:00 - 23:00",
            },
            "max_guests": 20,
            "time_slots": ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
        },
    }


def get_appointment_template(industry: IndustryType = IndustryType.HEALTHCARE) -> Dict[str, Any]:
    """Get appointment booking section template."""
    dept_options = {
        IndustryType.HEALTHCARE: ["Genel Cerrahi", "Kardiyoloji", "Ortopedi", "Dahiliye", "Kulak Burun Boğaz", "Diğer"],
        IndustryType.SALON: ["Saç", "Cilt", "Makyaj", "Manikür/Pedikür", "Damat Paketi"],
        IndustryType.FITNESS: ["Kişisel Antrenman", "Beslenme Danışmanlığı", "Fizik Tedavi", "Pilates"],
    }
    depts = dept_options.get(industry, ["Genel"])

    return {
        "config": {
            "layout_variant": "default",
            "columns": 2,
            "show_title": True,
            "show_form": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1000px",
        },
        "content": {
            "title": "Randevu Al",
            "subtitle": "Size Uygun Zamanı Seçin",
            "form_fields": [
                {"name": "name", "label": "Adınız", "type": "text", "required": True},
                {"name": "email", "label": "E-posta", "type": "email", "required": True},
                {"name": "phone", "label": "Telefon", "type": "tel", "required": True},
                {"name": "department", "label": "Bölüm/Hizmet", "type": "select", "required": True, "options": depts},
                {"name": "date", "label": "Tercih Edilen Tarih", "type": "date", "required": True},
                {"name": "time", "label": "Tercih Edilen Saat", "type": "select", "required": True,
                 "options": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]},
                {"name": "notes", "label": "Notlar", "type": "textarea", "required": False},
            ],
            "submit_button_text": "Randevu Al",
            "success_message": "Randevu talebiniz alındı! En kısa sürede size dönüş yapacağız.",
        },
    }


def get_faq_template(industry: IndustryType = IndustryType.GENERIC) -> Dict[str, Any]:
    """Get FAQ section template."""
    faq_defaults = {
        IndustryType.RESTAURANT: [
            {"question": "Rezervasyon yaptırmak zorunlu mu?", "answer": "Hafta sonları ve özel günlerde rezervasyon önerilir. Hafta içi yürüyerek de gelebilirsiniz."},
            {"question": "Vale hizmeti var mı?", "answer": "Evet, ücretsiz vale hizmetimiz mevcuttur."},
            {"question": "Çocuk menüsü var mı?", "answer": "Evet, özel çocuk menümüz ve yüksek sandalye imkanımız bulunmaktadır."},
            {"question": "Paket servis var mı?", "answer": "Evet, tüm yemeklerimizi paket servis olarak da sipariş edebilirsiniz."},
        ],
        IndustryType.CAFE: [
            {"question": "Kahvelerinizi hangi çekirdeklerden yapıyorsunuz?", "answer": "Etiyopya, Kolombiya, Guatemala ve Brezilya'dan ithal edilen özel çekirdekler kullanıyoruz."},
            {"question": "WiFi şifresi nedir?", "answer": "WiFi şifresi masalardaki kartlarda yazmaktadır. Girişte personelden de alabilirsiniz."},
            {"question": "Müşteri getirebilir miyim?", "answer": "Evet, evcil dostlarınızı getirebilirsiniz. Dış alanlarımız pet-friendly'dir."},
        ],
        IndustryType.HEALTHCARE: [
            {"question": "Randevu nasıl alabilirim?", "answer": "Web sitemizden, telefonla veya mobil uygulamamız üzerinden randevu alabilirsiniz."},
            {"question": "Acil durumlarda ne yapmalıyım?", "answer": "Acil servisimiz 7/24 hizmet vermektedir. 444 XX XX numaralı hattı arayabilirsiniz."},
            {"question": "Sigorta kapsamında hizmet alabilir miyim?", "answer": "Anlaşmalı olduğumuz sigorta şirketleri listesini iletişim sayfamızdan inceleyebilirsiniz."},
        ],
        IndustryType.FITNESS: [
            {"question": "Deneme dersi var mı?", "answer": "Evet, ücretsiz bir deneme dersi hakkınız bulunmaktadır."},
            {"question": "Üyelik iptal edilebilir mi?", "answer": "Evet, 30 gün önceden bildirimde bulunarak üyeliğinizi iptal edebilirsiniz."},
            {"question": "Eğitmen seçebilir miyim?", "answer": "Tabii, eğitmenlerimizin profillerini inceleyip tercihinizi belirtebilirsiniz."},
        ],
    }
    faqs = faq_defaults.get(industry, [
        {"question": "Soru 1?", "answer": "Cevap 1."},
        {"question": "Soru 2?", "answer": "Cevap 2."},
        {"question": "Soru 3?", "answer": "Cevap 3."},
    ])

    return {
        "config": {
            "layout_variant": "accordion",
            "alignment": "center",
            "show_title": True,
            "show_subtitle": True,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "800px",
        },
        "content": {
            "title": "Sıkça Sorulan Sorular",
            "subtitle": "Sorularınızın Cevapları",
            "faqs": faqs,
            "contact_prompt": "Cevabını bulamadınız mı? Bize ulaşın.",
            "contact_link": "/contact",
        },
    }


def get_team_template(industry: IndustryType = IndustryType.GENERIC) -> Dict[str, Any]:
    """Get team/staff section template."""
    return {
        "config": {
            "layout_variant": "grid",
            "columns": 4,
            "show_title": True,
            "show_subtitle": True,
            "show_social": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
        "content": {
            "title": "Ekibimiz",
            "subtitle": "Tanıyın",
            "members": [
                {"name": "Ahmet Yılmaz", "role": "Genel Müdür", "bio": "15 yıllık sektör deneyimi.", "social": {}},
                {"name": "Selin Kaya", "role": "Operasyon Müdürü", "bio": "İşletme yönetimi uzmanı.", "social": {}},
                {"name": "Mehmet Demir", "role": "Teknik Direktör", "bio": "Uzman bilgi ve deneyim.", "social": {}},
                {"name": "Zeynep Aydın", "role": "Müşteri İlişkileri", "bio": "Müşteri memnuniyeti odaklı.", "social": {}},
            ],
        },
    }


def get_stats_template(industry: IndustryType = IndustryType.GENERIC) -> Dict[str, Any]:
    """Get stats/counters section template."""
    return {
        "config": {
            "layout_variant": "counters",
            "columns": 4,
            "show_icon": True,
            "item_count": 4,
            "animation_level": "moderate",
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "60px",
            "padding_bottom": "60px",
            "background_color": "#f8fafc",
        },
        "content": {
            "title": "Rakamlarla Biz",
            "stats": [
                {"value": "10+", "label": "Yıllık Deneyim", "icon": "calendar"},
                {"value": "5K+", "label": "Mutlu Müşteri", "icon": "users"},
                {"value": "50+", "label": "Proje", "icon": "briefcase"},
                {"value": "20+", "label": "Uzman Çalışan", "icon": "user-tie"},
            ],
        },
    }


def get_partners_template() -> Dict[str, Any]:
    """Get partners/logo cloud section template."""
    return {
        "config": {
            "layout_variant": "logos",
            "columns": 6,
            "show_title": True,
            "show_subtitle": False,
            "item_count": 6,
            "heading_tag": "h3",
        },
        "style": {
            "padding_top": "40px",
            "padding_bottom": "40px",
            "max_width": "1200px",
        },
        "content": {
            "title": "İş Ortaklarımız",
            "logos": [
                {"name": "Partner 1", "url": None},
                {"name": "Partner 2", "url": None},
                {"name": "Partner 3", "url": None},
                {"name": "Partner 4", "url": None},
                {"name": "Partner 5", "url": None},
                {"name": "Partner 6", "url": None},
            ],
        },
    }


def get_process_steps_template(industry: IndustryType = IndustryType.GENERIC) -> Dict[str, Any]:
    """Get process/steps section template."""
    return {
        "config": {
            "layout_variant": "steps",
            "columns": 4,
            "show_title": True,
            "show_subtitle": True,
            "show_icon": True,
            "item_count": 4,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "max_width": "1200px",
        },
        "content": {
            "title": "Süreç",
            "subtitle": "Nasıl Çalışıyoruz?",
            "steps": [
                {"number": 1, "title": "İletişim", "description": "Bize ulaşın, ihtiyaçlarınızı dinleyelim.", "icon": "phone"},
                {"number": 2, "title": "Planlama", "description": "Size özel çözüm planı hazırlayalım.", "icon": "clipboard-list"},
                {"number": 3, "title": "Uygulama", "description": "Planı hayata geçirelim.", "icon": "cogs"},
                {"number": 4, "title": "Teslimat", "description": "Sonuçları birlikte değerlendirelim.", "icon": "check-circle"},
            ],
        },
    }


def get_newsletter_template() -> Dict[str, Any]:
    """Get newsletter signup section template."""
    return {
        "config": {
            "layout_variant": "inline",
            "alignment": "center",
            "show_title": True,
            "heading_tag": "h3",
        },
        "style": {
            "padding_top": "60px",
            "padding_bottom": "60px",
            "max_width": "600px",
        },
        "content": {
            "title": "Bültenimize Abone Olun",
            "description": "Kampanya, duyuru ve yeniliklerden ilk siz haberdar olun.",
            "placeholder": "E-posta adresiniz",
            "button_text": "Abone Ol",
            "privacy_note": "E-posta adresiniz güvende. İstediğiniz zaman aboneliğinizi iptal edebilirsiniz.",
            "success_message": "Aboneliğiniz başarıyla tamamlandı!",
        },
    }


def get_trust_badges_template() -> Dict[str, Any]:
    """Get trust badges section template."""
    return {
        "config": {
            "layout_variant": "badges",
            "columns": 4,
            "show_icon": True,
            "item_count": 4,
        },
        "style": {
            "padding_top": "40px",
            "padding_bottom": "40px",
            "max_width": "1000px",
        },
        "content": {
            "badges": [
                {"icon": "shield-alt", "title": "Güvenli Ödeme", "description": "256-bit SSL güvenliği"},
                {"icon": "truck", "title": "Hızlı Teslimat", "description": "Aynı gün kargo"},
                {"icon": "undo", "title": "Kolay İade", "description": "14 gün içinde iade"},
                {"icon": "headset", "title": "7/24 Destek", "description": "Her zaman yanınızdayız"},
            ],
        },
    }


def get_location_template(industry: IndustryType = IndustryType.GENERIC) -> Dict[str, Any]:
    """Get location/map section template."""
    return {
        "config": {
            "layout_variant": "with_map",
            "columns": 2,
            "show_title": True,
            "show_form": False,
            "heading_tag": "h2",
        },
        "style": {
            "padding_top": "80px",
            "padding_bottom": "80px",
            "full_width": True,
        },
        "content": {
            "title": "Bizi Ziyaret Edin",
            "subtitle": "Konumumuz",
            "address": "İstanbul, Türkiye",
            "phone": "+90 (212) 555 00 00",
            "email": "info@ornek.com",
            "working_hours": "Pazartesi - Cumartesi: 09:00 - 18:00",
            "map_embed_url": None,
            "map_lat": 41.0082,
            "map_lng": 28.9784,
            "parking_info": "Ücretsiz otopark mevcuttur.",
            "public_transport": "Metro: M2 - Şişhane İstasyonu",
        },
    }
