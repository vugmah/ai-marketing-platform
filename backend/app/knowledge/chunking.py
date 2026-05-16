"""Semantic Chunking Engine.

Metni anlamli parcalara bolme motoru.
- NLP tabanli cumle sinirlari
- Baslik korumasi
- Token bazli chunk boyutu
- Semantic overlap
- Anahtar kelime ve entity cikarimi
"""

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# Basit Turkce stop words listesi
TURKISH_STOP_WORDS = {
    "acaba", "altmıs", "altı", "ama", "ancak", "arada", "aslında", "ayrıca",
    "bana", "bazı", "belki", "ben", "benden", "beni", "benim", "beri", "beş",
    "bile", "bin", "bir", "birçok", "biri", "birkaç", "birkez", "birşey",
    "birşeyi", "biz", "bize", "bizi", "bizim", "böyle", "böylece", "bu",
    "buna", "bunda", "bundan", "bunlar", "bunları", "bunların", "bunu",
    "bunun", "burada", "bütün", "çoğu", "çoğunu", "çok", "çünkü", "da",
    "daha", "dahi", "de", "defa", "değil", "diğer", "diğeri", "diğerleri",
    "diye", "doksan", "dokuz", "dolayı", "dolayısıyla", "dört", "edecek",
    "eden", "ederek", "edilecek", "ediliyor", "edilmesi", "ediyor", "eğer",
    "elli", "en", "etmesi", "etti", "ettiği", "ettiğini", "gibi", "göre",
    "halde", "halen", "hangi", "hatta", "hem", "henüz", "hep", "hepsi",
    "her", "herhangi", "herkes", "herkese", "herkesi", "herkesin", "hiç",
    "hiçbir", "için", "iki", "ile", "ilgili", "ise", "işte", "itibaren",
    "itibariyle", "kadar", "karşın", "katrilyon", "kendi", "kendilerine",
    "kendini", "kendisi", "kendisine", "kendisini", "kez", "ki", "kim",
    "kime", "kimi", "kimin", "kimse", "kırk", "milyar", "milyon", "mu",
    "mü", "mı", "nasıl", "ne", "neden", "nedenle", "nerde", "nerede",
    "nereye", "niye", "niçin", "o", "olan", "olarak", "oldu", "olduğu",
    "olduğunu", "olduklarını", "olmadı", "olmadığı", "olmak", "olması",
    "olmayan", "olmaz", "olsa", "olsun", "olup", "olur", "olursa", "oluyor",
    "on", "ona", "ondan", "onlar", "onlardan", "onları", "onların", "onu",
    "onun", "otuz", "oysa", "öyle", "pek", "rağmen", "sadece", "sanki",
    "sekiz", "seksen", "sen", "senden", "seni", "senin", "siz", "sizden",
    "sizi", "sizin", "şey", "şeyden", "şeyi", "şeyler", "şöyle", "şu",
    "şuna", "şunda", "şundan", "şunları", "şunu", "tarafından", "trilyon",
    "tüm", "üç", "üzere", "var", "vardı", "ve", "veya", "ya", "yani",
    "yapacak", "yapılan", "yapılması", "yapıyor", "yapmak", "yaptı",
    "yaptığı", "yaptığını", "yaptıkları", "yedi", "yerine", "yetmiş", "yine",
    "yirmi", "yoksa", "yüz", "zaten",
}


@dataclass
class ChunkMetadata:
    """Chunk metadata veri yapisi."""

    chunk_type: str = "paragraph"
    source_section: Optional[str] = None
    source_heading: Optional[str] = None
    sequence: int = 0
    token_count: int = 0
    char_count: int = 0
    keywords: List[str] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    semantic_tags: List[str] = field(default_factory=list)


@dataclass
class TextChunk:
    """Bir metin chunk'inin veri yapisi."""

    content: str
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    @property
    def content_hash(self) -> str:
        """Icerik hash'i uret."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class SemanticChunker:
    """Semantic chunking motoru.

    Metni anlamli parcalara boler:
    1. Cumle sinirlari tespit et
    2. Basliklari koru
    3. Token bazli boyutlandir
    4. Semantic overlap ekle
    5. Anahtar kelime cikar
    """

    # Varsayilan parametreler
    DEFAULT_CHUNK_SIZE: int = 512  # Hedef token sayisi
    DEFAULT_CHUNK_OVERLAP: int = 64  # Overlap token sayisi
    DEFAULT_PRESERVE_HEADINGS: bool = True

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        preserve_headings: bool = True,
        extract_keywords: bool = True,
        language: str = "tr",
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.preserve_headings = preserve_headings
        self.extract_keywords = extract_keywords
        self.language = language
        self._stop_words = TURKISH_STOP_WORDS if language == "tr" else set()

    def _estimate_token_count(self, text: str) -> int:
        """Basit token sayisi tahmini.

        Turkce icin ortalama 1.3 token/kelime varsayimi.
        """
        words = text.split()
        return int(len(words) * 1.3)

    def _split_into_sentences(self, text: str) -> List[str]:
        """Metni cumlelere boler.

        Turkce ve Ingilizce cumle ayirici.
        """
        # Cumle sonu karakterleri: . ! ?
        pattern = r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜa-zçğıöşü0-9])"
        sentences = re.split(pattern, text)
        # Bos cumleleri filtrele ve temizle
        return [s.strip() for s in sentences if s.strip()]

    def _detect_headings(self, text: str) -> List[Tuple[str, str]]:
        """Basliklari tespit et.

        Returns:
            List of (heading_text, context_after_heading) tuples.
        """
        headings = []
        # Markdown basliklari
        md_pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
        for match in md_pattern.finditer(text):
            heading = match.group(1).strip()
            start = match.end()
            # Baslik sonrasi icerik
            next_match = md_pattern.search(text, start)
            end = next_match.start() if next_match else len(text)
            context = text[start:end].strip()
            headings.append((heading, context))

        # ALL CAPS basliklar (min 3 kelime, max 10 kelime)
        caps_pattern = re.compile(r"^([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]{2,60}[A-ZÇĞİÖŞÜ])$", re.MULTILINE)
        for match in caps_pattern.finditer(text):
            heading = match.group(1).strip()
            start = match.end()
            end = len(text)
            # Sonraki bos satira kadar
            for i in range(start, min(start + 500, len(text))):
                if text[i:i + 2] == "\n\n":
                    end = i
                    break
            context = text[start:end].strip()
            if context:
                headings.append((heading, context))

        return headings

    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """Anahtar kelime cikarimi.

        Basit TF-based anahtar kelime cikarimi.
        """
        # Kelimeleri ayir ve temizle
        words = re.findall(r"\b[a-zçğıöşüA-ZÇĞİÖŞÜ]{3,}\b", text)
        words = [w.lower() for w in words if w.lower() not in self._stop_words]

        if not words:
            return []

        # Kelime frekanslari
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        # En sik gecen kelimeleri sirala
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Basit entity cikarimi.

        Buyuk harfli kelime gruplarini entity olarak tespit eder.
        """
        entities = []

        # Kisi isimleri (basit pattern)
        person_pattern = re.compile(
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\b"
        )
        for match in person_pattern.finditer(text):
            name = match.group(1)
            if len(name) > 5:  # Kisa eslesmeleri filtrele
                entities.append({
                    "text": name,
                    "type": "PERSON",
                    "start": match.start(),
                    "end": match.end(),
                })

        # Kurum/Sirket isimleri
        org_pattern = re.compile(
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]*\s+(?:A\.Ş\.|Ltd\.|Inc\.|Corp\.|Şirketi|Kurumu|Bankası|Holding))\b"
        )
        for match in org_pattern.finditer(text):
            entities.append({
                "text": match.group(1),
                "type": "ORGANIZATION",
                "start": match.start(),
                "end": match.end(),
            })

        # Tarihler
        date_pattern = re.compile(
            r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
        )
        for match in date_pattern.finditer(text):
            entities.append({
                "text": match.group(1),
                "type": "DATE",
                "start": match.start(),
                "end": match.end(),
            })

        # Para birimleri
        money_pattern = re.compile(
            r"\b([\d.,]+\s*(?:TL|USD|EUR|₺|\$|€))\b"
        )
        for match in money_pattern.finditer(text):
            entities.append({
                "text": match.group(1),
                "type": "MONEY",
                "start": match.start(),
                "end": match.end(),
            })

        return entities

    def _get_semantic_tags(self, text: str) -> List[str]:
        """Semantic etiketler cikar.

        Metin turunu belirlemeye yardimci etiketler.
        """
        tags = []

        if re.search(r"\b(hakkımızda|about us|biz kimiz|misyon|vizyon)\b", text, re.IGNORECASE):
            tags.append("brand_info")

        if re.search(r"\b(ürün|product|hizmet|service|çözüm|solution)\b", text, re.IGNORECASE):
            tags.append("product_service")

        if re.search(r"\b(iletişim|contact|adres|telefon|email|e-posta)\b", text, re.IGNORECASE):
            tags.append("contact_info")

        if re.search(r"\b(kampanya|campaign|indirim|discount|fırsat|offer)\b", text, re.IGNORECASE):
            tags.append("campaign")

        if re.search(r"\b(değer|value|ilke|principle|etik|ethical)\b", text, re.IGNORECASE):
            tags.append("values")

        if re.search(r"\b(ekip|team|çalışan|personel|insan kaynakları)\b", text, re.IGNORECASE):
            tags.append("team")

        if len(text) < 100:
            tags.append("short_text")

        if len(text) > 1000:
            tags.append("long_text")

        return tags

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Metni paragraflara boler."""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _create_chunks_from_paragraphs(
        self,
        paragraphs: List[str],
        heading: Optional[str] = None,
    ) -> List[TextChunk]:
        """Paragraflardan semantic chunk'lar olustur.

        Paragraflari birlestirerek hedef token boyutuna ulasir,
        overlap ekler.
        """
        chunks: List[TextChunk] = []
        current_buffer: List[str] = []
        current_tokens = 0
        sequence = 0

        for para in paragraphs:
            para_tokens = self._estimate_token_count(para)

            if para_tokens > self.chunk_size:
                # Paragraf cok buyuk - cumlelere bol
                sentences = self._split_into_sentences(para)
                for sent in sentences:
                    sent_tokens = self._estimate_token_count(sent)

                    if current_tokens + sent_tokens > self.chunk_size and current_buffer:
                        # Chunk'i kaydet
                        chunk_text = " ".join(current_buffer)
                        chunks.append(self._create_chunk(
                            chunk_text, sequence, heading, heading
                        ))
                        sequence += 1

                        # Overlap icin son parcalari tut
                        overlap_text = " ".join(current_buffer[-2:]) if len(current_buffer) >= 2 else " ".join(current_buffer)
                        overlap_tokens = self._estimate_token_count(overlap_text)

                        if overlap_tokens < self.chunk_overlap:
                            current_buffer = current_buffer[-2:]
                            current_tokens = overlap_tokens
                        else:
                            current_buffer = []
                            current_tokens = 0

                    current_buffer.append(sent)
                    current_tokens += sent_tokens
            else:
                if current_tokens + para_tokens > self.chunk_size and current_buffer:
                    # Chunk'i kaydet
                    chunk_text = " ".join(current_buffer)
                    chunks.append(self._create_chunk(
                        chunk_text, sequence, heading, heading
                    ))
                    sequence += 1

                    # Overlap
                    overlap_text = " ".join(current_buffer[-1:])
                    overlap_tokens = self._estimate_token_count(overlap_text)

                    if overlap_tokens < self.chunk_overlap:
                        current_buffer = current_buffer[-1:]
                        current_tokens = overlap_tokens
                    else:
                        current_buffer = []
                        current_tokens = 0

                current_buffer.append(para)
                current_tokens += para_tokens

        # Kalan buffer'i kaydet
        if current_buffer:
            chunk_text = " ".join(current_buffer)
            chunks.append(self._create_chunk(
                chunk_text, sequence, heading, heading
            ))

        return chunks

    def _create_chunk(
        self,
        content: str,
        sequence: int,
        heading: Optional[str] = None,
        section: Optional[str] = None,
    ) -> TextChunk:
        """Bir TextChunk olustur."""
        content = content.strip()
        token_count = self._estimate_token_count(content)
        char_count = len(content)

        metadata = ChunkMetadata(
            chunk_type="paragraph",
            source_heading=heading,
            source_section=section,
            sequence=sequence,
            token_count=token_count,
            char_count=char_count,
            keywords=self._extract_keywords(content) if self.extract_keywords else [],
            entities=self._extract_entities(content),
            semantic_tags=self._get_semantic_tags(content),
        )

        return TextChunk(content=content, metadata=metadata)

    def chunk_text(self, text: str) -> List[TextChunk]:
        """Metni semantic chunk'lara boler.

        Ana chunking fonksiyonu.

        Args:
            text: Chunk'lanacak metin.

        Returns:
            Semantic chunk listesi.
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        all_chunks: List[TextChunk] = []

        # Basliklari tespit et ve koru
        if self.preserve_headings:
            headings = self._detect_headings(text)

            if headings:
                for heading_text, context in headings:
                    heading_para = f"{heading_text}\n\n{context}"
                    paragraphs = self._split_by_paragraphs(heading_para)
                    heading_chunks = self._create_chunks_from_paragraphs(
                        paragraphs, heading=heading_text
                    )
                    # Ilk chunk'in tipini heading yap
                    if heading_chunks:
                        heading_chunks[0].metadata.chunk_type = "heading"
                    all_chunks.extend(heading_chunks)
            else:
                paragraphs = self._split_by_paragraphs(text)
                all_chunks = self._create_chunks_from_paragraphs(paragraphs)
        else:
            paragraphs = self._split_by_paragraphs(text)
            all_chunks = self._create_chunks_from_paragraphs(paragraphs)

        # Tek liste halinde ve sequence numaralarini yeniden ata
        final_chunks: List[TextChunk] = []
        for i, chunk in enumerate(all_chunks):
            chunk.metadata.sequence = i
            final_chunks.append(chunk)

        logger.info(
            "semantic_chunking_complete",
            chunk_count=len(final_chunks),
            total_chars=sum(c.metadata.char_count for c in final_chunks),
            total_tokens=sum(c.metadata.token_count for c in final_chunks),
        )

        return final_chunks

    def chunk_with_stats(self, text: str) -> Dict[str, Any]:
        """Chunk'la ve istatistikleri dondur.

        API response icin kullanilan fonksiyon.

        Returns:
            Dict with chunks list and statistics.
        """
        start_time = time.time()
        chunks = self.chunk_text(text)
        elapsed_ms = (time.time() - start_time) * 1000

        total_tokens = sum(c.metadata.token_count for c in chunks)
        total_chars = sum(c.metadata.char_count for c in chunks)
        avg_chunk_size = total_tokens / len(chunks) if chunks else 0

        chunk_dicts = []
        for chunk in chunks:
            chunk_dicts.append({
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "metadata": {
                    "chunk_type": chunk.metadata.chunk_type,
                    "sequence": chunk.metadata.sequence,
                    "token_count": chunk.metadata.token_count,
                    "char_count": chunk.metadata.char_count,
                    "keywords": chunk.metadata.keywords,
                    "entities": chunk.metadata.entities,
                    "semantic_tags": chunk.metadata.semantic_tags,
                    "source_section": chunk.metadata.source_section,
                    "source_heading": chunk.metadata.source_heading,
                }
            })

        return {
            "chunks": chunk_dicts,
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "total_chars": total_chars,
            "avg_chunk_size": round(avg_chunk_size, 2),
            "processing_time_ms": round(elapsed_ms, 2),
        }


class RecursiveChunker(SemanticChunker):
    """Recursive (ozyinelemeli) chunking strategisi.

    Once buyuk ayrimcilarla (paragraf), sonra kucuk ayrimcilarla
    (cumle) boler. Hiyerarsik yapi korunur.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        separators: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, **kwargs)
        self.separators = separators or [
            "\n\n",  # Paragraf
            "\n",     # Satir
            ". ",     # Cumle (nokta bosluk)
            "! ",     # Cumle (unlem)
            "? ",     # Cumle (soru)
            "; ",     # Noktali virgul
            ", ",     # Virgul
            " ",      # Kelime
        ]

    def _split_at_separator(self, text: str, separator: str) -> List[str]:
        """Belirli bir ayirici ile metni boler."""
        if separator == " ":
            parts = text.split()
        else:
            parts = text.split(separator)
        return [p.strip() for p in parts if p.strip()]

    def _merge_splits(self, splits: List[str]) -> List[TextChunk]:
        """Parcalari hedef boyuta gore birlestir."""
        chunks: List[TextChunk] = []
        current: List[str] = []
        current_tokens = 0
        sequence = 0

        for split in splits:
            split_tokens = self._estimate_token_count(split)

            if current_tokens + split_tokens > self.chunk_size and current:
                chunk_text = " ".join(current)
                chunks.append(self._create_chunk(chunk_text, sequence))
                sequence += 1

                # Overlap
                overlap_splits = []
                overlap_tokens = 0
                for s in reversed(current):
                    t = self._estimate_token_count(s)
                    if overlap_tokens + t > self.chunk_overlap:
                        break
                    overlap_splits.insert(0, s)
                    overlap_tokens += t

                current = overlap_splits
                current_tokens = overlap_tokens

            current.append(split)
            current_tokens += split_tokens

        if current:
            chunk_text = " ".join(current)
            chunks.append(self._create_chunk(chunk_text, sequence))

        return chunks

    def chunk_text(self, text: str) -> List[TextChunk]:
        """Recursive chunking uygula."""
        if not text or not text.strip():
            return []

        # Once en buyuk ayiriciyla dene
        for separator in self.separators:
            splits = self._split_at_separator(text, separator)
            if len(splits) > 1:
                return self._merge_splits(splits)

        # Hicbir ayirici islemediyse butun metin tek chunk
        return [self._create_chunk(text, 0)]


def get_chunker(
    strategy: str = "semantic",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    **kwargs: Any,
) -> SemanticChunker:
    """Chunker factory fonksiyonu.

    Args:
        strategy: "semantic" veya "recursive"
        chunk_size: Hedef token sayisi
        chunk_overlap: Overlap token sayisi
        **kwargs: Ek parametreler

    Returns:
        SemanticChunker instance.
    """
    if strategy == "recursive":
        return RecursiveChunker(chunk_size, chunk_overlap, **kwargs)
    return SemanticChunker(chunk_size, chunk_overlap, **kwargs)
