"""
RAG (Retrieval-Augmented Generation) - Full Implementation

End-to-end RAG pipeline that:
1. Accepts a user query
2. Retrieves relevant documents from vector store
3. Assembles context
4. Injects context into LLM prompt
5. Returns the generated response with source citations

Features:
- Full RAG pipeline with vector search + LLM generation
- Company-aware retrieval (tenant isolation)
- Branch-aware retrieval (branch-specific knowledge)
- Source citation in responses
- Context token budget management
- Streaming support (planned)
- Fallback when RAG is unavailable

Usage:
    rag = RAGPipeline()
    result = await rag.query(
        query="What are our best selling products?",
        company_id=1,
        branch_id=2,
    )
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.embeddings import get_embedding_service
from app.ai.retrieval import ContextRetriever, get_retriever, RetrievedDocument
from app.ai.vector_store import get_vector_store
from app.ai.service import OpenAIService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAG_SYSTEM_PROMPT = """Sen bir pazarlama asistanisisin. Kullanicinin sorusunu yalnizca saglanan BILGI KAYNAKLARINA dayanarak yanitla.
Kurallar:
- Bilgi kaynaklarindaki icerigi kullan, dis bilgi ekleme
- Kaynaklari belirt: [1], [2] gibi
- Emin degilsen "Bu konuda yeterli bilgi bulunmuyor" de
- Turkce yanit ver
- Oz ve anlasilir ol"""

DEFAULT_TOP_K = 5
MAX_CONTEXT_TOKENS = 3500

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class RAGSource:
    """A source document cited in a RAG response."""

    id: str
    content_preview: str
    score: float
    entity_type: str
    entity_id: int
    rank: int = 0


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""

    query: str
    answer: str
    sources: List[RAGSource]
    context_used: str
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    latency_ms: int = 0
    cached: bool = False
    model: str = "gpt-4o-mini"
    fallback: bool = False


# ---------------------------------------------------------------------------
# RAG Pipeline
# ---------------------------------------------------------------------------


class RAGPipeline:
    """Full RAG pipeline with retrieval + generation.

    Orchestrates the complete RAG flow:
    1. Retrieve relevant documents from vector store
    2. Assemble context with source citations
    3. Build LLM prompt with context
    4. Generate response via OpenAI
    5. Return response with source citations

    Usage:
        rag = RAGPipeline()

        # Simple query
        result = await rag.query(
            "Yaz kampanyasi fikirleri oner",
            company_id=1,
        )

        # Branch-aware query
        result = await rag.query(
            "Sube ozel kampanyalari nelerdir?",
            company_id=1,
            branch_id=3,
        )

        # Custom parameters
        result = await rag.query(
            query="...",
            company_id=1,
            top_k=10,
            system_prompt="Custom prompt...",
        )
    """

    def __init__(
        self,
        retriever: Optional[ContextRetriever] = None,
        openai_service: Optional[OpenAIService] = None,
    ):
        self._retriever = retriever
        self._openai = openai_service

    async def _get_retriever(self) -> ContextRetriever:
        if self._retriever is None:
            self._retriever = await get_retriever()
        return self._retriever

    def _get_openai(self) -> OpenAIService:
        if self._openai is None:
            self._openai = OpenAIService()
        return self._openai

    # ------------------------------------------------------------------
    # Main Query Method
    # ------------------------------------------------------------------

    async def query(
        self,
        query: str,
        company_id: int,
        branch_id: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        system_prompt: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        use_hybrid: bool = False,
    ) -> RAGResponse:
        """Execute a full RAG query.

        Retrieves relevant documents, assembles context, and generates
        a response using the LLM with the retrieved context.

        Args:
            query: User query text.
            company_id: Company ID for tenant isolation.
            branch_id: Optional branch ID for branch-aware retrieval.
            entity_types: Filter by entity types.
            top_k: Number of documents to retrieve.
            system_prompt: Custom system prompt (optional).
            model: LLM model to use.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            use_hybrid: Use hybrid search (semantic + keyword).

        Returns:
            RAGResponse with answer and sources.
        """
        start_time = time.time()
        retriever = await self._get_retriever()

        # 1. Retrieve context
        try:
            if use_hybrid:
                documents = await retriever.hybrid_search(
                    query=query,
                    company_id=company_id,
                    branch_id=branch_id,
                    entity_types=entity_types,
                    top_k=top_k,
                )
            else:
                documents = await retriever.search(
                    query=query,
                    company_id=company_id,
                    branch_id=branch_id,
                    entity_types=entity_types,
                    top_k=top_k,
                )
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)
            return RAGResponse(
                query=query,
                answer="Bilgi erisimi sirasinda bir hata olustu. Lutfen tekrar deneyin.",
                sources=[],
                context_used="",
                fallback=True,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 2. Assemble context
        context = retriever.assemble_context(documents, query)

        if not documents:
            return RAGResponse(
                query=query,
                answer="Bu konuda sistemde yeterli bilgi bulunmuyor. Lutfen farkli bir soru sorun.",
                sources=[],
                context_used="",
                fallback=True,
                latency_ms=int((time.time() - start_time) * 1000),
            )

        # 3. Build messages
        sys_prompt = system_prompt or RAG_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": sys_prompt},
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"=== KULLANICI SORUSU ===\n"
                    f"{query}\n\n"
                    f"Yukaridaki bilgi kaynaklarina dayanarak soruyu yanitla."
                ),
            },
        ]

        # 4. Generate response
        openai = self._get_openai()
        try:
            result = await openai.create_chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                company_id=company_id,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Build sources
            sources = [
                RAGSource(
                    id=doc.id,
                    content_preview=doc.content[:200],
                    score=doc.score,
                    entity_type=doc.entity_type,
                    entity_id=doc.entity_id,
                    rank=doc.rank,
                )
                for doc in documents
            ]

            return RAGResponse(
                query=query,
                answer=result.get("content", ""),
                sources=sources,
                context_used=context,
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                total_tokens=result.get("total_tokens", 0),
                cost_estimate=result.get("cost_estimate", 0.0),
                latency_ms=latency_ms,
                cached=False,
                model=result.get("model", model),
                fallback=result.get("fallback", False),
            )

        except Exception as exc:
            logger.error("RAG generation failed: %s", exc)
            latency_ms = int((time.time() - start_time) * 1000)

            return RAGResponse(
                query=query,
                answer="Yanit olusturulurken bir hata olustu. Lutfen tekrar deneyin.",
                sources=[
                    RAGSource(
                        id=doc.id,
                        content_preview=doc.content[:200],
                        score=doc.score,
                        entity_type=doc.entity_type,
                        entity_id=doc.entity_id,
                        rank=doc.rank,
                    )
                    for doc in documents
                ],
                context_used=context,
                fallback=True,
                latency_ms=latency_ms,
            )

    # ------------------------------------------------------------------
    # Quick Search (retrieval only, no generation)
    # ------------------------------------------------------------------

    async def search_only(
        self,
        query: str,
        company_id: int,
        branch_id: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> List[RetrievedDocument]:
        """Search only - retrieve documents without LLM generation.

        Useful for document lookup and preview.

        Args:
            query: Search query.
            company_id: Company ID.
            branch_id: Branch ID.
            entity_types: Entity type filter.
            top_k: Number of results.

        Returns:
            List of RetrievedDocument.
        """
        retriever = await self._get_retriever()
        return await retriever.search(
            query=query,
            company_id=company_id,
            branch_id=branch_id,
            entity_types=entity_types,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest(
        self,
        content: str,
        entity_type: str,
        entity_id: int,
        company_id: int,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk: bool = True,
    ) -> int:
        """Ingest a document into the RAG knowledge base.

        Args:
            content: Document content.
            entity_type: Type of entity.
            entity_id: Entity ID.
            company_id: Company ID.
            branch_id: Optional branch ID.
            metadata: Additional metadata.
            chunk: Whether to chunk the document.

        Returns:
            Number of chunks ingested.
        """
        retriever = await self._get_retriever()
        return await retriever.ingest_document(
            content=content,
            entity_type=entity_type,
            entity_id=entity_id,
            company_id=company_id,
            branch_id=branch_id,
            metadata=metadata,
            chunk=chunk,
        )

    async def delete(
        self,
        entity_type: str,
        entity_id: int,
    ) -> int:
        """Delete a document from the RAG knowledge base.

        Args:
            entity_type: Type of entity.
            entity_id: Entity ID.

        Returns:
            Number of chunks deleted.
        """
        retriever = await self._get_retriever()
        return await retriever.delete_document(entity_type, entity_id)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get RAG knowledge base statistics.

        Args:
            company_id: Company ID.
            branch_id: Optional branch ID.

        Returns:
            Statistics dict.
        """
        store = await get_vector_store()
        health = await store.health_check()

        total = await store.count(company_id=company_id)
        branch_total = 0
        if branch_id:
            branch_total = await store.count(
                company_id=company_id, branch_id=branch_id
            )

        return {
            "backend": health.get("backend", "unknown"),
            "backend_type": health.get("backend_type", "unknown"),
            "dimension": health.get("dimension", 0),
            "company_id": company_id,
            "branch_id": branch_id,
            "total_vectors": total,
            "branch_vectors": branch_total,
            "status": health.get("status", "unknown"),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_rag_pipeline: Optional[RAGPipeline] = None


async def get_rag_pipeline() -> RAGPipeline:
    """Get or create the singleton RAGPipeline.

    Returns:
        RAGPipeline instance.
    """
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def reset_rag_pipeline() -> None:
    """Reset the singleton (mainly for testing)."""
    global _rag_pipeline
    _rag_pipeline = None
