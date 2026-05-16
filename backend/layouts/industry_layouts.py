"""
Industry Layout Presets
=======================
Pre-configured page layouts for common industries.
These define the recommended page structure (sections and their order)
for each supported industry vertical.
"""

from typing import Dict, Any, List
from schemas.enums import IndustryType, SectionType, PageType


def _create_page_spec(
    page_id: str,
    page_name: str,
    slug: str,
    is_homepage: bool,
    sections: List[Dict[str, Any]],
    meta_title: str = "",
    meta_description: str = "",
) -> Dict[str, Any]:
    """Helper to create a page specification."""
    return {
        "page_id": page_id,
        "page_name": page_name,
        "slug": slug,
        "is_homepage": is_homepage,
        "meta_title": meta_title or page_name,
        "meta_description": meta_description,
        "sections": sections,
    }


def _create_section_spec(
    section_type: SectionType,
    name: str = "",
    variant: str = "default",
    position: int = 0,
) -> Dict[str, Any]:
    """Helper to create a section specification."""
    return {
        "section_type": section_type,
        "name": name or section_type.value,
        "variant": variant,
        "position": position,
    }


def get_restaurant_layout() -> Dict[str, Any]:
    """Get the recommended layout for a restaurant website."""
    return {
        "industry": IndustryType.RESTAURANT.value,
        "description": "Restoran web sitesi - menü, rezervasyon ve galeri odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.ABOUT, "Hakkımızda", "split", 2),
                    _create_section_spec(SectionType.MENU, "Menü", "tabs", 3),
                    _create_section_spec(SectionType.GALLERY, "Galeri", "masonry", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Yorumlar", "carousel", 5),
                    _create_section_spec(SectionType.CTA, "Rezervasyon CTA", "default", 6),
                    _create_section_spec(SectionType.LOCATION, "Konum", "with_map", 7),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 8),
                ],
                meta_title="Restoran - Lezzetin Adresi",
                meta_description="Taze malzemeler, unutulmaz tatlar. Rezervasyon için hemen arayın.",
            ),
            _create_page_spec(
                "menu", "Menü", "/menu", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "Menü Başlık", "minimal", 1),
                    _create_section_spec(SectionType.MENU, "Tüm Menü", "default", 2),
                    _create_section_spec(SectionType.CTA, "Rezervasyon CTA", "default", 3),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 4),
                ],
                meta_title="Menümüz - Restoran",
            ),
            _create_page_spec(
                "reservation", "Rezervasyon", "/reservation", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.RESERVATION, "Rezervasyon Formu", "default", 1),
                    _create_section_spec(SectionType.CONTACT_INFO, "İletişim Bilgileri", "info_only", 2),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 3),
                ],
                meta_title="Rezervasyon - Restoran",
            ),
            _create_page_spec(
                "about", "Hakkımızda", "/about", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "Hakkımızda Başlık", "minimal", 1),
                    _create_section_spec(SectionType.ABOUT, "Hikayemiz", "default", 2),
                    _create_section_spec(SectionType.STATS_COUNTERS, "İstatistikler", "counters", 3),
                    _create_section_spec(SectionType.ABOUT_TEAM, "Şeflerimiz", "team", 4),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 5),
                ],
                meta_title="Hakkımızda - Restoran",
            ),
            _create_page_spec(
                "contact", "İletişim", "/contact", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "İletişim Başlık", "minimal", 1),
                    _create_section_spec(SectionType.CONTACT, "İletişim", "with_map", 2),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 3),
                ],
                meta_title="İletişim - Restoran",
            ),
        ],
        "features": {
            "reservations": True,
            "contact_form": True,
            "reviews": True,
            "multilingual": False,
            "live_chat": False,
        },
    }


def get_cafe_layout() -> Dict[str, Any]:
    """Get the recommended layout for a cafe website."""
    return {
        "industry": IndustryType.CAFE.value,
        "description": "Kafe web sitesi - kahve menüsü ve atmosfer odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.ABOUT, "Hakkımızda", "split", 2),
                    _create_section_spec(SectionType.MENU, "Menü", "tabs", 3),
                    _create_section_spec(SectionType.GALLERY, "Galeri", "grid", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Yorumlar", "carousel", 5),
                    _create_section_spec(SectionType.LOCATION, "Konum", "with_map", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
                meta_title="Kafe - Güne Kahveyle Başlayın",
            ),
            _create_page_spec(
                "menu", "Menü", "/menu", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "Menü Başlık", "minimal", 1),
                    _create_section_spec(SectionType.MENU, "Kahve Menüsü", "grid", 2),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 3),
                ],
            ),
            _create_page_spec(
                "about", "Hakkımızda", "/about", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.ABOUT, "Hikayemiz", "default", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
            _create_page_spec(
                "contact", "İletişim", "/contact", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.CONTACT, "İletişim", "with_map", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
        ],
        "features": {
            "contact_form": True,
            "reviews": True,
            "multilingual": False,
        },
    }


def get_healthcare_layout() -> Dict[str, Any]:
    """Get the recommended layout for a healthcare/clinic website."""
    return {
        "industry": IndustryType.HEALTHCARE.value,
        "description": "Sağlık kliniği web sitesi - randevu ve hizmet odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.SERVICES, "Hizmetler", "cards", 2),
                    _create_section_spec(SectionType.ABOUT, "Kliniğimiz", "split", 3),
                    _create_section_spec(SectionType.ABOUT_TEAM, "Doktorlarımız", "team", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Hasta Yorumları", "carousel", 5),
                    _create_section_spec(SectionType.APPOINTMENT, "Randevu", "default", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
                meta_title="Sağlık Kliniği - Sağlığınız İçin Buradayız",
            ),
            _create_page_spec(
                "services", "Hizmetler", "/services", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "Hizmetler", "minimal", 1),
                    _create_section_spec(SectionType.SERVICES, "Tüm Hizmetler", "grid", 2),
                    _create_section_spec(SectionType.FAQ, "Sık Sorulan Sorular", "accordion", 3),
                    _create_section_spec(SectionType.CTA, "Randevu CTA", "default", 4),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 5),
                ],
            ),
            _create_page_spec(
                "doctors", "Doktorlarımız", "/doctors", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_MINIMAL, "Doktorlar", "minimal", 1),
                    _create_section_spec(SectionType.ABOUT_TEAM, "Ekibimiz", "team", 2),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 3),
                ],
            ),
            _create_page_spec(
                "appointment", "Randevu", "/appointment", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.APPOINTMENT, "Randevu Formu", "default", 1),
                    _create_section_spec(SectionType.CONTACT_INFO, "İletişim", "info_only", 2),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 3),
                ],
            ),
            _create_page_spec(
                "contact", "İletişim", "/contact", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.CONTACT, "İletişim", "with_map", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
        ],
        "features": {
            "appointment_booking": True,
            "contact_form": True,
            "reviews": True,
            "live_chat": True,
        },
    }


def get_fitness_layout() -> Dict[str, Any]:
    """Get the recommended layout for a fitness/gym website."""
    return {
        "industry": IndustryType.FITNESS.value,
        "description": "Fitness salonu web sitesi - programlar ve üyelik odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_VIDEO, "Hero", "video", 1),
                    _create_section_spec(SectionType.SERVICES, "Programlar", "cards", 2),
                    _create_section_spec(SectionType.PRICING, "Üyelik", "default", 3),
                    _create_section_spec(SectionType.ABOUT_TEAM, "Eğitmenler", "team", 4),
                    _create_section_spec(SectionType.STATS_COUNTERS, "Rakamlar", "counters", 5),
                    _create_section_spec(SectionType.TESTIMONIALS, "Başarılar", "carousel", 6),
                    _create_section_spec(SectionType.CTA, "Ücretsiz Deneme", "default", 7),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 8),
                ],
                meta_title="Fitness Salonu - Daha Güçlü Bir Sen",
            ),
            _create_page_spec(
                "programs", "Programlar", "/programs", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.SERVICES, "Programlar", "grid", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
            _create_page_spec(
                "pricing", "Fiyatlar", "/pricing", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.PRICING, "Üyelik Paketleri", "default", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
            _create_page_spec(
                "contact", "İletişim", "/contact", False,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.CONTACT, "İletişim", "with_map", 1),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 2),
                ],
            ),
        ],
        "features": {
            "appointment_booking": True,
            "contact_form": True,
            "reviews": True,
        },
    }


def get_salon_layout() -> Dict[str, Any]:
    """Get the recommended layout for a salon/barber website."""
    return {
        "industry": IndustryType.SALON.value,
        "description": "Kuaför/güzellik salonu web sitesi - randevu ve hizmet odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.SERVICES, "Hizmetler", "cards", 2),
                    _create_section_spec(SectionType.PRICING, "Fiyat Listesi", "tables", 3),
                    _create_section_spec(SectionType.GALLERY, "Galeri", "grid", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Yorumlar", "carousel", 5),
                    _create_section_spec(SectionType.APPOINTMENT, "Randevu", "default", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
                meta_title="Güzellik Salonu - Tarzınızı Yenileyin",
            ),
        ],
        "features": {
            "appointment_booking": True,
            "contact_form": True,
        },
    }


def get_hotel_layout() -> Dict[str, Any]:
    """Get the recommended layout for a hotel website."""
    return {
        "industry": IndustryType.HOTEL.value,
        "description": "Otel web sitesi - oda rezervasyonu ve olanaklar odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO_SLIDER, "Hero", "slider", 1),
                    _create_section_spec(SectionType.ABOUT, "Otelimiz", "split", 2),
                    _create_section_spec(SectionType.SERVICES, "Olanaklar", "cards", 3),
                    _create_section_spec(SectionType.GALLERY, "Galeri", "masonry", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Misafir Yorumları", "carousel", 5),
                    _create_section_spec(SectionType.RESERVATION, "Rezervasyon", "default", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
                meta_title="Otel - Konforun Yeni Adı",
            ),
        ],
        "features": {
            "reservations": True,
            "contact_form": True,
            "reviews": True,
        },
    }


def get_retail_layout() -> Dict[str, Any]:
    """Get the recommended layout for a retail store website."""
    return {
        "industry": IndustryType.RETAIL.value,
        "description": "Perakende mağaza web sitesi - ürün vitrini ve iletişim odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.PRODUCTS, "Ürünler", "grid", 2),
                    _create_section_spec(SectionType.FEATURES, "Neden Biz?", "tabs", 3),
                    _create_section_spec(SectionType.GALLERY, "Galeri", "grid", 4),
                    _create_section_spec(SectionType.TESTIMONIALS, "Müşteri Yorumları", "carousel", 5),
                    _create_section_spec(SectionType.LOCATION, "Mağazalarımız", "with_map", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
            ),
        ],
        "features": {
            "contact_form": True,
            "ecommerce": True,
        },
    }


def get_technology_layout() -> Dict[str, Any]:
    """Get the recommended layout for a technology company website."""
    return {
        "industry": IndustryType.TECHNOLOGY.value,
        "description": "Teknoloji şirketi web sitesi - ürün ve hizmet tanıtım odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.FEATURES, "Özellikler", "tabs", 2),
                    _create_section_spec(SectionType.SERVICES, "Hizmetler", "grid", 3),
                    _create_section_spec(SectionType.INTEGRATIONS, "Entegrasyonlar", "default", 4),
                    _create_section_spec(SectionType.PRICING, "Fiyatlandırma", "default", 5),
                    _create_section_spec(SectionType.TESTIMONIALS, "Müşteri Yorumları", "carousel", 6),
                    _create_section_spec(SectionType.CTA, "Demo İste", "default", 7),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 8),
                ],
                meta_title="Teknoloji Şirketi - Geleceği İnşa Ediyoruz",
            ),
        ],
        "features": {
            "contact_form": True,
            "live_chat": True,
        },
    }


def get_construction_layout() -> Dict[str, Any]:
    """Get the recommended layout for a construction company website."""
    return {
        "industry": IndustryType.CONSTRUCTION.value,
        "description": "İnşaat şirketi web sitesi - proje vitrini ve hizmet odaklı",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.SERVICES, "Hizmetler", "cards", 2),
                    _create_section_spec(SectionType.GALLERY, "Projelerimiz", "masonry", 3),
                    _create_section_spec(SectionType.ABOUT, "Hakkımızda", "split", 4),
                    _create_section_spec(SectionType.STATS_COUNTERS, "Rakamlar", "counters", 5),
                    _create_section_spec(SectionType.PROCESS_STEPS, "Süreç", "steps", 6),
                    _create_section_spec(SectionType.CTA, "Teklif Al", "default", 7),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 8),
                ],
                meta_title="İnşaat Şirketi - Hayallerinizi İnşa Ediyoruz",
            ),
        ],
        "features": {
            "contact_form": True,
        },
    }


def get_industry_layout(industry: IndustryType) -> Dict[str, Any]:
    """
    Get the recommended layout for any supported industry.
    
    Args:
        industry: The industry type
        
    Returns:
        Complete layout specification with pages and sections
    """
    layout_getters = {
        IndustryType.RESTAURANT: get_restaurant_layout,
        IndustryType.CAFE: get_cafe_layout,
        IndustryType.HEALTHCARE: get_healthcare_layout,
        IndustryType.FITNESS: get_fitness_layout,
        IndustryType.SALON: get_salon_layout,
        IndustryType.HOTEL: get_hotel_layout,
        IndustryType.RETAIL: get_retail_layout,
        IndustryType.TECHNOLOGY: get_technology_layout,
        IndustryType.CONSTRUCTION: get_construction_layout,
    }
    
    getter = layout_getters.get(industry)
    if getter:
        return getter()
    
    # Return a generic layout for unmapped industries
    return {
        "industry": industry.value,
        "description": f"{industry.value} web sitesi - genel layout",
        "pages": [
            _create_page_spec(
                "home", "Ana Sayfa", "/", True,
                [
                    _create_section_spec(SectionType.NAVBAR, "Navigasyon", "default", 0),
                    _create_section_spec(SectionType.HERO, "Hero", "default", 1),
                    _create_section_spec(SectionType.ABOUT, "Hakkımızda", "default", 2),
                    _create_section_spec(SectionType.SERVICES, "Hizmetler", "default", 3),
                    _create_section_spec(SectionType.TESTIMONIALS, "Yorumlar", "default", 4),
                    _create_section_spec(SectionType.CTA, "CTA", "default", 5),
                    _create_section_spec(SectionType.CONTACT, "İletişim", "with_map", 6),
                    _create_section_spec(SectionType.FOOTER, "Footer", "default", 7),
                ],
            ),
        ],
        "features": {
            "contact_form": True,
        },
    }


def list_supported_industries() -> List[str]:
    """List all industries with pre-defined layouts."""
    return [
        IndustryType.RESTAURANT.value,
        IndustryType.CAFE.value,
        IndustryType.HEALTHCARE.value,
        IndustryType.FITNESS.value,
        IndustryType.SALON.value,
        IndustryType.HOTEL.value,
        IndustryType.RETAIL.value,
        IndustryType.TECHNOLOGY.value,
        IndustryType.CONSTRUCTION.value,
    ]
