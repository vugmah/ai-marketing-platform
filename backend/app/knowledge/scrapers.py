"""Website Scraping Module.

BeautifulSoup ile web scraping, semantic chunking ve knowledge base'e kayit.
- Asenkron HTTP istekleri
- HTML parsing ve text extraction
- Link takibi (configurable depth)
- CSS selector destegi
- Rate limiting
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)

# Varsayilan header'lar
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# Icerik disi HTML elementleri
EXCLUDE_TAGS = {
    "script", "style", "noscript", "iframe", "canvas",
    "svg", "img", "video", "audio", "source", "track",
    "embed", "object", "param", "footer", "nav", "aside",
    "header"  # header nav bazen icerik olabilir, opsiyonel
}


@dataclass
class ScrapedPage:
    """Scrap edilmis sayfa veri yapisi."""

    url: str
    title: str = ""
    meta_description: str = ""
    content: str = ""
    headings: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    language: str = ""
    status_code: int = 200
    content_hash: str = ""
    scrape_time_ms: float = 0.0

    def to_knowledge_dict(self) -> Dict[str, Any]:
        """KnowledgeBase kayit formatina donustur."""
        return {
            "source_url": self.url,
            "source_title": self.title,
            "source_description": self.meta_description,
            "raw_content": self.content,
            "raw_content_hash": self.content_hash,
            "content_metadata": {
                "headings": self.headings,
                "link_count": len(self.links),
                "language": self.language,
                "status_code": self.status_code,
                "scrape_time_ms": self.scrape_time_ms,
            }
        }


class WebsiteScraper:
    """Website scraper sinifi.

    BeautifulSoup + httpx ile web scraping yapar.
    Rate limiting, depth control, ve content filtering saglar.
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 50,
        follow_links: bool = True,
        css_selector: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        timeout: float = 30.0,
        rate_limit: float = 0.5,  # saniye
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.follow_links = follow_links
        self.css_selector = css_selector
        self.exclude_patterns = exclude_patterns or []
        self.include_patterns = include_patterns or []
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.headers = headers or DEFAULT_HEADERS.copy()
        self._client: Optional[httpx.AsyncClient] = None
        self._scraped_urls: Set[str] = set()
        self._page_count = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP client olustur (lazy)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    def _is_valid_url(self, url: str, base_url: str) -> bool:
        """URL'nin scrape edilip edilmeyecegini kontrol et."""
        parsed = urlparse(url)
        base_parsed = urlparse(base_url)

        # Ayni domain kontrolu
        if parsed.netloc and parsed.netloc != base_parsed.netloc:
            return False

        # Protokol kontrolu
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return False

        # Exclude pattern kontrolu
        url_lower = url.lower()
        for pattern in self.exclude_patterns:
            if pattern.lower() in url_lower:
                return False

        # Include pattern kontrolu (varsa)
        if self.include_patterns:
            matched = any(p.lower() in url_lower for p in self.include_patterns)
            if not matched:
                return False

        # Daha once scrape edilmis mi
        if url in self._scraped_urls:
            return False

        return True

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """HTML'den temiz metin cikar.

        Script, style vb. elementleri kaldirir ve metni duzgun sekilde cikarir.
        """
        # Icerik disi elementleri kaldir
        for tag in soup.find_all(EXCLUDE_TAGS):
            tag.decompose()

        # CSS selector ile spesifik alan
        if self.css_selector:
            target = soup.select_one(self.css_selector)
            if target:
                return target.get_text(separator="\n", strip=True)

        # Ana icerik alani (article, main, div.content vb.)
        content_selectors = [
            "article", "main",
            "[role='main']",
            ".content", "#content",
            ".main-content", "#main-content",
            ".page-content", "#page-content",
            ".entry-content",
            ".post-content",
            ".article-body",
        ]

        for selector in content_selectors:
            target = soup.select_one(selector)
            if target:
                text = target.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # Fallback: body'den cikar
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    def _extract_meta(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Meta tag'lerden bilgi cikar."""
        meta = {}

        # Title
        title_tag = soup.find("title")
        meta["title"] = title_tag.get_text(strip=True) if title_tag else ""

        # Meta description
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag:
            meta["description"] = desc_tag.get("content", "")
        else:
            og_desc = soup.find("meta", attrs={"property": "og:description"})
            meta["description"] = og_desc.get("content", "") if og_desc else ""

        # Language
        html_tag = soup.find("html")
        meta["language"] = html_tag.get("lang", "") if html_tag else ""

        # Keywords
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        meta["keywords"] = keywords_tag.get("content", "") if keywords_tag else ""

        # OG title
        og_title = soup.find("meta", attrs={"property": "og:title"})
        meta["og_title"] = og_title.get("content", "") if og_title else ""

        return meta

    def _extract_headings(self, soup: BeautifulSoup) -> List[str]:
        """Basliklari (h1-h6) cikar."""
        headings = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                text = tag.get_text(strip=True)
                if text:
                    headings.append(f"H{level}: {text}")
        return headings

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Sayfa ici linkleri cikar."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            full_url = full_url.split("#")[0]  # Fragment kaldir
            if self._is_valid_url(full_url, base_url):
                links.append(full_url)
        return links

    async def scrape_page(self, url: str) -> ScrapedPage:
        """Tek sayfa scrape et.

        Args:
            url: Scrape edilecek URL.

        Returns:
            ScrapedPage veri yapisi.
        """
        start_time = time.time()
        self._scraped_urls.add(url)
        self._page_count += 1

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            # HTML parse
            soup = BeautifulSoup(response.text, "lxml")

            # Bilgi cikar
            meta = self._extract_meta(soup)
            text = self._extract_text(soup)
            headings = self._extract_headings(soup)
            links = self._extract_links(soup, url)

            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            elapsed_ms = (time.time() - start_time) * 1000

            page = ScrapedPage(
                url=url,
                title=meta.get("title", ""),
                meta_description=meta.get("description", ""),
                content=text,
                headings=headings,
                links=links,
                language=meta.get("language", ""),
                status_code=response.status_code,
                content_hash=content_hash,
                scrape_time_ms=elapsed_ms,
            )

            logger.info(
                "page_scraped",
                url=url,
                title=page.title[:50],
                content_length=len(text),
                links=len(links),
                time_ms=round(elapsed_ms, 2),
            )

            return page

        except httpx.HTTPStatusError as e:
            logger.warning(
                "page_scrape_http_error",
                url=url,
                status_code=e.response.status_code,
            )
            return ScrapedPage(url=url, status_code=e.response.status_code)

        except Exception as e:
            logger.error("page_scrape_error", url=url, error=str(e))
            return ScrapedPage(url=url, status_code=0)

    async def scrape_website(
        self,
        start_url: str,
        progress_callback: Optional[Any] = None,
    ) -> List[ScrapedPage]:
        """Website'i recursive scrape et.

        Args:
            start_url: Baslangic URL'si.
            progress_callback: Ilerleme raporu callback'i.

        Returns:
            ScrapedPage listesi.
        """
        self._scraped_urls.clear()
        self._page_count = 0

        pages: List[ScrapedPage] = []
        urls_to_scrape: List[Tuple[str, int]] = [(start_url, 0)]  # (url, depth)

        while urls_to_scrape and self._page_count < self.max_pages:
            url, depth = urls_to_scrape.pop(0)

            if url in self._scraped_urls:
                continue

            # Rate limit
            await asyncio.sleep(self.rate_limit)

            # Sayfayi scrape et
            page = await self.scrape_page(url)
            if page.status_code == 200 and page.content:
                pages.append(page)

                # Progress callback
                if progress_callback:
                    await progress_callback(
                        page_num=len(pages),
                        total=min(self.max_pages, len(urls_to_scrape) + len(pages)),
                        current_url=url,
                    )

                # Alt sayfalari ekle
                if self.follow_links and depth < self.max_depth:
                    for link in page.links:
                        if link not in [u for u, _ in urls_to_scrape]:
                            if self._is_valid_url(link, start_url):
                                urls_to_scrape.append((link, depth + 1))

        logger.info(
            "website_scrape_complete",
            start_url=start_url,
            pages_scraped=len(pages),
            total_urls=len(self._scraped_urls),
        )

        return pages

    async def scrape_single(self, url: str) -> ScrapedPage:
        """Tek sayfa scrape et (non-recursive).

        Args:
            url: Scrape edilecek URL.

        Returns:
            ScrapedPage.
        """
        self._scraped_urls.clear()
        self._page_count = 0
        return await self.scrape_page(url)

    async def close(self) -> None:
        """Client'i kapat."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False


# =============================================================================
# Sitemap Scraper
# =============================================================================

class SitemapScraper:
    """Sitemap.xml scraper.

    robots.txt ve sitemap.xml'den URL listesi cikarir.
    """

    @staticmethod
    async def from_sitemap(sitemap_url: str) -> List[str]:
        """Sitemap.xml'den URL'leri cikar.

        Args:
            sitemap_url: Sitemap URL.

        Returns:
            URL listesi.
        """
        urls = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(sitemap_url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "xml")

                # URL loc'lari bul
                for loc in soup.find_all("loc"):
                    url = loc.get_text(strip=True)
                    if url:
                        urls.append(url)

                logger.info("sitemap_parsed", url=sitemap_url, urls_found=len(urls))

        except Exception as e:
            logger.error("sitemap_parse_error", url=sitemap_url, error=str(e))

        return urls

    @staticmethod
    async def from_robots_txt(base_url: str) -> Optional[str]:
        """robots.txt'den sitemap URL'sini bul.

        Args:
            base_url: Website base URL.

        Returns:
            Sitemap URL veya None.
        """
        try:
            robots_url = urljoin(base_url, "/robots.txt")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    for line in response.text.split("\n"):
                        if line.lower().startswith("sitemap:"):
                            return line.split(":", 1)[1].strip()
        except Exception as e:
            logger.error("robots_txt_error", url=base_url, error=str(e))
        return None


# =============================================================================
# Factory
# =============================================================================

async def scrape_website(
    url: str,
    company_id: int,
    branch_id: Optional[int] = None,
    max_depth: int = 2,
    max_pages: int = 50,
    follow_links: bool = True,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Website scrape et ve knowledge dict listesi dondur.

    Convenience fonksiyonu - async olarak calisir.

    Returns:
        KnowledgeBase kayit formatinda dict listesi.
    """
    scraper = WebsiteScraper(
        max_depth=max_depth,
        max_pages=max_pages,
        follow_links=follow_links,
        **kwargs,
    )

    try:
        pages = await scraper.scrape_website(url)
        results = []
        for page in pages:
            if page.content:
                kd = page.to_knowledge_dict()
                kd["company_id"] = company_id
                kd["branch_id"] = branch_id
                kd["source_type"] = "website"
                results.append(kd)
        return results
    finally:
        await scraper.close()
