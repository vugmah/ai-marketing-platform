"""Visual Learning Module.

Gorsel analiz ve marka gorsel kimligi ogrenme.
- Dominant renk analizi
- Nesne tespiti (placeholder)
- Metin tespiti (OCR entegrasyonu)
- Brand element tespiti
- Kompozisyon analizi
- Stil etiketleri

Not: Gercek gorsel analiz icin Pillow, OpenCV gereklidir.
AI tabanli nesne tespiti icin (future): transformers/timm
"""

import hashlib
import io
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Renk Analizi
# =============================================================================

@dataclass
class ColorInfo:
    """Renk bilgisi."""

    hex_code: str
    rgb: Tuple[int, int, int]
    percentage: float = 0.0
    color_name: str = ""


@dataclass
class VisualAnalysis:
    """Gorsel analiz sonucu."""

    description: str = ""
    dominant_colors: List[ColorInfo] = field(default_factory=list)
    detected_objects: List[str] = field(default_factory=list)
    detected_text: str = ""
    brand_elements: List[str] = field(default_factory=list)
    composition_analysis: Dict[str, Any] = field(default_factory=dict)
    style_tags: List[str] = field(default_factory=list)
    is_brand_asset: bool = False
    brand_relevance_score: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "dominant_colors": [
                {"hex": c.hex_code, "rgb": c.rgb, "percentage": c.percentage, "name": c.color_name}
                for c in self.dominant_colors
            ],
            "detected_objects": self.detected_objects,
            "detected_text": self.detected_text,
            "brand_elements": self.brand_elements,
            "composition_analysis": self.composition_analysis,
            "style_tags": self.style_tags,
            "is_brand_asset": self.is_brand_asset,
            "brand_relevance_score": self.brand_relevance_score,
        }


class ColorAnalyzer:
    """Renk analiz motoru.

    Gorselden dominant renkleri cikarir.
    Pillow kullanarak k-means benzeri renk kumeleme yapar.
    """

    # Bilinen renk isimleri
    COLOR_NAMES = {
        (255, 0, 0): "red", (0, 128, 0): "green", (0, 0, 255): "blue",
        (255, 255, 0): "yellow", (255, 165, 0): "orange", (128, 0, 128): "purple",
        (0, 0, 0): "black", (255, 255, 255): "white", (128, 128, 128): "gray",
        (255, 192, 203): "pink", (165, 42, 42): "brown", (0, 255, 255): "cyan",
        (255, 0, 255): "magenta", (0, 128, 128): "teal", (0, 0, 128): "navy",
        (128, 128, 0): "olive", (128, 0, 0): "maroon", (255, 215, 0): "gold",
        (192, 192, 192): "silver", (255, 127, 80): "coral", (255, 140, 0): "darkorange",
    }

    TURKISH_COLOR_NAMES = {
        "red": "kirmizi", "green": "yesil", "blue": "mavi", "yellow": "sari",
        "orange": "turuncu", "purple": "mor", "black": "siyah", "white": "beyaz",
        "gray": "gri", "pink": "pembe", "brown": "kahverengi", "cyan": "camgobegi",
        "magenta": "macenta", "teal": "camgobegi", "navy": "lacivert",
        "olive": "zeytinyesili", "maroon": "bordo", "gold": "altin",
        "silver": "gumus", "coral": "mercan", "darkorange": "koyu turuncu",
    }

    def __init__(self, num_colors: int = 5) -> None:
        self.num_colors = num_colors

    def _find_closest_color_name(self, rgb: Tuple[int, int, int]) -> str:
        """En yakin renk ismini bul."""
        min_dist = float("inf")
        closest_name = "unknown"
        for known_rgb, name in self.COLOR_NAMES.items():
            dist = sum((a - b) ** 2 for a, b in zip(rgb, known_rgb))
            if dist < min_dist:
                min_dist = dist
                closest_name = name
        return closest_name

    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """RGB'den hex kodu uret."""
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def analyze_image(self, image_bytes: bytes) -> List[ColorInfo]:
        """Gorselden dominant renkleri cikar.

        Placeholder - gercek implementasyon Pillow ile.

        Args:
            image_bytes: Gorsel dosya icerigi.

        Returns:
            ColorInfo listesi.
        """
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))

            # Kucult hizli islem icin
            image.thumbnail((150, 150))

            # RGB'ye cevir
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Piksel listesi
            pixels = list(image.getdata())
            total_pixels = len(pixels)

            # Basit renk kumeleme (quantization)
            # 64 renk bucket'i (4-bit per channel)
            color_buckets: Dict[Tuple[int, int, int], int] = {}
            for r, g, b in pixels:
                bucket = (r // 64 * 64, g // 64 * 64, b // 64 * 64)
                color_buckets[bucket] = color_buckets.get(bucket, 0) + 1

            # En sik renkleri sirala
            sorted_colors = sorted(color_buckets.items(), key=lambda x: x[1], reverse=True)

            colors = []
            for i, (rgb, count) in enumerate(sorted_colors[:self.num_colors]):
                pct = count / total_pixels * 100
                name = self._find_closest_color_name(rgb)
                turkish_name = self.TURKISH_COLOR_NAMES.get(name, name)
                colors.append(ColorInfo(
                    hex_code=self._rgb_to_hex(rgb),
                    rgb=rgb,
                    percentage=round(pct, 2),
                    color_name=turkish_name,
                ))

            return colors

        except ImportError:
            logger.warning("Pillow not installed - color analysis disabled")
            return []
        except Exception as e:
            logger.error("color_analysis_error", error=str(e))
            return []

    def analyze_image_url(self, image_url: str) -> List[ColorInfo]:
        """URL'den gorsel al ve renk analizi yap."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(image_url)
                response.raise_for_status()
                return self.analyze_image(response.content)
        except Exception as e:
            logger.error("image_fetch_error", url=image_url, error=str(e))
            return []


# =============================================================================
# Nesne Tespiti (Placeholder)
# =============================================================================

class ObjectDetector:
    """Nesne tespiti (Placeholder).

    Future: transformers/timm ile gercek nesne tespiti.
    Mevcut: Basit keyword-based tespit.
    """

    # Bilinen brand nesneleri
    BRAND_OBJECTS = {
        "logo": ["logo", "marka", "amblem", "sembol"],
        "product": ["urun", "product", "item", "esya"],
        "person": ["insan", "kisi", "person", "model", "manken"],
        "building": ["bina", "ofis", "store", "magaza", "showroom"],
        "nature": ["dogal", "nature", "organic", "organik"],
        "tech": ["teknoloji", "technology", "digital", "digital"],
        "food": ["yemek", "food", "restoran", "restaurant"],
        "fashion": ["moda", "fashion", "giyim", "clothing", "textile"],
    }

    def detect_from_text(self, image_description: str) -> List[str]:
        """Metin aciklamasindan nesneleri tespit et."""
        if not image_description:
            return []

        desc_lower = image_description.lower()
        detected = []

        for obj_type, keywords in self.BRAND_OBJECTS.items():
            for kw in keywords:
                if kw in desc_lower:
                    detected.append(obj_type)
                    break

        return list(set(detected))

    def detect(self, image_bytes: bytes) -> List[str]:
        """Gorselden nesneleri tespit et (placeholder).

        Future: Vision transformer ile gercek nesne tespiti.
        """
        return []


# =============================================================================
# Kompozisyon Analizi
# =============================================================================

class CompositionAnalyzer:
    """Gorsel kompozisyon analizi.

    Gorsel duzenini analiz eder.
    """

    def analyze(self, image_bytes: bytes) -> Dict[str, Any]:
        """Kompozisyon analizi yap.

        Args:
            image_bytes: Gorsel dosya icerigi.

        Returns:
            Kompozisyon analizi dict.
        """
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size

            aspect_ratio = width / height if height > 0 else 1

            # Aspect ratio kategorisi
            ratio_category = "square"
            if aspect_ratio > 1.5:
                ratio_category = "landscape_wide"
            elif aspect_ratio > 1.1:
                ratio_category = "landscape"
            elif aspect_ratio < 0.7:
                ratio_category = "portrait_tall"
            elif aspect_ratio < 0.9:
                ratio_category = "portrait"

            # Boyut kategorisi
            size_category = "small"
            pixels = width * height
            if pixels > 2_000_000:
                size_category = "large"
            elif pixels > 500_000:
                size_category = "medium"

            return {
                "width": width,
                "height": height,
                "aspect_ratio": round(aspect_ratio, 3),
                "ratio_category": ratio_category,
                "size_category": size_category,
                "total_pixels": pixels,
                "orientation": "landscape" if width > height else "portrait" if height > width else "square",
            }

        except ImportError:
            return {}
        except Exception as e:
            logger.error("composition_analysis_error", error=str(e))
            return {}


# =============================================================================
# Stil Analizi
# =============================================================================

class StyleAnalyzer:
    """Gorsel stil analizi.

    Gorselin stil etiketlerini cikarir.
    """

    STYLE_TAGS = {
        "modern": ["modern", "cagdas", "contemporary", "sleek", "minimal", "clean"],
        "classic": ["classic", "klasik", "traditional", "vintage", "retro"],
        "minimalist": ["minimalist", "minimal", "sade", "simple", "clean"],
        "luxury": ["luxury", "luks", "premium", "elegant", "sophisticated"],
        "playful": ["playful", "fun", "colorful", "energetic", "dynamic"],
        "professional": ["professional", "profesyonel", "corporate", "kurumsal"],
        "natural": ["natural", "dogal", "organic", "rustic", "warm"],
        "tech": ["tech", "technology", "futuristic", "digital", "innovative"],
        "artistic": ["artistic", "sanatsal", "creative", "illustration"],
        "flat": ["flat design", "flat", "2d", "vector"],
        "photographic": ["photo", "photographic", "fotograf", "realistic"],
    }

    def analyze_from_text(self, description: str) -> List[str]:
        """Metin aciklamasindan stil etiketleri cikar."""
        if not description:
            return []

        desc_lower = description.lower()
        tags = []

        for tag_name, keywords in self.STYLE_TAGS.items():
            for kw in keywords:
                if kw in desc_lower:
                    tags.append(tag_name)
                    break

        return list(set(tags))

    def analyze_from_colors(self, colors: List[ColorInfo]) -> List[str]:
        """Renklerden stil etiketleri cikar."""
        tags = []
        color_names = [c.color_name for c in colors]

        if "black" in color_names and "white" in color_names and len(colors) <= 3:
            tags.append("minimalist")

        if "gold" in color_names or "silver" in color_names:
            tags.append("luxury")

        bright_colors = ["red", "yellow", "orange", "pink", "cyan"]
        if any(c in color_names for c in bright_colors):
            tags.append("vibrant")

        if len(colors) <= 2:
            tags.append("minimalist")

        return tags


# =============================================================================
# Ana Gorsel Analiz Motoru
# =============================================================================

class VisualAnalyzer:
    """Ana gorsel analiz motoru.

    Tum gorsel analiz bilesenlerini birlestirir.
    """

    def __init__(self) -> None:
        self.color_analyzer = ColorAnalyzer(num_colors=5)
        self.object_detector = ObjectDetector()
        self.composition_analyzer = CompositionAnalyzer()
        self.style_analyzer = StyleAnalyzer()

    async def analyze_image(
        self,
        image_url: str,
        company_id: int,
        branch_id: Optional[int] = None,
        detect_brand_elements: bool = True,
    ) -> VisualAnalysis:
        """Gorseli analiz et.

        Args:
            image_url: Gorsel URL.
            company_id: Sirket ID.
            branch_id: Sube ID (opsiyonel).
            detect_brand_elements: Brand element tespiti yap.

        Returns:
            VisualAnalysis sonucu.
        """
        start_time = time.time()

        # Gorseli indir
        image_bytes = await self._fetch_image(image_url)
        if not image_bytes:
            return VisualAnalysis(description="Failed to fetch image")

        # Renk analizi
        colors = self.color_analyzer.analyze_image(image_bytes)

        # Kompozisyon analizi
        composition = self.composition_analyzer.analyze(image_bytes)

        # Stil etiketleri
        style_tags = self.style_analyzer.analyze_from_colors(colors)

        # Brand element tespiti
        brand_elements = []
        is_brand_asset = False
        brand_relevance = 0.0

        if detect_brand_elements:
            brand_elements = self._detect_brand_elements(image_url, colors, style_tags)
            is_brand_asset = len(brand_elements) > 0
            brand_relevance = min(len(brand_elements) * 0.2 + (0.3 if colors else 0), 1.0)

        # Aciklama uret
        description = self._generate_description(colors, composition, style_tags, brand_elements)

        elapsed_ms = (time.time() - start_time) * 1000

        return VisualAnalysis(
            description=description,
            dominant_colors=colors,
            detected_objects=[],
            detected_text="",
            brand_elements=brand_elements,
            composition_analysis=composition,
            style_tags=style_tags,
            is_brand_asset=is_brand_asset,
            brand_relevance_score=round(brand_relevance, 4),
            processing_time_ms=round(elapsed_ms, 2),
        )

    async def _fetch_image(self, image_url: str) -> Optional[bytes]:
        """Gorseli indir."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error("image_fetch_error", url=image_url, error=str(e))
            return None

    def _detect_brand_elements(
        self,
        image_url: str,
        colors: List[ColorInfo],
        style_tags: List[str],
    ) -> List[str]:
        """Brand elementlerini tespit et."""
        elements = []

        # URL'den brand ipucu
        url_lower = image_url.lower()
        if "logo" in url_lower:
            elements.append("logo")
        if "banner" in url_lower:
            elements.append("banner")
        if "header" in url_lower:
            elements.append("header")
        if "hero" in url_lower:
            elements.append("hero_image")
        if "product" in url_lower or "urun" in url_lower:
            elements.append("product_image")
        if "team" in url_lower or "ekip" in url_lower:
            elements.append("team_photo")

        # Renklerden brand ipucu
        if any(c.color_name in ("gold", "silver") for c in colors):
            elements.append("premium_branding")

        # Stil'den brand ipucu
        if "minimalist" in style_tags and "luxury" in style_tags:
            elements.append("luxury_branding")

        return elements

    def _generate_description(
        self,
        colors: List[ColorInfo],
        composition: Dict[str, Any],
        style_tags: List[str],
        brand_elements: List[str],
    ) -> str:
        """Gorsel aciklamasi uret."""
        parts = []

        # Kompozisyon
        orientation = composition.get("orientation", "")
        size = composition.get("size_category", "")
        if orientation and size:
            parts.append(f"{size} {orientation} goruntu")

        # Renkler
        if colors:
            color_desc = ", ".join([c.color_name for c in colors[:3]])
            parts.append(f"baskin renkler: {color_desc}")

        # Stil
        if style_tags:
            parts.append(f"stil: {', '.join(style_tags)}")

        # Brand elementleri
        if brand_elements:
            parts.append(f"brand ogeleri: {', '.join(brand_elements)}")

        return "; ".join(parts) if parts else "Gorsel analiz edildi"

    async def analyze_batch(
        self,
        image_urls: List[str],
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> List[VisualAnalysis]:
        """Toplu gorsel analizi.

        Args:
            image_urls: Gorsel URL listesi.
            company_id: Sirket ID.
            branch_id: Sube ID.

        Returns:
            VisualAnalysis listesi.
        """
        results = []
        for url in image_urls:
            try:
                analysis = await self.analyze_image(url, company_id, branch_id)
                results.append(analysis)
            except Exception as e:
                logger.error("batch_analysis_error", url=url, error=str(e))
                results.append(VisualAnalysis(description=f"Error: {str(e)}"))
        return results


# =============================================================================
# Factory
# =============================================================================

async def analyze_image(
    image_url: str,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Gorsel analiz et ve dict dondur.

    Convenience fonksiyonu.

    Returns:
        VisualAnalysis dict formati.
    """
    analyzer = VisualAnalyzer()
    result = await analyzer.analyze_image(image_url, company_id, branch_id)
    return result.to_dict()
