"""
Content Generator
==================
Generates AI-ready content prompts and placeholder content for sections.
Provides the interface between the blueprint system and AI content generation.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from schemas.enums import IndustryType, SectionType


class ContentGenerationRequest(BaseModel):
    """A request for AI content generation."""
    section_type: SectionType
    industry: IndustryType
    business_name: str
    business_description: Optional[str] = None
    tone: str = "professional"
    target_audience: Optional[str] = None
    max_length: int = 500
    language: str = "tr"
    context: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class ContentGenerator:
    """
    Generates content prompts and placeholder content for website sections.
    This module prepares the structured input that an AI would use to generate
    actual website content (headlines, descriptions, etc.).
    """

    def __init__(self):
        self._prompt_templates = self._load_prompt_templates()

    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load AI prompt templates for each section type."""
        return {
            SectionType.HERO.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründe faaliyet gösteren '{business_name}' işletmesi için hero bölümü içeriği oluştur.

İşletme açıklaması: {business_description}
Hedef kitle: {target_audience}

Lütfen şu alanları doldur:
- headline: Ana başlık (kısa, etkileyici, max 60 karakter)
- subheadline: Alt başlık (açıklayıcı, max 120 karakter)
- primary_cta: Ana buton metni (eylem kelimesi, max 20 karakter)
- secondary_cta: İkincil buton metni (max 20 karakter)

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
- SEO dostu olmalı
- Hedef kitleye hitap etmeli
""",
            SectionType.ABOUT.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründeki '{business_name}' için hakkımızda bölümü içeriği oluştur.

İşletme açıklaması: {business_description}

Lütfen şu alanları doldur:
- title: Bölüm başlığı (max 40 karakter)
- subtitle: Alt başlık (max 80 karakter)
- description: Paragraf (2-3 cümle, max 300 karakter)

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
- Güven verici ve samimi olmalı
""",
            SectionType.SERVICES.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründeki '{business_name}' için hizmetler bölümü içeriği oluştur.

İşletme açıklaması: {business_description}

Lütfen şu alanları doldur:
- title: Bölüm başlığı
- subtitle: Alt başlık
- description: Genel açıklama
- items: 3-6 hizmet maddesi (her biri: title, description, icon)

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
- Her hizmet max 150 karakter açıklama
""",
            SectionType.TESTIMONIALS.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründeki '{business_name}' için müşteri yorumları oluştur.

İşletme açıklaması: {business_description}
Hedef kitle: {target_audience}

Lütfen 3-4 gerçekçi müşteri yorumu oluştur:
- Her yorumda: isim, rol, puan (1-5), yorum metni
- Yorumlar gerçekçi ve çeşitli olmalı
- Hem olumlu hem küçük eleştiri içerebilir

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
""",
            SectionType.CONTACT.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründeki '{business_name}' için iletişim bölümü içeriği oluştur.

Lütfen şu alanları doldur:
- title: Bölüm başlığı
- subtitle: Alt başlık
- description: Kısa açıklama
- form_title: Form başlığı
- submit_button_text: Gönder butonu metni
- success_message: Başarılı gönderim mesajı

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
""",
            SectionType.CTA.value: """
{language} dilinde, {tone} bir üslupla, {industry} sektöründeki '{business_name}' için CTA bölümü içeriği oluştur.

İşletme açıklaması: {business_description}
Hedef kitle: {target_audience}

Lütfen şu alanları doldur:
- headline: CTA başlığı (dikkat çekici, max 60 karakter)
- description: Açıklama (max 150 karakter)
- primary_cta: Ana buton metni (max 25 karakter)
- urgency_text: Aciliyet metni (varsa, max 50 karakter)

Kısıtlamalar:
- Toplam uzunluk: {max_length} karakter
- Eylem odaklı olmalı
- Aciliyet hissi vermeli
""",
        }

    def generate_prompt(self, request: ContentGenerationRequest) -> str:
        """
        Generate an AI content generation prompt from a request.

        Args:
            request: Content generation request

        Returns:
            Formatted prompt string ready for AI
        """
        template = self._prompt_templates.get(
            request.section_type.value,
            self._prompt_templates.get(SectionType.HERO.value, ""),
        )

        return template.format(
            language=request.language,
            tone=request.tone,
            industry=request.industry.value,
            business_name=request.business_name,
            business_description=request.business_description or "Belirtilmemiş",
            target_audience=request.target_audience or "Genel kitle",
            max_length=request.max_length,
            context=str(request.context or {}),
        )

    def generate_placeholder_content(
        self,
        section_type: SectionType,
        industry: IndustryType,
        business_name: str = "İşletmem",
    ) -> Dict[str, Any]:
        """
        Generate placeholder content for a section.
        Used when AI content generation is not available.

        Args:
            section_type: Type of section
            industry: Business industry
            business_name: Business name

        Returns:
            Placeholder content dict
        """
        placeholders = {
            SectionType.HERO.value: {
                "headline": f"{business_name}'e Hoş Geldiniz",
                "subheadline": f"{industry.value} sektöründe kaliteli hizmet.",
                "primary_cta": "Başlayın",
                "secondary_cta": "Daha Fazla",
            },
            SectionType.ABOUT.value: {
                "title": "Hakkımızda",
                "subtitle": "Biz Kimiz?",
                "description": f"{business_name}, {industry.value} sektöründe yılların deneyimiyle hizmet vermektedir.",
            },
            SectionType.SERVICES.value: {
                "title": "Hizmetlerimiz",
                "subtitle": "Neler Sunuyoruz?",
                "description": "Size özel çözümler sunuyoruz.",
                "items": [
                    {"title": "Hizmet 1", "description": "Kaliteli hizmet açıklaması.", "icon": "star"},
                    {"title": "Hizmet 2", "description": "Profesyonel çözüm sunumu.", "icon": "check"},
                    {"title": "Hizmet 3", "description": "Müşteri odaklı yaklaşım.", "icon": "heart"},
                ],
            },
            SectionType.TESTIMONIALS.value: {
                "title": "Müşteri Yorumları",
                "subtitle": "Bizi Değerlendirin",
                "testimonials": [
                    {"name": "Ahmet Y.", "role": "Müşteri", "rating": 5, "text": "Çok memnun kaldım, kesinlikle tavsiye ederim."},
                    {"name": "Selin K.", "role": "Müşteri", "rating": 5, "text": "Harika bir deneyimdi. Personel çok ilgili."},
                ],
            },
            SectionType.CONTACT.value: {
                "title": "Bize Ulaşın",
                "subtitle": "Sorularınız mı var?",
                "description": "Size en kısa sürede dönüş yapacağız.",
                "submit_button_text": "Gönder",
                "success_message": "Mesajınız alındı! Teşekkür ederiz.",
            },
            SectionType.CTA.value: {
                "headline": "Hemen Başlayın",
                "description": "Size en iyi hizmeti sunmak için buradayız.",
                "primary_cta": "Bize Ulaşın",
                "primary_link": "#contact",
            },
            SectionType.FOOTER.value: {
                "logo_text": business_name,
                "tagline": "Kaliteli hizmet, güvenilir çözümler.",
                "columns": [
                    {"title": "Hızlı Linkler", "links": []},
                    {"title": "İletişim", "contact_info": {}},
                ],
            },
        }

        return placeholders.get(section_type.value, {
            "title": f"{section_type.value.title()}",
            "description": "İçerik hazırlanıyor...",
        })

    def batch_generate_prompts(
        self,
        business_name: str,
        industry: IndustryType,
        section_types: List[SectionType],
        tone: str = "professional",
        language: str = "tr",
    ) -> Dict[str, str]:
        """
        Generate content prompts for multiple sections at once.

        Args:
            business_name: Business name
            industry: Business industry
            section_types: List of sections to generate content for
            tone: Tone of voice
            language: Content language

        Returns:
            Dict mapping section type to prompt string
        """
        prompts = {}
        for section_type in section_types:
            request = ContentGenerationRequest(
                section_type=section_type,
                industry=industry,
                business_name=business_name,
                tone=tone,
                language=language,
            )
            prompts[section_type.value] = self.generate_prompt(request)

        return prompts


# Singleton
_generator_instance: Optional[ContentGenerator] = None


def get_content_generator() -> ContentGenerator:
    """Get the singleton ContentGenerator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ContentGenerator()
    return _generator_instance
