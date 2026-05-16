"""Brand Learning Module.

Marka tonu, renkleri, degerleri, kisiligi ogrenme motoru.
- Metin tabanli marka analizi
- Ton tespiti (formal, informal, playful, professional)
- Deger cikarimi
- Renk paleti ogrenme
- Dil stili analizi
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Ton Analizi Sozlugu
# =============================================================================

TONE_INDICATORS = {
    "professional": {
        "keywords": [
            "musteri", "hizmet", "kalite", "guvenilir", "uzman", "profesyonel",
            "cozum", "destek", "sirket", "kurumsal", "b2b", "consulting",
            "strategy", "innovation", "excellence", "dedicated", "premium",
            "fark yaratan", "sektorunde lider", "yenilikci", "butunlesik",
        ],
        "patterns": [
            r"\b(profesyonel|kurumsal|uzman|sektor lideri)\b",
            r"\b(kaliteli hizmet|guvenilir cozum)\b",
        ],
        "emoji_usage": "low",
        "formality": 0.8,
    },
    "friendly": {
        "keywords": [
            "sizinle", "birlikte", "yardimci", "mutluluk", "sevgi", "sicak",
            "samimi", "arkadas", "aile", "hosgeldiniz", "merhaba", "selam",
            "friendly", "warm", "welcome", "together", "happy", "joy",
            "sizin icin", "yaninizda", "keyifli",
        ],
        "patterns": [
            r"\b(merhaba|hos geldiniz|sizinle)\b",
            r"\b(yaninizdayiz|birlikte)\b",
        ],
        "emoji_usage": "medium",
        "formality": 0.4,
    },
    "playful": {
        "keywords": [
            "eglence", "mukemmel", "super", "harika", "fantastik", "wow",
            "fun", "amazing", "awesome", "cool", "love", "crazy", "yolo",
            "eğlenceli", "mucize", "efsane", "bambaska", "cildir", "pop",
        ],
        "patterns": [
            r"\b(wow|omg|harika|efsane)\b",
            r"[!]{2,}",  # Birden fazla unlem
        ],
        "emoji_usage": "high",
        "formality": 0.2,
    },
    "authoritative": {
        "keywords": [
            "kesinlikle", "mutlaka", "en iyi", "tek", "lider", "numara",
            "guarantee", "proven", "best", "only", "number one", "top",
            "kesin cozum", "en guvenilir", "vazgecilmez", "mutlak",
            "tartismasiz", "suphesiz", "en basarili",
        ],
        "patterns": [
            r"\b(en iyi|tek|lider|numara)\b",
            r"\b(kesinlikle|mutlaka)\b",
        ],
        "emoji_usage": "low",
        "formality": 0.7,
    },
    "empathetic": {
        "keywords": [
            "anliyoruz", "hissedin", "ozel", "degerli", "onemli",
            "anlayis", "empati", "duygusal", "icinizden",
            "understand", "feel", "care", "important", "value", "special",
            "sizin yerinize", "dusunuyoruz", "onemsiyoruz", "hissettirin",
        ],
        "patterns": [
            r"\b(anliyoruz|hissedin|degerli)\b",
            r"\b(sizin icin|onemsiyoruz)\b",
        ],
        "emoji_usage": "medium",
        "formality": 0.5,
    },
    "minimalist": {
        "keywords": [
            "basit", "sade", "minimal", "temiz", "az", "oz",
            "simple", "clean", "minimal", "less", "essential", "pure",
            "rafinasyon", "saf", "ozunde", "klasik",
        ],
        "patterns": [
            r"\b(basit|sade|minimal|temiz)\b",
        ],
        "emoji_usage": "low",
        "formality": 0.6,
    },
}

# Renk isimleri -> Hex kodlari
COLOR_MAP = {
    # Temel renkler
    "kirmizi": "#FF0000", "red": "#FF0000", "yesil": "#008000", "green": "#008000",
    "mavi": "#0000FF", "blue": "#0000FF", "sari": "#FFFF00", "yellow": "#FFFF00",
    "turuncu": "#FFA500", "orange": "#FFA500", "mor": "#800080", "purple": "#800080",
    "pembe": "#FFC0CB", "pink": "#FFC0CB", "kahverengi": "#8B4513", "brown": "#8B4513",
    "siyah": "#000000", "black": "#000000", "beyaz": "#FFFFFF", "white": "#FFFFFF",
    "gri": "#808080", "gray": "#808080", "turkuaz": "#40E0D0", "turquoise": "#40E0D0",
    "lacivert": "#000080", "navy": "#000080", "bordo": "#800020", "burgundy": "#800020",

    # Marka renkleri (Turk sirketler)
    "turkcell sari": "#FFCC00", "turkcell yellow": "#FFCC00",
    "turkcell mavi": "#0033A0", "turkcell blue": "#0033A0",
    "vodafone kirmizi": "#E60000", "vodafone red": "#E60000",
    "turk hava yollari kirmizi": "#C8102E", "thy red": "#C8102E",
    "arcelik turuncu": "#F47920", "arcelik orange": "#F47920",
    "vestel beyaz": "#FFFFFF", "vestel white": "#FFFFFF",
}


@dataclass
class BrandTone:
    """Marka ton analizi sonucu."""

    primary_tone: str = ""
    secondary_tone: str = ""
    formality_score: float = 0.5
    emoji_usage: str = "medium"
    avg_sentence_length: float = 0.0
    vocabulary_richness: float = 0.0
    confidence: float = 0.0


@dataclass
class BrandColor:
    """Marka rengi analizi sonucu."""

    hex_code: str = ""
    color_name: str = ""
    usage_area: str = ""
    confidence: float = 0.0


@dataclass
class BrandValues:
    """Marka degerleri analizi sonucu."""

    values: List[str] = field(default_factory=list)
    mission: str = ""
    vision: str = ""
    confidence: float = 0.0


@dataclass
class BrandAnalysis:
    """Tum brand analizi sonucu."""

    tone: BrandTone = field(default_factory=BrandTone)
    colors: List[BrandColor] = field(default_factory=list)
    values: BrandValues = field(default_factory=BrandValues)
    personality: Dict[str, Any] = field(default_factory=dict)
    slogans: List[str] = field(default_factory=list)
    target_audience: List[str] = field(default_factory=list)
    confidence: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone": {
                "primary": self.tone.primary_tone,
                "secondary": self.tone.secondary_tone,
                "formality_score": self.tone.formality_score,
                "emoji_usage": self.tone.emoji_usage,
                "avg_sentence_length": self.tone.avg_sentence_length,
                "vocabulary_richness": self.tone.vocabulary_richness,
                "confidence": self.tone.confidence,
            },
            "colors": [
                {
                    "hex": c.hex_code,
                    "name": c.color_name,
                    "usage_area": c.usage_area,
                    "confidence": c.confidence,
                }
                for c in self.colors
            ],
            "values": {
                "values": self.values.values,
                "mission": self.values.mission,
                "vision": self.values.vision,
                "confidence": self.values.confidence,
            },
            "personality": self.personality,
            "slogans": self.slogans,
            "target_audience": self.target_audience,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
        }


class BrandAnalyzer:
    """Marka analiz motoru.

    Metin ve gorsel icerikten marka profili cikarir.
    Ton, renk, deger, kisilik analizi yapar.
    """

    def __init__(self, language: str = "tr") -> None:
        self.language = language

    # =========================================================================
    # Ton Analizi
    # =========================================================================

    def analyze_tone(self, texts: List[str]) -> BrandTone:
        """Metinlerden marka tonunu analiz et.

        Args:
            texts: Analiz edilecek metin listesi.

        Returns:
            BrandTone analiz sonucu.
        """
        if not texts:
            return BrandTone()

        combined_text = " ".join(texts).lower()

        # Her ton icin skor hesapla
        tone_scores: Dict[str, float] = {}
        for tone_name, indicators in TONE_INDICATORS.items():
            score = 0.0

            # Keyword eslesmeleri
            for keyword in indicators["keywords"]:
                count = combined_text.count(keyword.lower())
                score += count * 1.0

            # Pattern eslesmeleri
            for pattern in indicators["patterns"]:
                matches = len(re.findall(pattern, combined_text))
                score += matches * 2.0

            tone_scores[tone_name] = score

        # Normalize
        max_score = max(tone_scores.values()) if tone_scores else 1
        if max_score > 0:
            tone_scores = {k: v / max_score for k, v in tone_scores.items()}

        # Sirala
        sorted_tones = sorted(tone_scores.items(), key=lambda x: x[1], reverse=True)

        primary_tone = sorted_tones[0][0] if sorted_tones else "neutral"
        secondary_tone = sorted_tones[1][0] if len(sorted_tones) > 1 else ""

        # Formality skoru
        formality = TONE_INDICATORS.get(primary_tone, {}).get("formality", 0.5)

        # Emoji kullanimi
        emoji_usage = TONE_INDICATORS.get(primary_tone, {}).get("emoji_usage", "medium")

        # Cumle uzunlugu
        all_sentences = []
        for text in texts:
            sentences = re.split(r"[.!?]+", text)
            all_sentences.extend(s.strip() for s in sentences if s.strip())
        avg_sentence_len = (
            sum(len(s.split()) for s in all_sentences) / len(all_sentences)
            if all_sentences else 0
        )

        # Kelime zenginligi
        all_words = combined_text.split()
        unique_words = set(all_words)
        vocab_richness = (
            len(unique_words) / len(all_words) if all_words else 0
        )

        # Confidence
        confidence = sorted_tones[0][1] if sorted_tones else 0.0

        return BrandTone(
            primary_tone=primary_tone,
            secondary_tone=secondary_tone,
            formality_score=formality,
            emoji_usage=emoji_usage,
            avg_sentence_length=round(avg_sentence_len, 2),
            vocabulary_richness=round(vocab_richness, 4),
            confidence=round(confidence, 4),
        )

    # =========================================================================
    # Renk Analizi
    # =========================================================================

    def extract_colors(self, texts: List[str]) -> List[BrandColor]:
        """Metinlerden renk bilgisi cikar.

        Args:
            texts: Analiz edilecek metin listesi.

        Returns:
            BrandColor listesi.
        """
        if not texts:
            return []

        combined_text = " ".join(texts).lower()
        colors_found = []

        # Renk isimlerini ara
        for color_name, hex_code in COLOR_MAP.items():
            count = combined_text.count(color_name.lower())
            if count > 0:
                # Usage area tespiti
                usage_area = self._detect_color_usage(combined_text, color_name)
                colors_found.append(BrandColor(
                    hex_code=hex_code,
                    color_name=color_name,
                    usage_area=usage_area,
                    confidence=min(0.5 + count * 0.1, 0.95),
                ))

        # Hex kodlarini dogrudan ara
        hex_pattern = re.compile(r"#([0-9A-Fa-f]{6})")
        for match in hex_pattern.finditer(combined_text):
            hex_code = f"#{match.group(1)}"
            if not any(c.hex_code == hex_code for c in colors_found):
                colors_found.append(BrandColor(
                    hex_code=hex_code,
                    color_name="",
                    usage_area="detected",
                    confidence=0.9,
                ))

        # Tekrar edenleri kaldir (hex bazli)
        unique_colors = {}
        for c in colors_found:
            if c.hex_code not in unique_colors:
                unique_colors[c.hex_code] = c

        return list(unique_colors.values())

    def _detect_color_usage(self, text: str, color_name: str) -> str:
        """Rengin kullanim alanini tespit et."""
        # Context-based kullanim alani tespiti
        idx = text.find(color_name.lower())
        if idx == -1:
            return "general"

        context = text[max(0, idx - 50):idx + 50]

        if any(w in context for w in ["logo", "logosu", "marka"]):
            return "logo"
        if any(w in context for w in ["web", "site", "sayfa", "arkaplan", "background"]):
            return "website"
        if any(w in context for w in ["ambalaj", "paket", "kutu", "package"]):
            return "packaging"
        if any(w in context for w in ["urun", "product", "giyim", "clothing"]):
            return "product"
        return "general"

    # =========================================================================
    # Deger Analizi
    # =========================================================================

    def extract_values(self, texts: List[str]) -> BrandValues:
        """Metinlerden marka degerleri cikar.

        Args:
            texts: Analiz edilecek metin listesi.

        Returns:
            BrandValues analiz sonucu.
        """
        if not texts:
            return BrandValues()

        combined_text = " ".join(texts).lower()

        # Deger kelimeleri
        value_keywords = [
            "guven", "kalite", "yenilik", "musteri odakli", "surdrulebilirlik",
            "seffaflik", "durustluk", "tutku", "mukemmellik", "isbirligi",
            "sorumluluk", "insan odakli", "teknoloji", "gelecek", "gelisim",
            "trust", "quality", "innovation", "sustainability", "transparency",
            "integrity", "passion", "excellence", "collaboration",
        ]

        values_found = []
        for keyword in value_keywords:
            if keyword.lower() in combined_text:
                values_found.append(keyword)

        # Misyon tespiti
        mission = ""
        mission_patterns = [
            r"misyon(?:umuz|umuz)?[:\s]+([^\.\n]+)",
            r"mission[:\s]+([^\.\n]+)",
            r"amaç(?:ımız|ımız)?[:\s]+([^\.\n]+)",
            r"hedef(?:imiz|ımız)?[:\s]+([^\.\n]+)",
        ]
        for pattern in mission_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                mission = match.group(1).strip()
                break

        # Vizyon tespiti
        vision = ""
        vision_patterns = [
            r"vizyon(?:umuz|umuz)?[:\s]+([^\.\n]+)",
            r"vision[:\s]+([^\.\n]+)",
            r"gelecek[:\s]+vizyon(?:umuz|umuz)?[:\s]+([^\.\n]+)",
        ]
        for pattern in vision_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                vision = match.group(1).strip()
                break

        confidence = min(len(values_found) * 0.1 + 0.3, 0.95)

        return BrandValues(
            values=values_found,
            mission=mission,
            vision=vision,
            confidence=round(confidence, 4),
        )

    # =========================================================================
    # Slogan Tespiti
    # =========================================================================

    def extract_slogans(self, texts: List[str]) -> List[str]:
        """Metinlerden sloganlari tespit et."""
        if not texts:
            return []

        slogans = []
        combined_text = "\n".join(texts)

        # Tirnak icindeki kisa ifadeler
        quote_pattern = re.compile(r'[""]([^""]{5,60})[""]')
        for match in quote_pattern.finditer(combined_text):
            slogans.append(match.group(1).strip())

        # "Sloganimiz", "Slogan" kelimeleri
        slogan_pattern = re.compile(r"(?:slogan(?:ımız|ımız)?|slogan)[:\s]+([^\.\n]+)", re.IGNORECASE)
        for match in slogan_pattern.finditer(combined_text):
            slogans.append(match.group(1).strip())

        # All caps kisa ifadeler (potansial slogan)
        caps_pattern = re.compile(r"^([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s,]{5,50}[A-ZÇĞİÖŞÜ])$", re.MULTILINE)
        for match in caps_pattern.finditer(combined_text):
            candidate = match.group(1).strip()
            if len(candidate) < 60:
                slogans.append(candidate)

        return list(set(slogans))

    # =========================================================================
    # Hedef Kitle Analizi
    # =========================================================================

    def extract_target_audience(self, texts: List[str]) -> List[str]:
        """Metinlerden hedef kitle bilgisi cikar."""
        if not texts:
            return []

        combined_text = " ".join(texts).lower()
        audiences = []

        # Yas gruplari
        age_patterns = [
            (r"\b(\d{2}-\d{2}\s*yaş)\b", "age_range"),
            (r"\b(genç|genc|young)\b", "young"),
            (r"\b(yaşlı|yasli|older|senior)\b", "senior"),
            (r"\b(çocuk|cocuk|kid|children)\b", "children"),
        ]
        for pattern, label in age_patterns:
            if re.search(pattern, combined_text):
                audiences.append(label)

        # Cinsiyet
        gender_patterns = [
            (r"\b(kadın|kadin|women|female)\b", "women"),
            (r"\b(erkek|men|male)\b", "men"),
            (r"\b(üniseks|unisex)\b", "unisex"),
        ]
        for pattern, label in gender_patterns:
            if re.search(pattern, combined_text):
                audiences.append(label)

        # Gelir seviyesi
        income_patterns = [
            (r"\b(lüks|luks|luxury|premium|vip)\b", "luxury"),
            (r"\b(ekonomik|uygun|budget|affordable)\b", "budget"),
        ]
        for pattern, label in income_patterns:
            if re.search(pattern, combined_text):
                audiences.append(label)

        # Konum
        location_patterns = [
            (r"\b(yerel|yerli|local)\b", "local"),
            (r"\b(uluslararası|uluslararasi|global|international)\b", "global"),
        ]
        for pattern, label in location_patterns:
            if re.search(pattern, combined_text):
                audiences.append(label)

        return list(set(audiences))

    # =========================================================================
    # Tam Analiz
    # =========================================================================

    def analyze(self, texts: List[str]) -> BrandAnalysis:
        """Tam marka analizi yap.

        Args:
            texts: Analiz edilecek metin listesi (web sitesi, sosyal medya vb.).

        Returns:
            BrandAnalysis sonucu.
        """
        start_time = time.time()

        tone = self.analyze_tone(texts)
        colors = self.extract_colors(texts)
        values = self.extract_values(texts)
        slogans = self.extract_slogans(texts)
        target_audience = self.extract_target_audience(texts)

        # Kisilik ozetleme
        personality = {
            "primary_trait": tone.primary_tone,
            "formality_level": tone.formality_score,
            "communication_style": self._describe_communication_style(tone),
            "emotional_appeal": self._describe_emotional_appeal(tone),
        }

        # Genel confidence
        confidences = [
            tone.confidence,
            values.confidence,
            min(len(colors) * 0.2, 0.9),
        ]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        elapsed_ms = (time.time() - start_time) * 1000

        return BrandAnalysis(
            tone=tone,
            colors=colors,
            values=values,
            personality=personality,
            slogans=slogans,
            target_audience=target_audience,
            confidence=round(overall_confidence, 4),
            processing_time_ms=round(elapsed_ms, 2),
        )

    def _describe_communication_style(self, tone: BrandTone) -> str:
        """Iletisim stilini tanimla."""
        if tone.formality_score > 0.7:
            return "formal_corporate"
        elif tone.formality_score > 0.4:
            return "professional_friendly"
        else:
            return "casual_conversational"

    def _describe_emotional_appeal(self, tone: BrandTone) -> str:
        """Duygusal cekiciligi tanimla."""
        if tone.primary_tone in ("playful", "friendly"):
            return "emotional_engaging"
        elif tone.primary_tone in ("professional", "authoritative"):
            return "rational_trust"
        elif tone.primary_tone == "empathetic":
            return "deeply_emotional"
        else:
            return "balanced"


# =============================================================================
# Sosyal Medya Ton Ogrenme
# =============================================================================

class SocialToneLearner:
    """Sosyal medya gonderilerinden ton ogrenme.

    Gecmis gonderileri analiz ederek marka tonunu ogrenir.
    """

    def __init__(self, language: str = "tr") -> None:
        self.language = language
        self.analyzer = BrandAnalyzer(language=language)

    def learn_from_posts(self, posts: List[str], platform: Optional[str] = None) -> Dict[str, Any]:
        """Gonderilerden marka tonunu ogren.

        Args:
            posts: Sosyal medya gonderileri.
            platform: Platform adi (instagram, twitter vb.)

        Returns:
            Ogrenme sonucu dict.
        """
        if not posts:
            return {}

        analysis = self.analyzer.analyze(posts)

        # Emoji kullanimi
        emoji_count = 0
        for post in posts:
            emoji_count += len(re.findall(r"[\U00010000-\U0010ffff]", post))
        avg_emoji = emoji_count / len(posts)

        emoji_usage = "low"
        if avg_emoji > 3:
            emoji_usage = "high"
        elif avg_emoji > 0.5:
            emoji_usage = "medium"

        # Hashtag pattern
        hashtags: List[str] = []
        for post in posts:
            found = re.findall(r"#\w+", post)
            hashtags.extend(found)
        top_hashtags = list(set(hashtags))[:10]

        # CTA stili
        cta_patterns = [
            r"\b(tiklayin|tikla|click|basmak|bas)\b",
            r"\b(ziyaret edin|ziyaret et|visit|inceleyin)\b",
            r"\b(satin al|satin alin|buy|purchase)\b",
            r"\b(yorum yap|yorum|comment)\b",
            r"\b(begen|like|paylas|share)\b",
        ]
        cta_found = []
        for pattern in cta_patterns:
            if any(re.search(pattern, post, re.IGNORECASE) for post in posts):
                cta_found.append(pattern.split("|")[0].replace(r"\b", ""))

        # Ortalama etkilesim
        engagement_scores = []
        for post in posts:
            score = len(post) + len(re.findall(r"[\U00010000-\U0010ffff]", post)) * 2
            engagement_scores.append(score)
        avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0

        return {
            "tone": analysis.tone.to_dict() if hasattr(analysis.tone, 'to_dict') else {
                "primary": analysis.tone.primary_tone,
                "secondary": analysis.tone.secondary_tone,
                "formality_score": analysis.tone.formality_score,
            },
            "language_style": self._detect_language_style(posts),
            "emoji_usage": emoji_usage,
            "avg_emoji_per_post": round(avg_emoji, 2),
            "hashtag_pattern": top_hashtags,
            "call_to_action_style": cta_found[0] if cta_found else "none",
            "avg_sentence_length": analysis.tone.avg_sentence_length,
            "vocabulary_richness": analysis.tone.vocabulary_richness,
            "formality_score": analysis.tone.formality_score,
            "platform": platform,
            "post_count_analyzed": len(posts),
            "engagement_score": round(avg_engagement, 2),
        }

    def _detect_language_style(self, posts: List[str]) -> str:
        """Dil stilini tespit et."""
        combined = " ".join(posts).lower()

        # Genclik dili
        youth_markers = ["lan", "ya", "falan", "falan filan", "aynen", "kanka", "bro"]
        youth_score = sum(1 for m in youth_markers if m in combined)

        # Kurumsal dil
        corporate_markers = ["degerli", "saygilarimizla", "bilginize", "musteri", "hizmet"]
        corp_score = sum(1 for m in corporate_markers if m in combined)

        # Samimi dil
        friendly_markers = ["merhaba", "selam", "naber", "nasılsın", "hosgeldiniz"]
        friendly_score = sum(1 for m in friendly_markers if m in combined)

        if youth_score > corp_score and youth_score > friendly_score:
            return "youth_casual"
        elif corp_score > friendly_score:
            return "corporate_formal"
        elif friendly_score > 0:
            return "friendly_casual"
        return "neutral"
