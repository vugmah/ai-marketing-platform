"""Knowledge Ingestion - Service Layer.

Ana is mantigi katmani:
- CRUD islemleri (KnowledgeBase, Chunk, Embedding)
- Website scraping & ingestion
- PDF/DOCX parsing & ingestion
- Brand learning
- Visual learning
- Campaign learning
- Semantic search
- Company/branch memory
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.knowledge.brand_learning import BrandAnalyzer, SocialToneLearner
from app.knowledge.campaign_learning import CampaignLearner
from app.knowledge.chunking import SemanticChunker, get_chunker
from app.knowledge.embeddings import BatchEmbeddingPipeline, get_embedding_pipeline
from app.knowledge.models import (
    BrandAttributeType,
    BrandColor,
    BrandProfile,
    CampaignInsight,
    ChunkType,
    IngestionJob,
    IngestionSource,
    IngestionStatus,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeEmbedding,
    SocialPostLearning,
    VisualAsset,
)
from app.knowledge.parsers import DocumentParser
from app.knowledge.scrapers import WebsiteScraper
from app.knowledge.visual_learning import VisualAnalyzer

logger = structlog.get_logger(__name__)


# =============================================================================
# Knowledge Base Service
# =============================================================================

class KnowledgeService:
    """Knowledge Base servis katmani."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # Knowledge Base CRUD
    # =========================================================================

    async def create_knowledge_base(
        self,
        company_id: int,
        source_type: IngestionSource,
        source_url: Optional[str] = None,
        source_title: Optional[str] = None,
        source_description: Optional[str] = None,
        raw_content: Optional[str] = None,
        branch_id: Optional[int] = None,
        content_metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[int] = None,
    ) -> KnowledgeBase:
        """Knowledge base kaydi olustur."""
        content_hash = ""
        if raw_content:
            content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        kb = KnowledgeBase(
            company_id=company_id,
            branch_id=branch_id,
            source_type=source_type.value,
            source_url=source_url,
            source_title=source_title,
            source_description=source_description,
            raw_content=raw_content,
            raw_content_hash=content_hash,
            content_metadata=content_metadata or {},
            status=IngestionStatus.PENDING.value,
            created_by=created_by,
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)

        logger.info(
            "knowledge_base_created",
            kb_id=kb.id,
            company_id=company_id,
            source_type=source_type.value,
        )
        return kb

    async def get_knowledge_base(self, kb_id: int) -> Optional[KnowledgeBase]:
        """Knowledge base kaydi getir."""
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()

    async def get_knowledge_bases_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[KnowledgeBase], int]:
        """Sirket bazli knowledge base listesi."""
        query = select(KnowledgeBase).where(KnowledgeBase.company_id == company_id)

        if branch_id is not None:
            query = query.where(KnowledgeBase.branch_id == branch_id)
        if source_type:
            query = query.where(KnowledgeBase.source_type == source_type)
        if status:
            query = query.where(KnowledgeBase.status == status)

        # Toplam sayi
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Sirala ve sayfala
        query = query.order_by(desc(KnowledgeBase.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return list(items), total

    async def update_knowledge_base(
        self,
        kb_id: int,
        **updates: Any,
    ) -> Optional[KnowledgeBase]:
        """Knowledge base kaydi guncelle."""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return None

        for key, value in updates.items():
            if hasattr(kb, key):
                setattr(kb, key, value)

        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def delete_knowledge_base(self, kb_id: int) -> bool:
        """Knowledge base kaydi sil (cascade ile chunk ve embedding'ler de silinir)."""
        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return False

        await self.db.delete(kb)
        await self.db.commit()
        return True

    # =========================================================================
    # Chunk CRUD
    # =========================================================================

    async def create_chunks(
        self,
        kb_id: int,
        company_id: int,
        chunks: List[Dict[str, Any]],
        branch_id: Optional[int] = None,
    ) -> List[KnowledgeChunk]:
        """Chunk'lari kaydet."""
        db_chunks = []
        for chunk_data in chunks:
            chunk = KnowledgeChunk(
                knowledge_base_id=kb_id,
                company_id=company_id,
                branch_id=branch_id,
                chunk_type=chunk_data.get("chunk_type", ChunkType.PARAGRAPH.value),
                content=chunk_data["content"],
                content_hash=chunk_data.get("content_hash", "")[:64],
                sequence=chunk_data.get("sequence", 0),
                token_count=chunk_data.get("token_count", 0),
                char_count=chunk_data.get("char_count", 0),
                semantic_tags=chunk_data.get("semantic_tags", []),
                keywords=chunk_data.get("keywords", []),
                entities=chunk_data.get("entities", []),
                source_section=chunk_data.get("source_section"),
                source_heading=chunk_data.get("source_heading"),
            )
            db_chunks.append(chunk)
            self.db.add(chunk)

        await self.db.commit()

        # Knowledge base chunk count guncelle
        await self.db.execute(
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(
                chunk_count=len(db_chunks),
                status=IngestionStatus.CHUNKING.value,
            )
        )
        await self.db.commit()

        logger.info("chunks_created", kb_id=kb_id, count=len(db_chunks))
        return db_chunks

    async def get_chunks_by_kb(self, kb_id: int) -> List[KnowledgeChunk]:
        """Knowledge base'e ait chunk'lari getir."""
        result = await self.db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.knowledge_base_id == kb_id)
            .order_by(KnowledgeChunk.sequence)
        )
        return list(result.scalars().all())

    async def get_chunks_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        chunk_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[KnowledgeChunk]:
        """Sirket bazli chunk'lari getir."""
        query = select(KnowledgeChunk).where(KnowledgeChunk.company_id == company_id)

        if branch_id is not None:
            query = query.where(KnowledgeChunk.branch_id == branch_id)
        if chunk_type:
            query = query.where(KnowledgeChunk.chunk_type == chunk_type)

        query = query.order_by(KnowledgeChunk.sequence).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Embedding CRUD
    # =========================================================================

    async def create_embeddings(
        self,
        kb_id: int,
        company_id: int,
        embeddings_data: List[Dict[str, Any]],
    ) -> List[KnowledgeEmbedding]:
        """Embedding'leri kaydet."""
        db_embeddings = []
        for emb_data in embeddings_data:
            emb = KnowledgeEmbedding(
                knowledge_base_id=kb_id,
                chunk_id=emb_data["chunk_id"],
                company_id=company_id,
                embedding_model=emb_data.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"),
                embedding_version=emb_data.get("embedding_version", "1.0"),
                embedding_dimension=emb_data.get("embedding_dimension", 384),
                vector_json=emb_data.get("vector_json", []),
            )
            db_embeddings.append(emb)
            self.db.add(emb)

        await self.db.commit()

        # Knowledge base guncelle
        await self.db.execute(
            update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(
                embedding_count=len(db_embeddings),
                status=IngestionStatus.COMPLETED.value,
                processed_at=func.now(),
            )
        )
        await self.db.commit()

        logger.info("embeddings_created", kb_id=kb_id, count=len(db_embeddings))
        return db_embeddings

    async def get_embeddings_by_kb(self, kb_id: int) -> List[KnowledgeEmbedding]:
        """Knowledge base'e ait embedding'leri getir."""
        result = await self.db.execute(
            select(KnowledgeEmbedding)
            .where(KnowledgeEmbedding.knowledge_base_id == kb_id)
        )
        return list(result.scalars().all())

    async def get_embeddings_by_company(
        self,
        company_id: int,
        limit: int = 1000,
    ) -> List[KnowledgeEmbedding]:
        """Sirket bazli embedding'leri getir."""
        result = await self.db.execute(
            select(KnowledgeEmbedding)
            .where(KnowledgeEmbedding.company_id == company_id)
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Semantic Chunking Pipeline
    # =========================================================================

    async def run_chunking_pipeline(
        self,
        kb_id: int,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        strategy: str = "semantic",
    ) -> Dict[str, Any]:
        """Chunking pipeline'i calistir.

        1. Knowledge base'den raw content'i al
        2. Semantic chunking yap
        3. Chunk'lari veritabanina kaydet
        """
        start_time = time.time()

        kb = await self.get_knowledge_base(kb_id)
        if not kb or not kb.raw_content:
            return {"error": "Knowledge base not found or empty", "chunks_created": 0}

        # Status: chunking
        await self.update_knowledge_base(
            kb_id=kb_id,
            status=IngestionStatus.CHUNKING.value,
        )

        # Chunking
        chunker = get_chunker(
            strategy=strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        result = chunker.chunk_with_stats(kb.raw_content)

        # Chunk'lari kaydet
        chunks_to_save = []
        for chunk_dict in result["chunks"]:
            meta = chunk_dict.get("metadata", {})
            chunks_to_save.append({
                "content": chunk_dict["content"],
                "content_hash": chunk_dict.get("content_hash", "")[:64],
                "chunk_type": meta.get("chunk_type", "paragraph"),
                "sequence": meta.get("sequence", 0),
                "token_count": meta.get("token_count", 0),
                "char_count": meta.get("char_count", 0),
                "semantic_tags": meta.get("semantic_tags", []),
                "keywords": meta.get("keywords", []),
                "entities": meta.get("entities", []),
                "source_section": meta.get("source_section"),
                "source_heading": meta.get("source_heading"),
            })

        saved_chunks = await self.create_chunks(
            kb_id=kb_id,
            company_id=kb.company_id,
            chunks=chunks_to_save,
            branch_id=kb.branch_id,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "kb_id": kb_id,
            "chunks_created": len(saved_chunks),
            "total_tokens": result.get("total_tokens", 0),
            "avg_chunk_size": result.get("avg_chunk_size", 0),
            "processing_time_ms": round(elapsed_ms, 2),
        }

    # =========================================================================
    # Embedding Pipeline
    # =========================================================================

    async def run_embedding_pipeline(
        self,
        kb_id: int,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
    ) -> Dict[str, Any]:
        """Embedding pipeline'i calistir.

        1. Chunk'lari al
        2. Embedding uret
        3. Embedding'leri kaydet
        """
        start_time = time.time()

        kb = await self.get_knowledge_base(kb_id)
        if not kb:
            return {"error": "Knowledge base not found", "embeddings_created": 0}

        # Status: embedding
        await self.update_knowledge_base(
            kb_id=kb_id,
            status=IngestionStatus.EMBEDDING.value,
        )

        # Chunk'lari al
        chunks = await self.get_chunks_by_kb(kb_id)
        if not chunks:
            return {"error": "No chunks found", "embeddings_created": 0}

        # Embedding pipeline
        pipeline = get_embedding_pipeline(model_name, batch_size)

        chunks_data = [
            {"content": c.content, "chunk_id": c.id}
            for c in chunks
        ]

        result = pipeline.process_chunks(chunks_data)

        # Embedding'leri kaydet
        embeddings_to_save = []
        for item in result:
            embeddings_to_save.append({
                "chunk_id": item["chunk_id"],
                "vector_json": item.get("vector_json", []),
                "embedding_model": item.get("embedding_model", model_name),
                "embedding_dimension": item.get("embedding_dimension", 384),
            })

        saved_embeddings = await self.create_embeddings(
            kb_id=kb_id,
            company_id=kb.company_id,
            embeddings_data=embeddings_to_save,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "kb_id": kb_id,
            "embeddings_created": len(saved_embeddings),
            "model_name": model_name,
            "processing_time_ms": round(elapsed_ms, 2),
        }

    # =========================================================================
    # Semantic Search
    # =========================================================================

    async def semantic_search(
        self,
        query: str,
        company_id: int,
        branch_id: Optional[int] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> Dict[str, Any]:
        """Semantik arama yap.

        1. Sorgu embedding'i uret
        2. Sirket embedding'lerini al
        3. Cosine similarity ile ara
        """
        start_time = time.time()

        # Embedding pipeline
        pipeline = get_embedding_pipeline()
        query_embedding = pipeline.generator.generate_single(query)

        # Sirket embedding'lerini al
        embeddings = await self.get_embeddings_by_company(company_id)

        # Branch filtreleme
        if branch_id is not None:
            embeddings = [e for e in embeddings if e.chunk and e.chunk.branch_id == branch_id]

        # Similarity search
        docs = []
        for emb in embeddings:
            chunk = emb.chunk
            if chunk:
                docs.append({
                    "chunk_id": emb.chunk_id,
                    "knowledge_base_id": emb.knowledge_base_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "source_section": chunk.source_section,
                    "keywords": chunk.keywords or [],
                    "vector_json": emb.vector_json,
                })

        results = pipeline.similarity.search_with_content(
            query_embedding, docs, top_k, min_score
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "query": query,
            "results": results,
            "total_results": len(results),
            "processing_time_ms": round(elapsed_ms, 2),
        }

    # =========================================================================
    # Company Memory
    # =========================================================================

    async def get_company_memory(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sirket hafizasini getir.

        Tum knowledge base, chunk, embedding, brand profili,
        gorsel varlik ve kampanya insight'larini getirir.
        """
        # Knowledge bases
        kbs, total_kbs = await self.get_knowledge_bases_by_company(
            company_id=company_id, branch_id=branch_id, page=1, page_size=1000
        )

        total_chunks = sum(kb.chunk_count for kb in kbs)
        total_embeddings = sum(kb.embedding_count for kb in kbs)

        # Brand profilleri
        brand_service = BrandService(self.db)
        brand_profiles = await brand_service.get_profiles_by_company(company_id, branch_id)

        # Brand renkleri
        brand_colors = await brand_service.get_colors_by_company(company_id, branch_id)

        # Gorsel varliklar
        visual_service = VisualLearningService(self.db)
        visual_assets = await visual_service.get_assets_by_company(company_id, branch_id)

        # Kampanya insight'lari
        campaign_service = CampaignLearningService(self.db)
        campaign_insights = await campaign_service.get_insights_by_company(company_id, branch_id)

        return {
            "company_id": company_id,
            "branch_id": branch_id,
            "knowledge_base_count": total_kbs,
            "total_chunks": total_chunks,
            "total_embeddings": total_embeddings,
            "brand_profiles": [p.to_dict() for p in brand_profiles],
            "brand_colors": [c.to_dict() for c in brand_colors],
            "visual_assets": [a.to_dict() for a in visual_assets],
            "campaign_insights": [i.to_dict() for i in campaign_insights],
            "knowledge_bases": [kb.to_dict() for kb in kbs[:20]],
        }


# =============================================================================
# Brand Learning Service
# =============================================================================

class BrandService:
    """Brand learning servis katmani."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analyzer = BrandAnalyzer()

    async def create_profile(
        self,
        company_id: int,
        attribute_type: BrandAttributeType,
        attribute_key: str,
        attribute_value: str,
        confidence_score: float = 0.5,
        branch_id: Optional[int] = None,
        source: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> BrandProfile:
        """Brand profili olustur."""
        profile = BrandProfile(
            company_id=company_id,
            branch_id=branch_id,
            attribute_type=attribute_type.value,
            attribute_key=attribute_key,
            attribute_value=attribute_value,
            confidence_score=confidence_score,
            source=source,
            extra_data=extra_data or {},
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def get_profiles_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        attribute_type: Optional[str] = None,
    ) -> List[BrandProfile]:
        """Sirket bazli brand profilleri."""
        query = select(BrandProfile).where(BrandProfile.company_id == company_id)

        if branch_id is not None:
            query = query.where(BrandProfile.branch_id == branch_id)
        if attribute_type:
            query = query.where(BrandProfile.attribute_type == attribute_type)

        query = query.order_by(desc(BrandProfile.confidence_score))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_brand_identity(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Marka kimligini derle."""
        profiles = await self.get_profiles_by_company(company_id, branch_id)

        identity = {
            "company_id": company_id,
            "branch_id": branch_id,
            "tone": {},
            "colors": [],
            "values": [],
            "personality": {},
            "mission": None,
            "vision": None,
            "slogans": [],
            "target_audience": {},
            "confidence_scores": {},
        }

        for profile in profiles:
            atype = profile.attribute_type
            akey = profile.attribute_key
            avalue = profile.attribute_value

            if atype == BrandAttributeType.TONE.value:
                identity["tone"][akey] = avalue
            elif atype == BrandAttributeType.COLOR.value:
                identity["colors"].append({"key": akey, "value": avalue})
            elif atype == BrandAttributeType.VALUE.value:
                identity["values"].append(avalue)
            elif atype == BrandAttributeType.MISSION.value:
                identity["mission"] = avalue
            elif atype == BrandAttributeType.VISION.value:
                identity["vision"] = avalue
            elif atype == BrandAttributeType.SLOGAN.value:
                identity["slogans"].append(avalue)
            elif atype == BrandAttributeType.PERSONALITY.value:
                identity["personality"][akey] = avalue
            elif atype == BrandAttributeType.TARGET_AUDIENCE.value:
                identity["target_audience"][akey] = avalue

            # Confidence skoru
            if atype not in identity["confidence_scores"]:
                identity["confidence_scores"][atype] = []
            identity["confidence_scores"][atype].append(profile.confidence_score)

        # Ortalama confidence
        for atype, scores in identity["confidence_scores"].items():
            if scores:
                identity["confidence_scores"][atype] = round(sum(scores) / len(scores), 4)

        return identity

    async def learn_from_texts(
        self,
        company_id: int,
        texts: List[str],
        branch_id: Optional[int] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Metinlerden marka ogren."""
        analysis = self.analyzer.analyze(texts)
        profiles_created = 0

        # Ton profilleri
        if analysis.tone.primary_tone:
            await self._upsert_profile(
                company_id, BrandAttributeType.TONE, "primary",
                analysis.tone.primary_tone, analysis.tone.confidence, branch_id, source
            )
            profiles_created += 1

        if analysis.tone.secondary_tone:
            await self._upsert_profile(
                company_id, BrandAttributeType.TONE, "secondary",
                analysis.tone.secondary_tone, analysis.tone.confidence * 0.8, branch_id, source
            )
            profiles_created += 1

        # Formality
        await self._upsert_profile(
            company_id, BrandAttributeType.PERSONALITY, "formality",
            str(round(analysis.tone.formality_score, 2)), analysis.tone.confidence,
            branch_id, source
        )
        profiles_created += 1

        # Degerler
        for value in analysis.values.values:
            await self._upsert_profile(
                company_id, BrandAttributeType.VALUE, value.lower().replace(" ", "_"),
                value, analysis.values.confidence, branch_id, source
            )
            profiles_created += 1

        # Misyon
        if analysis.values.mission:
            await self._upsert_profile(
                company_id, BrandAttributeType.MISSION, "primary",
                analysis.values.mission, analysis.values.confidence, branch_id, source
            )
            profiles_created += 1

        # Vizyon
        if analysis.values.vision:
            await self._upsert_profile(
                company_id, BrandAttributeType.VISION, "primary",
                analysis.values.vision, analysis.values.confidence, branch_id, source
            )
            profiles_created += 1

        # Sloganlar
        for slogan in analysis.slogans:
            await self._upsert_profile(
                company_id, BrandAttributeType.SLOGAN, f"slogan_{hash(slogan) % 10000}",
                slogan, 0.7, branch_id, source
            )
            profiles_created += 1

        # Kisilik
        for key, value in analysis.personality.items():
            await self._upsert_profile(
                company_id, BrandAttributeType.PERSONALITY, key,
                str(value), analysis.tone.confidence, branch_id, source
            )
            profiles_created += 1

        await self.db.commit()

        return {
            "company_id": company_id,
            "profiles_created": profiles_created,
            "analysis": analysis.to_dict(),
        }

    async def _upsert_profile(
        self,
        company_id: int,
        attr_type: BrandAttributeType,
        attr_key: str,
        attr_value: str,
        confidence: float,
        branch_id: Optional[int],
        source: Optional[str],
    ) -> None:
        """Brand profili ekle veya guncelle."""
        query = select(BrandProfile).where(
            and_(
                BrandProfile.company_id == company_id,
                BrandProfile.attribute_type == attr_type.value,
                BrandProfile.attribute_key == attr_key,
            )
        )
        if branch_id is not None:
            query = query.where(BrandProfile.branch_id == branch_id)

        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.attribute_value = attr_value
            existing.confidence_score = max(existing.confidence_score, confidence)
            existing.source = source
            existing.source_count = (existing.source_count or 0) + 1
        else:
            profile = BrandProfile(
                company_id=company_id,
                branch_id=branch_id,
                attribute_type=attr_type.value,
                attribute_key=attr_key,
                attribute_value=attr_value,
                confidence_score=confidence,
                source=source,
                source_count=1,
            )
            self.db.add(profile)

    # Renk servisi
    async def create_color(
        self,
        company_id: int,
        hex_code: str,
        color_name: Optional[str] = None,
        color_role: Optional[str] = None,
        usage_area: Optional[str] = None,
        confidence: float = 0.5,
        branch_id: Optional[int] = None,
        source: Optional[str] = None,
    ) -> BrandColor:
        """Brand rengi kaydet."""
        color = BrandColor(
            company_id=company_id,
            branch_id=branch_id,
            hex_code=hex_code,
            color_name=color_name,
            color_role=color_role,
            usage_area=usage_area,
            confidence=confidence,
            source=source,
        )
        self.db.add(color)
        await self.db.commit()
        await self.db.refresh(color)
        return color

    async def get_colors_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> List[BrandColor]:
        """Sirket bazli brand renkleri."""
        query = select(BrandColor).where(BrandColor.company_id == company_id)
        if branch_id is not None:
            query = query.where(BrandColor.branch_id == branch_id)
        query = query.order_by(desc(BrandColor.confidence))
        result = await self.db.execute(query)
        return list(result.scalars().all())


# =============================================================================
# Visual Learning Service
# =============================================================================

class VisualLearningService:
    """Visual learning servis katmani."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analyzer = VisualAnalyzer()

    async def create_asset(
        self,
        company_id: int,
        image_url: str,
        branch_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
        image_type: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> VisualAsset:
        """Gorsel varlik kaydet."""
        image_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:64]

        asset = VisualAsset(
            company_id=company_id,
            branch_id=branch_id,
            knowledge_base_id=knowledge_base_id,
            image_url=image_url,
            image_hash=image_hash,
            image_type=image_type,
            source_url=source_url,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_assets_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        is_brand_asset: Optional[bool] = None,
        limit: int = 100,
    ) -> List[VisualAsset]:
        """Sirket bazli gorsel varliklar."""
        query = select(VisualAsset).where(VisualAsset.company_id == company_id)
        if branch_id is not None:
            query = query.where(VisualAsset.branch_id == branch_id)
        if is_brand_asset is not None:
            query = query.where(VisualAsset.is_brand_asset == (1 if is_brand_asset else 0))
        query = query.order_by(desc(VisualAsset.created_at)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def analyze_and_save(
        self,
        image_url: str,
        company_id: int,
        branch_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Gorseli analiz et ve kaydet."""
        # Analiz yap
        analysis = await self.analyzer.analyze_image(
            image_url, company_id, branch_id
        )

        # Kaydet
        asset = await self.create_asset(
            company_id=company_id,
            image_url=image_url,
            branch_id=branch_id,
            knowledge_base_id=knowledge_base_id,
            image_type="analyzed",
        )

        # Guncelle analiz sonuclariyla
        asset.description = analysis.description
        asset.dominant_colors = [c.__dict__ for c in analysis.dominant_colors]
        asset.detected_objects = analysis.detected_objects
        asset.brand_elements = analysis.brand_elements
        asset.composition_analysis = analysis.composition_analysis
        asset.style_tags = analysis.style_tags
        asset.is_brand_asset = 1 if analysis.is_brand_asset else 0
        asset.brand_relevance_score = analysis.brand_relevance_score
        asset.analyzed_at = func.now()

        await self.db.commit()

        return {
            "asset_id": asset.id,
            "analysis": analysis.to_dict(),
        }


# =============================================================================
# Campaign Learning Service
# =============================================================================

class CampaignLearningService:
    """Campaign learning servis katmani."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.learner = CampaignLearner()

    async def create_insight(
        self,
        company_id: int,
        campaign_name: str,
        campaign_type: Optional[str] = None,
        platform: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        branch_id: Optional[int] = None,
        knowledge_base_id: Optional[int] = None,
        success_factors: Optional[List[str]] = None,
        failure_factors: Optional[List[str]] = None,
        ai_summary: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> CampaignInsight:
        """Kampanya insight'i kaydet."""
        metrics_data = metrics or {}

        insight = CampaignInsight(
            company_id=company_id,
            branch_id=branch_id,
            knowledge_base_id=knowledge_base_id,
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            platform=platform,
            reach=metrics_data.get("reach"),
            impressions=metrics_data.get("impressions"),
            clicks=metrics_data.get("clicks"),
            conversions=metrics_data.get("conversions"),
            spend=metrics_data.get("spend"),
            revenue=metrics_data.get("revenue"),
            engagement_rate=metrics_data.get("engagement_rate"),
            ctr=metrics_data.get("ctr"),
            roas=metrics_data.get("roas"),
            cpa=metrics_data.get("cpa"),
            success_factors=success_factors or [],
            failure_factors=failure_factors or [],
            ai_summary=ai_summary,
            extra_data=extra_data or {},
        )
        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return insight

    async def get_insights_by_company(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        platform: Optional[str] = None,
        limit: int = 100,
    ) -> List[CampaignInsight]:
        """Sirket bazli kampanya insight'lari."""
        query = select(CampaignInsight).where(CampaignInsight.company_id == company_id)
        if branch_id is not None:
            query = query.where(CampaignInsight.branch_id == branch_id)
        if platform:
            query = query.where(CampaignInsight.platform == platform)
        query = query.order_by(desc(CampaignInsight.created_at)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def learn_from_campaigns(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Kampanyalardan ogren."""
        insights = await self.get_insights_by_company(company_id, branch_id)

        campaigns = []
        for insight in insights:
            campaigns.append({
                "name": insight.campaign_name,
                "platform": insight.platform,
                "type": insight.campaign_type,
                "metrics": {
                    "reach": insight.reach,
                    "impressions": insight.impressions,
                    "clicks": insight.clicks,
                    "conversions": insight.conversions,
                    "spend": insight.spend,
                    "revenue": insight.revenue,
                    "engagement_rate": insight.engagement_rate,
                    "ctr": insight.ctr,
                    "roas": insight.roas,
                    "cpa": insight.cpa,
                }
            })

        result = self.learner.learn(campaigns)
        result["company_id"] = company_id
        result["branch_id"] = branch_id

        return result


# =============================================================================
# Ingestion Job Service
# =============================================================================

class IngestionJobService:
    """Ingestion job servis katmani."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_job(
        self,
        knowledge_base_id: int,
        company_id: int,
        job_type: str,
        source_info: Optional[Dict[str, Any]] = None,
        celery_task_id: Optional[str] = None,
        branch_id: Optional[int] = None,
    ) -> IngestionJob:
        """Ingestion job olustur."""
        job = IngestionJob(
            knowledge_base_id=knowledge_base_id,
            company_id=company_id,
            branch_id=branch_id,
            job_type=job_type,
            source_info=source_info or {},
            celery_task_id=celery_task_id,
            status=IngestionStatus.PENDING.value,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: int) -> Optional[IngestionJob]:
        """Ingestion job getir."""
        result = await self.db.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_jobs_by_company(
        self,
        company_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[IngestionJob]:
        """Sirket bazli ingestion job'lari."""
        query = select(IngestionJob).where(IngestionJob.company_id == company_id)
        if status:
            query = query.where(IngestionJob.status == status)
        query = query.order_by(desc(IngestionJob.created_at)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_job_status(
        self,
        job_id: int,
        status: str,
        progress_percent: Optional[int] = None,
        logs: Optional[List[str]] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> Optional[IngestionJob]:
        """Job status guncelle."""
        job = await self.get_job(job_id)
        if not job:
            return None

        job.status = status
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if logs:
            job.logs = (job.logs or []) + logs
        if error_details:
            job.error_details = error_details

        if status == IngestionStatus.IN_PROGRESS.value:
            job.started_at = func.now()
        elif status in (IngestionStatus.COMPLETED.value, IngestionStatus.FAILED.value):
            job.completed_at = func.now()

        await self.db.commit()
        await self.db.refresh(job)
        return job
