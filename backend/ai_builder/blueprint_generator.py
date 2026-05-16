"""
AI Blueprint Generator
=======================
Generates complete website blueprints from business descriptions.
This is the entry point for AI-driven website creation.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from schemas.enums import IndustryType, BusinessSize, ColorScheme, FontPair, AnimationLevel, DeviceTarget, SectionType
from schemas.blueprint import Blueprint, BlueprintPage, BlueprintSection, BlueprintRecommendation


class GenerationContext(BaseModel):
    """Context for AI blueprint generation."""
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    target_audience: Optional[str] = None
    tone_of_voice: Optional[str] = "professional"
    existing_website: Optional[str] = None
    competitor_websites: Optional[List[str]] = None
    preferred_colors: Optional[List[str]] = None
    must_have_features: Optional[List[str]] = None
    language: str = "tr"

    class Config:
        extra = "allow"


class BlueprintGenerator:
    """
    Generates website blueprints from business context.
    This is the core AI component that translates business requirements
    into structured website specifications.
    """

    def __init__(self):
        self._industry_section_map = self._build_industry_section_map()

    def _build_industry_section_map(self) -> Dict[IndustryType, List[Dict[str, Any]]]:
        """Build the default section structure for each industry."""
        return {
            IndustryType.RESTAURANT: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Restoranın atmosferini ve lezzetini yansıtan ana karşılama alanı"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Restoranın hikayesi, misyonu ve değerleri"},
                {"type": SectionType.MENU, "variant": "tabs", "purpose": "Kategorize edilmiş yemek ve içecek menüsü"},
                {"type": SectionType.GALLERY, "variant": "masonry", "purpose": "Mekan, yemek ve etkinlik fotoğrafları"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Misafir değerlendirmeleri ve yorumlar"},
                {"type": SectionType.RESERVATION, "variant": "default", "purpose": "Online rezervasyon formu"},
                {"type": SectionType.LOCATION, "variant": "with_map", "purpose": "Adres, çalışma saatleri ve harita"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.CAFE: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Kafe atmosferi ve kahve kültürü tanıtımı"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Kafe hikayesi ve kahve anlayışı"},
                {"type": SectionType.MENU, "variant": "tabs", "purpose": "Kahve, tatlı ve atıştırmalık menüsü"},
                {"type": SectionType.GALLERY, "variant": "grid", "purpose": "Kafe ortamı, kahve ve pastalar"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Müşteri değerlendirmeleri"},
                {"type": SectionType.LOCATION, "variant": "with_map", "purpose": "Konum ve çalışma saatleri"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.HEALTHCARE: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Klinik tanıtımı ve güven mesajı"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "Tıbbi hizmet ve branş tanıtımı"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Klinik hakkında bilgi"},
                {"type": SectionType.ABOUT_TEAM, "variant": "team", "purpose": "Doktor ve uzman kadro tanıtımı"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Hasta yorumları ve başarı hikayeleri"},
                {"type": SectionType.APPOINTMENT, "variant": "default", "purpose": "Online randevu formu"},
                {"type": SectionType.FAQ, "variant": "accordion", "purpose": "Sık sorulan sorular"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.FITNESS: [
                {"type": SectionType.HERO_VIDEO, "variant": "video", "purpose": "Spor salonu enerjisi ve motivasyon"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "Fitness programları ve dersler"},
                {"type": SectionType.PRICING, "variant": "default", "purpose": "Üyelik paketleri"},
                {"type": SectionType.ABOUT_TEAM, "variant": "team", "purpose": "Eğitmen kadrosu"},
                {"type": SectionType.STATS_COUNTERS, "variant": "counters", "purpose": "Salon istatistikleri"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Üye başarı hikayeleri"},
                {"type": SectionType.CTA, "variant": "default", "purpose": "Ücretsiz deneme CTA"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.SALON: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Salon atmosferi ve hizmet tanıtımı"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "Saç, cilt, makyaj hizmetleri"},
                {"type": SectionType.PRICING, "variant": "tables", "purpose": "Fiyat listesi"},
                {"type": SectionType.GALLERY, "variant": "grid", "purpose": "Before/after görselleri"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Müşteri yorumları"},
                {"type": SectionType.APPOINTMENT, "variant": "default", "purpose": "Randevu formu"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.HOTEL: [
                {"type": SectionType.HERO_SLIDER, "variant": "slider", "purpose": "Otel ve oda görselleri slayt"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Otel tanıtımı"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "SPA, restoran, toplantı olanakları"},
                {"type": SectionType.GALLERY, "variant": "masonry", "purpose": "Otel, oda ve tesis görselleri"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Misafir yorumları"},
                {"type": SectionType.RESERVATION, "variant": "default", "purpose": "Oda rezervasyon formu"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.TECHNOLOGY: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Ürün/hizmet ana tanıtımı"},
                {"type": SectionType.FEATURES, "variant": "tabs", "purpose": "Özellikler ve yetenekler"},
                {"type": SectionType.SERVICES, "variant": "grid", "purpose": "Hizmetler ve çözümler"},
                {"type": SectionType.INTEGRATIONS, "variant": "default", "purpose": "Entegrasyonlar ve partnerler"},
                {"type": SectionType.PRICING, "variant": "default", "purpose": "Fiyatlandırma planları"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Müşteri case'leri"},
                {"type": SectionType.CTA, "variant": "default", "purpose": "Demo talep CTA"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.CONSTRUCTION: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "İnşaat şirketi tanıtımı"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "İnşaat hizmetleri"},
                {"type": SectionType.GALLERY, "variant": "masonry", "purpose": "Tamamlanan projeler"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Şirket hakkında"},
                {"type": SectionType.STATS_COUNTERS, "variant": "counters", "purpose": "Proje istatistikleri"},
                {"type": SectionType.PROCESS_STEPS, "variant": "steps", "purpose": "Çalışma süreci"},
                {"type": SectionType.CTA, "variant": "default", "purpose": "Teklif alma CTA"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.EDUCATION: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Eğitim kurumu tanıtımı"},
                {"type": SectionType.SERVICES, "variant": "cards", "purpose": "Programlar ve dersler"},
                {"type": SectionType.ABOUT, "variant": "split", "purpose": "Kurum hakkında"},
                {"type": SectionType.ABOUT_TEAM, "variant": "team", "purpose": "Eğitmen kadrosu"},
                {"type": SectionType.STATS_COUNTERS, "variant": "counters", "purpose": "Öğrenci ve başarı istatistikleri"},
                {"type": SectionType.TESTIMONIALS, "variant": "carousel", "purpose": "Öğrenci ve veli yorumları"},
                {"type": SectionType.CTA, "variant": "default", "purpose": "Kayıt CTA"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
            IndustryType.GENERIC: [
                {"type": SectionType.HERO, "variant": "default", "purpose": "Ana karşılama ve tanıtım"},
                {"type": SectionType.ABOUT, "variant": "default", "purpose": "Hakkımızda bilgisi"},
                {"type": SectionType.SERVICES, "variant": "default", "purpose": "Hizmetler tanıtımı"},
                {"type": SectionType.TESTIMONIALS, "variant": "default", "purpose": "Müşteri yorumları"},
                {"type": SectionType.CTA, "variant": "default", "purpose": "Ana CTA"},
                {"type": SectionType.CONTACT, "variant": "with_map", "purpose": "İletişim bilgileri"},
                {"type": SectionType.FOOTER, "variant": "default", "purpose": "Footer bilgileri"},
            ],
        }

    # ── Blueprint Generation ───────────────────────────────────

    def generate_blueprint(
        self,
        industry: IndustryType,
        context: Optional[GenerationContext] = None,
        color_scheme: ColorScheme = ColorScheme.CORPORATE_BLUE,
        font_pair: FontPair = FontPair.MODERN_SANS,
    ) -> Blueprint:
        """
        Generate a complete website blueprint from business parameters.

        Args:
            industry: Business industry type
            context: Additional business context (name, description, etc.)
            color_scheme: Preferred color scheme
            font_pair: Preferred font pairing

        Returns:
            A complete Blueprint instance ready for site assembly
        """
        ctx = context or GenerationContext()
        now = datetime.now()

        # Get industry section map
        section_map = self._industry_section_map.get(industry, self._industry_section_map[IndustryType.GENERIC])

        # Build blueprint pages
        pages = self._build_pages(industry, section_map)

        # Build feature flags
        features = self._build_feature_flags(industry)

        # Build recommendations
        recommendations = self._build_recommendations(industry)

        # Determine CTA strategy
        cta_config = self._get_cta_config(industry)

        blueprint = Blueprint(
            generated_by="ai",
            generation_prompt=ctx.business_description,
            industry=industry,
            business_name=ctx.business_name or f"{industry.value.title()} İşletmem",
            business_description=ctx.business_description,
            target_audience=ctx.target_audience,
            tone_of_voice=ctx.tone_of_voice,
            color_scheme=color_scheme,
            font_pair=font_pair,
            animation_level=AnimationLevel.SUBTLE,
            device_target=DeviceTarget.ALL_DEVICES,
            pages=pages,
            primary_cta=cta_config["primary_label"],
            primary_cta_link=cta_config["primary_link"],
            secondary_cta=cta_config.get("secondary_label"),
            cta_locations=cta_config.get("placements"),
            recommendations=recommendations,
            features=features,
        )

        return blueprint

    def _build_pages(
        self,
        industry: IndustryType,
        section_map: List[Dict[str, Any]],
    ) -> List[BlueprintPage]:
        """Build blueprint pages from section map."""
        # Group sections by page
        homepage_sections = []
        other_pages: Dict[str, List[BlueprintSection]] = {}

        for i, sec in enumerate(section_map):
            bp_section = BlueprintSection(
                section_type=sec["type"],
                name=sec["purpose"],
                purpose=sec["purpose"],
                position=i,
                layout_variant=sec["variant"],
                content_guidelines=f"{sec['purpose']} için endüstriye uygun içerik oluştur.",
            )

            # Navigation and footer go on all pages
            if sec["type"] in (SectionType.NAVBAR, SectionType.FOOTER):
                for page_sections in other_pages.values():
                    page_sections.append(bp_section)
                homepage_sections.append(bp_section)
            else:
                homepage_sections.append(bp_section)

        # Create homepage
        pages = [
            BlueprintPage(
                page_id="home",
                page_name="Ana Sayfa",
                slug="/",
                is_homepage=True,
                meta_title=f"Ana Sayfa - {industry.value.title()}",
                purpose="Ana karşılama sayfası, tüm bölümler",
                sections=homepage_sections,
            ),
        ]

        # Add sub-pages based on industry
        pages.extend(self._build_sub_pages(industry, section_map))

        return pages

    def _build_sub_pages(
        self,
        industry: IndustryType,
        section_map: List[Dict[str, Any]],
    ) -> List[BlueprintPage]:
        """Build sub-pages for an industry."""
        sub_pages = []

        page_configs = {
            IndustryType.RESTAURANT: [
                ("menu", "Menü", "/menu", "Tüm yemek ve içecek menüsü"),
                ("reservation", "Rezervasyon", "/reservation", "Online rezervasyon"),
                ("about", "Hakkımızda", "/about", "Restoran hikayesi ve ekibi"),
                ("contact", "İletişim", "/contact", "İletişim bilgileri ve harita"),
            ],
            IndustryType.CAFE: [
                ("menu", "Menü", "/menu", "Kahve ve tatlı menüsü"),
                ("about", "Hakkımızda", "/about", "Kafe hikayesi"),
                ("contact", "İletişim", "/contact", "Konum ve iletişim"),
            ],
            IndustryType.HEALTHCARE: [
                ("services", "Hizmetler", "/services", "Tüm tıbbi hizmetler"),
                ("doctors", "Doktorlarımız", "/doctors", "Uzman kadro"),
                ("appointment", "Randevu", "/appointment", "Online randevu"),
                ("contact", "İletişim", "/contact", "İletişim ve ulaşım"),
            ],
            IndustryType.FITNESS: [
                ("programs", "Programlar", "/programs", "Fitness programları"),
                ("pricing", "Fiyatlar", "/pricing", "Üyelik paketleri"),
                ("trainers", "Eğitmenler", "/trainers", "Eğitmen kadrosu"),
                ("contact", "İletişim", "/contact", "İletişim bilgileri"),
            ],
            IndustryType.HOTEL: [
                ("rooms", "Odalar", "/rooms", "Oda tipleri ve özellikleri"),
                ("facilities", "Olanaklar", "/facilities", "SPA, restoran, havuz"),
                ("reservation", "Rezervasyon", "/reservation", "Oda rezervasyonu"),
                ("contact", "İletişim", "/contact", "İletişim ve ulaşım"),
            ],
        }

        for page_id, name, slug, purpose in page_configs.get(industry, []):
            sub_pages.append(BlueprintPage(
                page_id=page_id,
                page_name=name,
                slug=slug,
                is_homepage=False,
                purpose=purpose,
                sections=[],
            ))

        return sub_pages

    def _build_feature_flags(self, industry: IndustryType) -> Dict[str, bool]:
        """Build industry-specific feature flags."""
        base = {
            "contact_form": True,
            "appointment_booking": False,
            "ecommerce": False,
            "blog": False,
            "multilingual": False,
            "dark_mode": False,
            "live_chat": False,
            "newsletter": False,
            "social_feed": False,
            "search": False,
            "reservations": False,
            "reviews": True,
        }

        industry_features = {
            IndustryType.RESTAURANT: {"reservations": True, "contact_form": True},
            IndustryType.CAFE: {"contact_form": True},
            IndustryType.HEALTHCARE: {"appointment_booking": True, "live_chat": True, "search": True},
            IndustryType.FITNESS: {"appointment_booking": True, "contact_form": True},
            IndustryType.SALON: {"appointment_booking": True, "contact_form": True},
            IndustryType.HOTEL: {"reservations": True, "live_chat": True, "multilingual": True},
            IndustryType.RETAIL: {"ecommerce": True, "contact_form": True},
            IndustryType.TECHNOLOGY: {"contact_form": True, "live_chat": True, "blog": True},
        }

        features = industry_features.get(industry, {})
        base.update(features)
        return base

    def _build_recommendations(self, industry: IndustryType) -> List[BlueprintRecommendation]:
        """Build AI recommendations for the blueprint."""
        return [
            BlueprintRecommendation(
                category="conversion",
                priority="high",
                title="Rezervasyon/Randevu Sistemi Ekleme",
                description="Online rezervasyon veya randevu alma özelliği dönüşüm oranını önemli ölçüde artırır.",
                actionable_steps=["Rezervasyon formu ekle", "Takvim entegrasyonu yap", "SMS onay sistemi kur"],
                expected_impact="Dönüşüm oranında %40-60 artış",
                auto_applicable=False,
            ),
            BlueprintRecommendation(
                category="seo",
                priority="high",
                title="Schema.org Structured Data",
                description="Schema.org yapılandırılmış verileri Google'da zengin sonuçlar gösterilmesini sağlar.",
                actionable_steps=["LocalBusiness schema ekle", "Review schema ekle", "FAQ schema ekle"],
                expected_impact="Arama sonuçlarında görünürlük artışı",
                auto_applicable=True,
            ),
            BlueprintRecommendation(
                category="ux",
                priority="medium",
                title="Sayfa Yükleme Hızı Optimizasyonu",
                description="Görsellerin lazy loading ile yüklenmesi ve kod optimizasyonu.",
                actionable_steps=["Görselleri WebP formatına dönüştür", "Lazy loading ekle", "CSS/JS minify yap"],
                expected_impact="Sayfa hızında %30-50 iyileşme",
                auto_applicable=True,
            ),
            BlueprintRecommendation(
                category="accessibility",
                priority="medium",
                title="Erişilebilirlik Uyumluluğu",
                description="WCAG 2.1 AA standartlarına uygunluk.",
                actionable_steps=["Renk kontrastını kontrol et", "Alt text ekle", "Klavye navigasyonu test et"],
                expected_impact="Daha geniş kitleye ulaşım",
                auto_applicable=True,
            ),
        ]

    def _get_cta_config(self, industry: IndustryType) -> Dict[str, Any]:
        """Get CTA configuration for an industry."""
        configs = {
            IndustryType.RESTAURANT: {
                "primary_label": "Rezervasyon Yap",
                "primary_link": "#reservation",
                "secondary_label": "Menüyü Gör",
                "placements": ["hero", "after_about", "before_footer"],
            },
            IndustryType.CAFE: {
                "primary_label": "Menüyü Keşfet",
                "primary_link": "#menu",
                "secondary_label": "Konumumuz",
                "placements": ["hero", "after_services"],
            },
            IndustryType.HEALTHCARE: {
                "primary_label": "Randevu Al",
                "primary_link": "#appointment",
                "secondary_label": "Hizmetlerimiz",
                "placements": ["hero", "navbar", "after_services", "before_footer"],
            },
            IndustryType.FITNESS: {
                "primary_label": "Ücretsiz Deneme",
                "primary_link": "#trial",
                "secondary_label": "Paketleri İncele",
                "placements": ["hero", "navbar", "after_pricing", "floating"],
            },
            IndustryType.SALON: {
                "primary_label": "Randevu Al",
                "primary_link": "#appointment",
                "secondary_label": "Hizmetler",
                "placements": ["hero", "after_services", "before_footer"],
            },
            IndustryType.HOTEL: {
                "primary_label": "Rezervasyon Yap",
                "primary_link": "#reservation",
                "secondary_label": "Odaları İncele",
                "placements": ["hero", "navbar", "after_about", "sticky_bottom"],
            },
            IndustryType.TECHNOLOGY: {
                "primary_label": "Ücretsiz Demo",
                "primary_link": "#demo",
                "secondary_label": "Daha Fazla Bilgi",
                "placements": ["hero", "navbar", "after_services", "floating"],
            },
            IndustryType.CONSTRUCTION: {
                "primary_label": "Teklif Al",
                "primary_link": "#quote",
                "secondary_label": "Projelerimiz",
                "placements": ["hero", "after_services", "before_footer"],
            },
        }
        return configs.get(industry, {
            "primary_label": "Bize Ulaşın",
            "primary_link": "#contact",
            "placements": ["hero", "before_footer"],
        })


# Singleton
_generator_instance: Optional[BlueprintGenerator] = None


def get_blueprint_generator() -> BlueprintGenerator:
    """Get the singleton BlueprintGenerator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = BlueprintGenerator()
    return _generator_instance
