"""Knowledge Ingestion - FastAPI Router.

API Endpoints:
    - Knowledge Base CRUD
    - Website Ingestion
    - File Ingestion (PDF/DOCX)
    - Semantic Chunking
    - Embedding Generation
    - Semantic Search
    - Brand Learning
    - Visual Learning
    - Campaign Learning
    - Company Memory
    - Ingestion Jobs
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.database import get_db
from app.knowledge import schemas as knowledge_schemas
from app.knowledge.embeddings import get_embedding_pipeline
from app.knowledge.ocr import OCRProcessor
from app.knowledge.service import (
    BrandService,
    CampaignLearningService,
    IngestionJobService,
    KnowledgeService,
    VisualLearningService,
)
from app.knowledge.tasks import (
    brand_learning_task,
    campaign_learning_task,
    embedding_generation_task,
    full_ingestion_pipeline_task,
    parse_document_task,
    scrape_website_task,
    semantic_chunking_task,
    visual_learning_task,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Ingestion"])


# =============================================================================
# Knowledge Base CRUD
# =============================================================================

@router.post("/bases", response_model=knowledge_schemas.KnowledgeBaseResponse)
async def create_knowledge_base(
    request: knowledge_schemas.KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Knowledge base kaydi olustur."""
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(
        company_id=request.company_id,
        source_type=request.source_type,
        source_url=request.source_url,
        source_title=request.source_title,
        source_description=request.source_description,
        raw_content=request.raw_content,
        branch_id=request.branch_id,
        content_metadata=request.content_metadata,
    )
    return kb.to_dict()


@router.get("/bases/{kb_id}", response_model=knowledge_schemas.KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Knowledge base kaydi getir."""
    service = KnowledgeService(db)
    kb = await service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.to_dict()


@router.get("/companies/{company_id}/bases", response_model=knowledge_schemas.KnowledgeBaseListResponse)
async def list_knowledge_bases(
    company_id: int,
    branch_id: Optional[int] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sirket bazli knowledge base listesi."""
    service = KnowledgeService(db)
    items, total = await service.get_knowledge_bases_by_company(
        company_id=company_id,
        branch_id=branch_id,
        source_type=source_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [item.to_dict() for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/bases/{kb_id}", response_model=knowledge_schemas.KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: int,
    request: knowledge_schemas.KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Knowledge base kaydi guncelle."""
    service = KnowledgeService(db)
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    kb = await service.update_knowledge_base(kb_id, **updates)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb.to_dict()


@router.delete("/bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Knowledge base kaydi sil."""
    service = KnowledgeService(db)
    success = await service.delete_knowledge_base(kb_id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {"status": "deleted"}


# =============================================================================
# Website Ingestion
# =============================================================================

@router.post("/ingest/website", response_model=knowledge_schemas.IngestResponse)
async def ingest_website(
    request: knowledge_schemas.WebsiteIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Website ingestion baslat.

    Celery task ile asenkron olarak scrape edilir.
    """
    # Knowledge base olustur (pending)
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(
        company_id=request.company_id,
        source_type=knowledge_schemas.IngestionSource.WEBSITE,
        source_url=request.url,
        branch_id=request.branch_id,
    )

    # Celery task baslat
    task = scrape_website_task.delay(
        url=request.url,
        company_id=request.company_id,
        branch_id=request.branch_id,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        follow_links=request.follow_links,
        css_selector=request.css_selector,
        exclude_patterns=request.exclude_patterns,
        include_patterns=request.include_patterns,
    )

    # Job kaydet
    job_service = IngestionJobService(db)
    await job_service.create_job(
        knowledge_base_id=kb.id,
        company_id=request.company_id,
        branch_id=request.branch_id,
        job_type="website_scrape",
        source_info={"url": request.url, "max_depth": request.max_depth},
        celery_task_id=task.id,
    )

    return {
        "knowledge_base_id": kb.id,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Website scraping started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 30,
    }


# =============================================================================
# File Ingestion (PDF/DOCX)
# =============================================================================

@router.post("/ingest/file", response_model=knowledge_schemas.IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    company_id: int = Query(...),
    branch_id: Optional[int] = None,
    source_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """PDF/DOCX dosya ingestion baslat."""
    import base64

    if not source_type:
        ext = file.filename.split(".")[-1].lower() if file.filename else ""
        source_type = ext

    if source_type not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Unsupported file type. Use pdf or docx.")

    # Dosyayi oku
    content = await file.read()
    content_b64 = base64.b64encode(content).decode("utf-8")

    # Knowledge base olustur
    service = KnowledgeService(db)
    kb = await service.create_knowledge_base(
        company_id=company_id,
        source_type=knowledge_schemas.IngestionSource(source_type),
        source_title=file.filename,
        branch_id=branch_id,
    )

    # Celery task baslat
    task = parse_document_task.delay(
        file_content_b64=content_b64,
        filename=file.filename or "document",
        company_id=company_id,
        branch_id=branch_id,
    )

    # Job kaydet
    job_service = IngestionJobService(db)
    await job_service.create_job(
        knowledge_base_id=kb.id,
        company_id=company_id,
        branch_id=branch_id,
        job_type="document_parse",
        source_info={"filename": file.filename, "size": len(content)},
        celery_task_id=task.id,
    )

    return {
        "knowledge_base_id": kb.id,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": f"Document parsing started ({source_type})",
        "celery_task_id": task.id,
        "estimated_time_seconds": 15,
    }


# =============================================================================
# Semantic Chunking
# =============================================================================

@router.post("/bases/{kb_id}/chunk", response_model=knowledge_schemas.SemanticChunkResponse)
async def semantic_chunking(
    kb_id: int,
    request: knowledge_schemas.SemanticChunkRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Semantic chunking calistir.

    Knowledge base'in raw content'ini chunk'lara boler.
    """
    service = KnowledgeService(db)

    # Direkt senkron calistir (kisa islem)
    result = await service.run_chunking_pipeline(
        kb_id=kb_id,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        strategy="semantic" if request.preserve_headings else "recursive",
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Chunk'lari don
    chunks = await service.get_chunks_by_kb(kb_id)

    return {
        "chunks": [c.to_dict() for c in chunks],
        "total_chunks": result.get("chunks_created", 0),
        "total_tokens": result.get("total_tokens", 0),
        "avg_chunk_size": result.get("avg_chunk_size", 0),
        "processing_time_ms": result.get("processing_time_ms", 0),
    }


@router.post("/bases/{kb_id}/chunk/async", response_model=knowledge_schemas.IngestResponse)
async def semantic_chunking_async(
    kb_id: int,
    request: knowledge_schemas.SemanticChunkRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Semantic chunking async calistir (Celery)."""
    kb = await KnowledgeService(db).get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    task = semantic_chunking_task.delay(
        kb_id=kb_id,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        strategy="semantic" if request.preserve_headings else "recursive",
    )

    job_service = IngestionJobService(db)
    await job_service.create_job(
        knowledge_base_id=kb_id,
        company_id=kb.company_id,
        branch_id=kb.branch_id,
        job_type="semantic_chunking",
        celery_task_id=task.id,
    )

    return {
        "knowledge_base_id": kb_id,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Semantic chunking started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 30,
    }


# =============================================================================
# Embedding Generation
# =============================================================================

@router.post("/bases/{kb_id}/embeddings", response_model=knowledge_schemas.EmbeddingResponse)
async def generate_embeddings(
    kb_id: int,
    request: knowledge_schemas.EmbeddingRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Embedding uret."""
    service = KnowledgeService(db)

    result = await service.run_embedding_pipeline(
        kb_id=kb_id,
        model_name=request.model_name,
        batch_size=request.batch_size,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "knowledge_base_id": kb_id,
        "embedding_count": result.get("embeddings_created", 0),
        "model_name": request.model_name,
        "dimension": 384,
        "processing_time_ms": result.get("processing_time_ms", 0),
    }


@router.post("/bases/{kb_id}/embeddings/async", response_model=knowledge_schemas.IngestResponse)
async def generate_embeddings_async(
    kb_id: int,
    request: knowledge_schemas.EmbeddingRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Embedding async uret (Celery)."""
    kb = await KnowledgeService(db).get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    task = embedding_generation_task.delay(
        kb_id=kb_id,
        model_name=request.model_name,
        batch_size=request.batch_size,
    )

    job_service = IngestionJobService(db)
    await job_service.create_job(
        knowledge_base_id=kb_id,
        company_id=kb.company_id,
        branch_id=kb.branch_id,
        job_type="embedding_generation",
        celery_task_id=task.id,
    )

    return {
        "knowledge_base_id": kb_id,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Embedding generation started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 60,
    }


# =============================================================================
# Semantic Search
# =============================================================================

@router.post("/search", response_model=knowledge_schemas.SimilaritySearchResponse)
async def semantic_search(
    request: knowledge_schemas.SimilaritySearchRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Semantik arama yap."""
    service = KnowledgeService(db)

    result = await service.semantic_search(
        query=request.query,
        company_id=request.company_id,
        branch_id=request.branch_id,
        top_k=request.top_k,
        min_score=request.min_score,
    )

    return {
        "query": request.query,
        "results": [
            knowledge_schemas.SimilaritySearchResult(**r)
            for r in result.get("results", [])
        ],
        "total_results": result.get("total_results", 0),
        "processing_time_ms": result.get("processing_time_ms", 0),
    }


@router.post("/query", response_model=knowledge_schemas.KnowledgeQueryResponse)
async def knowledge_query(
    request: knowledge_schemas.KnowledgeQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Knowledge base sorgu."""
    service = KnowledgeService(db)

    # Semantik arama
    search_result = await service.semantic_search(
        query=request.query,
        company_id=request.company_id,
        branch_id=request.branch_id,
        top_k=request.top_k,
    )

    # Brand context
    brand_service = BrandService(db)
    brand_context = await brand_service.get_brand_identity(
        company_id=request.company_id,
        branch_id=request.branch_id,
    )

    return {
        "query": request.query,
        "results": search_result.get("results", []),
        "brand_context": brand_context if brand_context.get("tone") else None,
        "processing_time_ms": search_result.get("processing_time_ms", 0),
    }


# =============================================================================
# Brand Learning
# =============================================================================

@router.post("/brand/learn", response_model=knowledge_schemas.BrandLearningResponse)
async def learn_brand(
    request: knowledge_schemas.BrandLearningRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Metinlerden marka ogren."""
    service = BrandService(db)

    texts = []
    if request.source_content:
        texts = [request.source_content]

    result = await service.learn_from_texts(
        company_id=request.company_id,
        texts=texts,
        branch_id=request.branch_id,
        source=request.source_url,
    )

    return {
        "company_id": request.company_id,
        "profiles_learned": result.get("profiles_created", 0),
        "attribute_summary": result.get("analysis", {}).get("tone", {}),
        "processing_time_ms": result.get("analysis", {}).get("processing_time_ms", 0),
    }


@router.post("/brand/learn/async", response_model=knowledge_schemas.IngestResponse)
async def learn_brand_async(
    request: knowledge_schemas.BrandLearningRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Marka ogrenme async baslat (Celery)."""
    texts = [request.source_content] if request.source_content else []

    task = brand_learning_task.delay(
        company_id=request.company_id,
        texts=texts,
        branch_id=request.branch_id,
        source=request.source_url,
    )

    return {
        "knowledge_base_id": 0,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Brand learning started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 30,
    }


@router.get("/companies/{company_id}/brand/identity", response_model=knowledge_schemas.BrandIdentityResponse)
async def get_brand_identity(
    company_id: int,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Marka kimligini getir."""
    service = BrandService(db)
    identity = await service.get_brand_identity(company_id, branch_id)
    return identity


@router.get("/companies/{company_id}/brand/profiles", response_model=List[knowledge_schemas.BrandProfileResponse])
async def list_brand_profiles(
    company_id: int,
    branch_id: Optional[int] = None,
    attribute_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Brand profillerini listele."""
    service = BrandService(db)
    profiles = await service.get_profiles_by_company(company_id, branch_id, attribute_type)
    return [p.to_dict() for p in profiles]


# =============================================================================
# Visual Learning
# =============================================================================

@router.post("/visual/analyze", response_model=knowledge_schemas.VisualAssetResponse)
async def analyze_visual(
    request: knowledge_schemas.VisualAssetAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Gorsel analiz et ve kaydet."""
    service = VisualLearningService(db)

    result = await service.analyze_and_save(
        image_url=request.image_url,
        company_id=request.company_id,
        branch_id=request.branch_id,
    )

    asset_id = result.get("asset_id")
    if asset_id:
        # Asset'i don
        result_data = result.get("analysis", {})
        result_data["id"] = asset_id
        result_data["company_id"] = request.company_id
        result_data["branch_id"] = request.branch_id
        result_data["image_url"] = request.image_url
        return result_data

    raise HTTPException(status_code=500, detail="Visual analysis failed")


@router.post("/visual/learn", response_model=knowledge_schemas.VisualLearningResponse)
async def learn_visual(
    request: knowledge_schemas.VisualLearningRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Gorsel ogrenme baslat."""
    task = visual_learning_task.delay(
        image_urls=request.image_urls,
        company_id=request.company_id,
        branch_id=request.branch_id,
    )

    return {
        "company_id": request.company_id,
        "images_analyzed": 0,
        "brand_assets_found": 0,
        "dominant_colors": [],
        "common_style_tags": [],
        "brand_elements_detected": [],
        "processing_time_ms": 0,
    }


@router.get("/companies/{company_id}/visual/assets", response_model=List[knowledge_schemas.VisualAssetResponse])
async def list_visual_assets(
    company_id: int,
    branch_id: Optional[int] = None,
    is_brand_asset: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Gorsel varliklari listele."""
    service = VisualLearningService(db)
    assets = await service.get_assets_by_company(company_id, branch_id, is_brand_asset, limit)
    return [a.to_dict() for a in assets]


# =============================================================================
# Campaign Learning
# =============================================================================

@router.post("/campaigns/insights", response_model=knowledge_schemas.CampaignInsightResponse)
async def create_campaign_insight(
    request: knowledge_schemas.CampaignInsightCreate,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Kampanya insight'i kaydet."""
    service = CampaignLearningService(db)

    insight = await service.create_insight(
        company_id=request.company_id,
        campaign_name=request.campaign_name,
        campaign_type=request.campaign_type,
        platform=request.platform,
        metrics={
            "reach": request.reach,
            "impressions": request.impressions,
            "clicks": request.clicks,
            "conversions": request.conversions,
            "spend": request.spend,
            "revenue": request.revenue,
            "engagement_rate": request.engagement_rate,
            "ctr": request.ctr,
            "roas": request.roas,
            "cpa": request.cpa,
        },
        branch_id=request.branch_id,
        knowledge_base_id=request.knowledge_base_id,
        success_factors=request.success_factors,
        failure_factors=request.failure_factors,
        ai_summary=request.ai_summary,
        extra_data=request.extra_data,
    )

    return insight.to_dict()


@router.get("/companies/{company_id}/campaigns/insights", response_model=List[knowledge_schemas.CampaignInsightResponse])
async def list_campaign_insights(
    company_id: int,
    branch_id: Optional[int] = None,
    platform: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Kampanya insight'larini listele."""
    service = CampaignLearningService(db)
    insights = await service.get_insights_by_company(company_id, branch_id, platform, limit)
    return [i.to_dict() for i in insights]


@router.post("/campaigns/learn", response_model=knowledge_schemas.CampaignLearningResponse)
async def learn_campaigns(
    company_id: int,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Kampanyalardan ogren."""
    service = CampaignLearningService(db)
    result = await service.learn_from_campaigns(company_id, branch_id)
    return {
        "company_id": company_id,
        "campaigns_analyzed": result.get("campaigns_analyzed", 0),
        "success_factors": result.get("success_factors", []),
        "failure_factors": result.get("failure_factors", []),
        "recommended_strategies": result.get("recommended_strategies", []),
        "audience_insights": result.get("audience_insights", {}),
        "processing_time_ms": 0,
    }


@router.post("/campaigns/learn/async", response_model=knowledge_schemas.IngestResponse)
async def learn_campaigns_async(
    company_id: int,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Kampanya ogrenme async baslat."""
    task = campaign_learning_task.delay(
        company_id=company_id,
        branch_id=branch_id,
    )

    return {
        "knowledge_base_id": 0,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Campaign learning started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 30,
    }


# =============================================================================
# Company Memory
# =============================================================================

@router.get("/companies/{company_id}/memory", response_model=knowledge_schemas.CompanyMemoryResponse)
async def get_company_memory(
    company_id: int,
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sirket hafizasini getir.

    Tum knowledge base, brand, visual ve campaign verilerini
    tek endpoint'te derler.
    """
    service = KnowledgeService(db)
    memory = await service.get_company_memory(company_id, branch_id)
    return memory


# =============================================================================
# Ingestion Jobs
# =============================================================================

@router.get("/jobs/{job_id}", response_model=knowledge_schemas.IngestionJobResponse)
async def get_ingestion_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Ingestion job getir."""
    service = IngestionJobService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.get("/companies/{company_id}/jobs", response_model=List[knowledge_schemas.IngestionJobResponse])
async def list_ingestion_jobs(
    company_id: int,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Ingestion job'lari listele."""
    service = IngestionJobService(db)
    jobs = await service.get_jobs_by_company(company_id, status, limit)
    return [j.to_dict() for j in jobs]


# =============================================================================
# OCR (Placeholder)
# =============================================================================

@router.get("/ocr/status")
async def get_ocr_status() -> Dict[str, Any]:
    """OCR durumunu kontrol et."""
    processor = OCRProcessor()
    return processor.get_status()


@router.post("/ingest/ocr", response_model=knowledge_schemas.IngestResponse)
async def ingest_ocr(
    request: knowledge_schemas.OCRIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """OCR ingestion baslat (placeholder).

    Gercek OCR icin tesseract kurulumu gereklidir.
    """
    processor = OCRProcessor(
        language=request.language,
        preprocess=request.preprocess,
    )

    status = processor.get_status()

    if not status["available"]:
        return {
            "knowledge_base_id": 0,
            "status": knowledge_schemas.IngestionStatus.FAILED,
            "message": "OCR not available. " + status["note"],
            "celery_task_id": None,
            "estimated_time_seconds": 0,
        }

    return {
        "knowledge_base_id": 0,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "OCR ingestion started (placeholder - not fully implemented)",
        "celery_task_id": None,
        "estimated_time_seconds": 30,
    }


# =============================================================================
# Full Pipeline
# =============================================================================

@router.post("/ingest/full-pipeline", response_model=knowledge_schemas.IngestResponse)
async def full_ingestion_pipeline(
    url: str,
    company_id: int,
    branch_id: Optional[int] = None,
    source_type: str = "website",
    learn_brand: bool = True,
    max_depth: int = 2,
    max_pages: int = 50,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Tam ingestion pipeline baslat.

    Scrape -> Chunk -> Embed -> Brand Learn
    """
    task = full_ingestion_pipeline_task.delay(
        url=url,
        company_id=company_id,
        branch_id=branch_id,
        source_type=source_type,
        learn_brand=learn_brand,
        max_depth=max_depth,
        max_pages=max_pages,
    )

    return {
        "knowledge_base_id": 0,
        "status": knowledge_schemas.IngestionStatus.PENDING,
        "message": "Full ingestion pipeline started",
        "celery_task_id": task.id,
        "estimated_time_seconds": 120,
    }


# =============================================================================
# Chunk Management
# =============================================================================

@router.get("/bases/{kb_id}/chunks", response_model=List[knowledge_schemas.KnowledgeChunkResponse])
async def list_chunks_by_kb(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Knowledge base chunk'larini listele."""
    service = KnowledgeService(db)
    chunks = await service.get_chunks_by_kb(kb_id)
    return [c.to_dict() for c in chunks]


@router.get("/companies/{company_id}/chunks", response_model=List[knowledge_schemas.KnowledgeChunkResponse])
async def list_chunks_by_company(
    company_id: int,
    branch_id: Optional[int] = None,
    chunk_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Sirket chunk'larini listele."""
    service = KnowledgeService(db)
    chunks = await service.get_chunks_by_company(company_id, branch_id, chunk_type, limit)
    return [c.to_dict() for c in chunks]


# =============================================================================
# Social Post Learning
# =============================================================================

@router.post("/social/tone/analyze")
async def analyze_social_tone(
    request: knowledge_schemas.SocialToneRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sosyal medya ton analizi yap."""
    from app.knowledge.brand_learning import SocialToneLearner

    learner = SocialToneLearner()
    result = learner.learn_from_posts(
        posts=request.posts,
        platform=request.platform,
    )

    # Brand profiline kaydet
    if result:
        service = BrandService(db)
        if result.get("detected_tone"):
            await service.create_profile(
                company_id=request.company_id,
                attribute_type=knowledge_schemas.BrandAttributeType.TONE,
                attribute_key="social_primary",
                attribute_value=result["detected_tone"],
                confidence_score=result.get("confidence", 0.5),
                branch_id=request.branch_id,
                source=f"social_{request.platform}",
            )
        await db.commit()

    return result
