"""Knowledge Ingestion - Celery Async Tasks.

Asenkron ingestion islemleri:
- Website scraping
- PDF/DOCX parsing
- Semantic chunking
- Embedding uretimi
- Brand learning
- Visual learning
- Campaign learning
- Full ingestion pipeline
"""

from typing import Any, Dict, List, Optional

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


# =============================================================================
# Task: Website Ingestion
# =============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_website_task(
    self,
    url: str,
    company_id: int,
    branch_id: Optional[int] = None,
    max_depth: int = 2,
    max_pages: int = 50,
    follow_links: bool = True,
    css_selector: Optional[str] = None,
    exclude_patterns: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Website scrape et ve knowledge base'e kaydet.

    Celery async task - website scraping islemini arka planda calistirir.

    Args:
        url: Scrape edilecek URL.
        company_id: Sirket ID.
        branch_id: Sube ID.
        max_depth: Tarama derinligi.
        max_pages: Maksimum sayfa sayisi.
        follow_links: Linkleri takip et.
        css_selector: CSS selector ile spesifik alan.
        exclude_patterns: Hariç tutulacak URL pattern'leri.
        include_patterns: Dahil edilecek URL pattern'leri.

    Returns:
        Task sonuc dict.
    """
    import asyncio

    logger.info(
        "website_scrape_task_started",
        task_id=self.request.id,
        url=url,
        company_id=company_id,
    )

    try:
        from app.knowledge.scrapers import WebsiteScraper

        async def _scrape():
            scraper = WebsiteScraper(
                max_depth=max_depth,
                max_pages=max_pages,
                follow_links=follow_links,
                css_selector=css_selector,
                exclude_patterns=exclude_patterns or [],
                include_patterns=include_patterns or [],
            )
            async with scraper:
                pages = await scraper.scrape_website(url)
                return [
                    page.to_knowledge_dict()
                    for page in pages
                    if page.content
                ]

        results = asyncio.run(_scrape())

        logger.info(
            "website_scrape_task_completed",
            task_id=self.request.id,
            pages_scraped=len(results),
        )

        return {
            "status": "completed",
            "task_id": self.request.id,
            "pages_scraped": len(results),
            "results": results[:5],  # Ilk 5 sayfa
        }

    except Exception as exc:
        logger.error(
            "website_scrape_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60)


# =============================================================================
# Task: Document Parsing
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def parse_document_task(
    self,
    file_content_b64: str,
    filename: str,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """PDF/DOCX parse et.

    Args:
        file_content_b64: Base64 encode edilmis dosya icerigi.
        filename: Dosya adi.
        company_id: Sirket ID.
        branch_id: Sube ID.

    Returns:
        Parse sonucu dict.
    """
    import base64

    logger.info(
        "document_parse_task_started",
        task_id=self.request.id,
        filename=filename,
        company_id=company_id,
    )

    try:
        from app.knowledge.parsers import DocumentParser

        file_bytes = base64.b64decode(file_content_b64)
        doc = DocumentParser.parse(file_bytes, filename)

        result = doc.to_knowledge_dict(company_id, branch_id)

        logger.info(
            "document_parse_task_completed",
            task_id=self.request.id,
            pages=doc.page_count,
            words=doc.word_count,
        )

        return {
            "status": "completed",
            "task_id": self.request.id,
            **result,
        }

    except Exception as exc:
        logger.error(
            "document_parse_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Semantic Chunking
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def semantic_chunking_task(
    self,
    kb_id: int,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    strategy: str = "semantic",
) -> Dict[str, Any]:
    """Semantic chunking yap.

    Args:
        kb_id: Knowledge base ID.
        chunk_size: Chunk boyutu (token).
        chunk_overlap: Overlap (token).
        strategy: Chunking strategisi (semantic/recursive).

    Returns:
        Chunking sonucu dict.
    """
    logger.info(
        "semantic_chunking_task_started",
        task_id=self.request.id,
        kb_id=kb_id,
    )

    try:
        import asyncio

        from app.database import AsyncSessionLocal
        from app.knowledge.service import KnowledgeService

        async def _chunk():
            async with AsyncSessionLocal() as db:
                service = KnowledgeService(db)
                return await service.run_chunking_pipeline(
                    kb_id=kb_id,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    strategy=strategy,
                )

        result = asyncio.run(_chunk())

        logger.info(
            "semantic_chunking_task_completed",
            task_id=self.request.id,
            chunks_created=result.get("chunks_created", 0),
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "semantic_chunking_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Embedding Generation
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def embedding_generation_task(
    self,
    kb_id: int,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> Dict[str, Any]:
    """Embedding uret.

    Args:
        kb_id: Knowledge base ID.
        model_name: Embedding model adi.
        batch_size: Batch boyutu.

    Returns:
        Embedding sonucu dict.
    """
    logger.info(
        "embedding_generation_task_started",
        task_id=self.request.id,
        kb_id=kb_id,
        model_name=model_name,
    )

    try:
        import asyncio

        from app.database import AsyncSessionLocal
        from app.knowledge.service import KnowledgeService

        async def _embed():
            async with AsyncSessionLocal() as db:
                service = KnowledgeService(db)
                return await service.run_embedding_pipeline(
                    kb_id=kb_id,
                    model_name=model_name,
                    batch_size=batch_size,
                )

        result = asyncio.run(_embed())

        logger.info(
            "embedding_generation_task_completed",
            task_id=self.request.id,
            embeddings_created=result.get("embeddings_created", 0),
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "embedding_generation_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Brand Learning
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def brand_learning_task(
    self,
    company_id: int,
    texts: List[str],
    branch_id: Optional[int] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """Metinlerden marka ogren.

    Args:
        company_id: Sirket ID.
        texts: Ogrenme metinleri.
        branch_id: Sube ID.
        source: Kaynak bilgisi.

    Returns:
        Ogrenme sonucu dict.
    """
    logger.info(
        "brand_learning_task_started",
        task_id=self.request.id,
        company_id=company_id,
        text_count=len(texts),
    )

    try:
        import asyncio

        from app.database import AsyncSessionLocal
        from app.knowledge.service import BrandService

        async def _learn():
            async with AsyncSessionLocal() as db:
                service = BrandService(db)
                return await service.learn_from_texts(
                    company_id=company_id,
                    texts=texts,
                    branch_id=branch_id,
                    source=source,
                )

        result = asyncio.run(_learn())

        logger.info(
            "brand_learning_task_completed",
            task_id=self.request.id,
            profiles_created=result.get("profiles_created", 0),
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "brand_learning_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Visual Learning
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def visual_learning_task(
    self,
    image_urls: List[str],
    company_id: int,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Gorselleri analiz et ve ogren.

    Args:
        image_urls: Gorsel URL listesi.
        company_id: Sirket ID.
        branch_id: Sube ID.

    Returns:
        Ogrenme sonucu dict.
    """
    logger.info(
        "visual_learning_task_started",
        task_id=self.request.id,
        company_id=company_id,
        image_count=len(image_urls),
    )

    try:
        import asyncio

        from app.database import AsyncSessionLocal
        from app.knowledge.visual_learning import VisualAnalyzer

        async def _analyze():
            analyzer = VisualAnalyzer()
            results = await analyzer.analyze_batch(
                image_urls=image_urls,
                company_id=company_id,
                branch_id=branch_id,
            )

            # Brand asset'leri kaydet
            async with AsyncSessionLocal() as db:
                from app.knowledge.service import VisualLearningService
                service = VisualLearningService(db)

                for i, url in enumerate(image_urls):
                    if i < len(results):
                        try:
                            analysis = results[i]
                            asset = await service.create_asset(
                                company_id=company_id,
                                image_url=url,
                                branch_id=branch_id,
                            )
                            asset.description = analysis.description
                            asset.dominant_colors = [
                                {"hex": c.hex_code, "rgb": c.rgb, "percentage": c.percentage}
                                for c in analysis.dominant_colors
                            ]
                            asset.brand_elements = analysis.brand_elements
                            asset.style_tags = analysis.style_tags
                            asset.is_brand_asset = 1 if analysis.is_brand_asset else 0
                            asset.brand_relevance_score = analysis.brand_relevance_score
                        except Exception as e:
                            logger.warning("visual_save_error", url=url, error=str(e))

                await db.commit()

            return {
                "images_analyzed": len(results),
                "brand_assets_found": sum(1 for r in results if r.is_brand_asset),
            }

        result = asyncio.run(_analyze())

        logger.info(
            "visual_learning_task_completed",
            task_id=self.request.id,
            **result,
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "visual_learning_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Campaign Learning
# =============================================================================

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def campaign_learning_task(
    self,
    company_id: int,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Kampanyalardan ogren.

    Args:
        company_id: Sirket ID.
        branch_id: Sube ID.

    Returns:
        Ogrenme sonucu dict.
    """
    logger.info(
        "campaign_learning_task_started",
        task_id=self.request.id,
        company_id=company_id,
    )

    try:
        import asyncio

        from app.database import AsyncSessionLocal
        from app.knowledge.service import CampaignLearningService

        async def _learn():
            async with AsyncSessionLocal() as db:
                service = CampaignLearningService(db)
                return await service.learn_from_campaigns(
                    company_id=company_id,
                    branch_id=branch_id,
                )

        result = asyncio.run(_learn())

        logger.info(
            "campaign_learning_task_completed",
            task_id=self.request.id,
            campaigns_analyzed=result.get("campaigns_analyzed", 0),
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "campaign_learning_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30)


# =============================================================================
# Task: Full Ingestion Pipeline
# =============================================================================

@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def full_ingestion_pipeline_task(
    self,
    url: str,
    company_id: int,
    branch_id: Optional[int] = None,
    source_type: str = "website",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    learn_brand: bool = True,
    max_depth: int = 2,
    max_pages: int = 50,
) -> Dict[str, Any]:
    """Tam ingestion pipeline.

    1. Website scrape et (veya dosya parse et)
    2. Knowledge base olustur
    3. Semantic chunking
    4. Embedding uret
    5. Brand learning (istege bagli)

    Args:
        url: Kaynak URL.
        company_id: Sirket ID.
        branch_id: Sube ID.
        source_type: Kaynak tipi (website/pdf/docx).
        chunk_size: Chunk boyutu.
        chunk_overlap: Overlap.
        model_name: Embedding modeli.
        learn_brand: Brand learning yap.
        max_depth: Tarama derinligi.
        max_pages: Maksimum sayfa.

    Returns:
        Pipeline sonucu dict.
    """
    import asyncio

    from app.database import AsyncSessionLocal
    from app.knowledge.models import IngestionSource

    logger.info(
        "full_ingestion_pipeline_started",
        task_id=self.request.id,
        url=url,
        company_id=company_id,
    )

    try:
        async def _pipeline():
            async with AsyncSessionLocal() as db:
                from app.knowledge.service import KnowledgeService

                service = KnowledgeService(db)

                # Adim 1: Icerik al
                raw_content = ""
                source_title = ""
                source_description = ""

                if source_type == IngestionSource.WEBSITE.value:
                    from app.knowledge.scrapers import WebsiteScraper
                    scraper = WebsiteScraper(max_depth=max_depth, max_pages=max_pages)
                    async with scraper:
                        pages = await scraper.scrape_website(url)
                        raw_content = "\n\n".join(p.content for p in pages if p.content)
                        source_title = pages[0].title if pages else url
                        source_description = pages[0].meta_description if pages else ""

                elif source_type in (IngestionSource.PDF.value, IngestionSource.DOCX.value):
                    # Dosya parsing placeholder
                    raw_content = f"[File content from {url}]"
                    source_title = url.split("/")[-1] if "/" in url else url

                # Adim 2: Knowledge base olustur
                kb = await service.create_knowledge_base(
                    company_id=company_id,
                    branch_id=branch_id,
                    source_type=IngestionSource(source_type),
                    source_url=url,
                    source_title=source_title,
                    source_description=source_description,
                    raw_content=raw_content,
                )

                # Adim 3: Chunking
                if raw_content:
                    chunk_result = await service.run_chunking_pipeline(
                        kb_id=kb.id,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )

                    # Adim 4: Embedding
                    emb_result = await service.run_embedding_pipeline(
                        kb_id=kb.id,
                        model_name=model_name,
                    )
                else:
                    chunk_result = {"chunks_created": 0}
                    emb_result = {"embeddings_created": 0}

                # Adim 5: Brand learning
                if learn_brand and raw_content:
                    from app.knowledge.service import BrandService
                    brand_service = BrandService(db)
                    brand_result = await brand_service.learn_from_texts(
                        company_id=company_id,
                        texts=[raw_content],
                        branch_id=branch_id,
                        source=url,
                    )
                else:
                    brand_result = {"profiles_created": 0}

                return {
                    "kb_id": kb.id,
                    "chunks_created": chunk_result.get("chunks_created", 0),
                    "embeddings_created": emb_result.get("embeddings_created", 0),
                    "brand_profiles_created": brand_result.get("profiles_created", 0),
                }

        result = asyncio.run(_pipeline())

        logger.info(
            "full_ingestion_pipeline_completed",
            task_id=self.request.id,
            **result,
        )

        return {"status": "completed", "task_id": self.request.id, **result}

    except Exception as exc:
        logger.error(
            "full_ingestion_pipeline_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60)
