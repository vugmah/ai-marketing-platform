"""
RAG Router - API endpoints for Vector Memory & RAG

Provides endpoints for:
- RAG queries (retrieval + generation)
- Semantic search (retrieval only)
- Document ingestion
- Document deletion
- Vector store health check
- Company/branch knowledge stats

Router prefix: /api/v2/ai/rag (registered in main.py)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import RAGPipeline, get_rag_pipeline
from app.ai.retrieval import ContextRetriever, get_retriever
from app.ai.vector_store import VectorStore, get_vector_store
from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_company_branch(user: User) -> tuple:
    """Extract company_id and branch_id from the current user."""
    if user.company_id is None:
        raise ValidationError("User must belong to a company")
    return user.company_id, user.branch_id


# ---------------------------------------------------------------------------
# RAG Query
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="RAG query - retrieve and generate",
)
async def rag_query(
    query: str = Query(..., min_length=1, description="Sorgu metni"),
    branch_id: Optional[int] = Query(default=None, description="Sube ID (branch-aware)"),
    entity_types: Optional[List[str]] = Query(
        default=None,
        description="Varlik turleri: product, post, customer, document, prompt",
    ),
    top_k: int = Query(default=5, ge=1, le=20, description="Dokuman sayisi"),
    model: str = Query(default="gpt-4o-mini", description="LLM modeli"),
    temperature: float = Query(default=0.7, ge=0.0, le=2.0),
    use_hybrid: bool = Query(default=False, description="Hybrid arama (semantic + keyword)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """RAG query - retrieve relevant documents and generate a response.

    Retrieves context-aware documents from the vector store and uses
    them to generate an LLM response with source citations.

    Args:
        query: Search query text.
        branch_id: Optional branch ID for branch-aware retrieval.
        entity_types: Filter by entity types.
        top_k: Number of documents to retrieve.
        model: LLM model.
        temperature: Sampling temperature.
        use_hybrid: Use hybrid search.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        RAG response with answer and sources.
    """
    company_id, user_branch_id = _get_company_branch(current_user)

    # Use user branch if not specified
    effective_branch_id = branch_id or user_branch_id

    rag = await get_rag_pipeline()
    result = await rag.query(
        query=query,
        company_id=company_id,
        branch_id=effective_branch_id,
        entity_types=entity_types,
        top_k=top_k,
        model=model,
        temperature=temperature,
        use_hybrid=use_hybrid,
    )

    return {
        "success": True,
        "data": {
            "query": result.query,
            "answer": result.answer,
            "sources": [
                {
                    "id": s.id,
                    "content_preview": s.content_preview,
                    "score": s.score,
                    "entity_type": s.entity_type,
                    "entity_id": s.entity_id,
                    "rank": s.rank,
                }
                for s in result.sources
            ],
            "tokens": {
                "input": result.tokens_input,
                "output": result.tokens_output,
                "total": result.total_tokens,
            },
            "cost_estimate": result.cost_estimate,
            "latency_ms": result.latency_ms,
            "model": result.model,
            "fallback": result.fallback,
        },
    }


# ---------------------------------------------------------------------------
# Semantic Search (retrieval only)
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Semantic search (retrieval only)",
)
async def semantic_search(
    query: str = Query(..., min_length=1, description="Arama sorgusu"),
    branch_id: Optional[int] = Query(default=None, description="Sube ID"),
    entity_types: Optional[List[str]] = Query(
        default=None,
        description="Varlik turleri",
    ),
    top_k: int = Query(default=10, ge=1, le=50),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Semantic search over the vector store (retrieval only, no LLM).

    Args:
        query: Search query.
        branch_id: Optional branch filter.
        entity_types: Filter by entity types.
        top_k: Maximum results.
        min_score: Minimum similarity threshold.
        current_user: Authenticated user.

    Returns:
        List of search results with scores.
    """
    company_id, user_branch_id = _get_company_branch(current_user)
    effective_branch_id = branch_id or user_branch_id

    retriever = await get_retriever()
    documents = await retriever.search(
        query=query,
        company_id=company_id,
        branch_id=effective_branch_id,
        entity_types=entity_types,
        top_k=top_k,
        min_score=min_score,
    )

    return {
        "success": True,
        "data": {
            "query": query,
            "total": len(documents),
            "results": [
                {
                    "id": doc.id,
                    "content": doc.content[:500],
                    "score": doc.score,
                    "entity_type": doc.entity_type,
                    "entity_id": doc.entity_id,
                    "company_id": doc.company_id,
                    "branch_id": doc.branch_id,
                    "metadata": doc.metadata,
                    "rank": doc.rank,
                }
                for doc in documents
            ],
        },
    }


# ---------------------------------------------------------------------------
# Hybrid Search
# ---------------------------------------------------------------------------


@router.get(
    "/search/hybrid",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Hybrid search (semantic + keyword)",
)
async def hybrid_search(
    query: str = Query(..., min_length=1, description="Arama sorgusu"),
    branch_id: Optional[int] = Query(default=None, description="Sube ID"),
    entity_types: Optional[List[str]] = Query(default=None),
    top_k: int = Query(default=10, ge=1, le=50),
    semantic_weight: float = Query(default=0.7, ge=0.0, le=1.0),
    keyword_weight: float = Query(default=0.3, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Hybrid search combining semantic and keyword matching.

    Args:
        query: Search query.
        branch_id: Optional branch filter.
        entity_types: Filter by entity types.
        top_k: Maximum results.
        semantic_weight: Weight for semantic scores.
        keyword_weight: Weight for keyword scores.
        current_user: Authenticated user.

    Returns:
        List of search results with combined scores.
    """
    company_id, user_branch_id = _get_company_branch(current_user)
    effective_branch_id = branch_id or user_branch_id

    retriever = await get_retriever()
    documents = await retriever.hybrid_search(
        query=query,
        company_id=company_id,
        branch_id=effective_branch_id,
        entity_types=entity_types,
        top_k=top_k,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    return {
        "success": True,
        "data": {
            "query": query,
            "total": len(documents),
            "weights": {
                "semantic": semantic_weight,
                "keyword": keyword_weight,
            },
            "results": [
                {
                    "id": doc.id,
                    "content": doc.content[:500],
                    "score": doc.score,
                    "entity_type": doc.entity_type,
                    "entity_id": doc.entity_id,
                    "company_id": doc.company_id,
                    "branch_id": doc.branch_id,
                    "rank": doc.rank,
                }
                for doc in documents
            ],
        },
    }


# ---------------------------------------------------------------------------
# Document Ingestion
# ---------------------------------------------------------------------------


@router.post(
    "/ingest",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the vector store",
)
async def ingest_document(
    content: str = Query(..., min_length=1, description="Dokuman icerigi"),
    entity_type: str = Query(..., min_length=1, max_length=50, description="Varlik turu"),
    entity_id: int = Query(..., ge=1, description="Varlik ID"),
    branch_id: Optional[int] = Query(default=None),
    metadata: Optional[str] = Query(default=None, description="JSON metadata"),
    chunk: bool = Query(default=True, description="Chunking yap"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ingest a document into the RAG knowledge base.

    Chunks the document, generates embeddings, and stores in the vector store.

    Args:
        content: Document content.
        entity_type: Type of entity.
        entity_id: Entity ID.
        branch_id: Optional branch ID.
        metadata: JSON metadata string.
        chunk: Whether to chunk the document.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Ingestion results.
    """
    company_id, user_branch_id = _get_company_branch(current_user)
    effective_branch_id = branch_id or user_branch_id

    import json

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON metadata")

    rag = await get_rag_pipeline()
    chunks_ingested = await rag.ingest(
        content=content,
        entity_type=entity_type,
        entity_id=entity_id,
        company_id=company_id,
        branch_id=effective_branch_id,
        metadata=meta,
        chunk=chunk,
    )

    return {
        "success": True,
        "data": {
            "chunks_ingested": chunks_ingested,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "company_id": company_id,
            "branch_id": effective_branch_id,
        },
    }


# ---------------------------------------------------------------------------
# Document Deletion
# ---------------------------------------------------------------------------


@router.delete(
    "/documents/{entity_type}/{entity_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a document from the vector store",
)
async def delete_document(
    entity_type: str,
    entity_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["super_admin", "company_admin"])),
) -> Dict[str, Any]:
    """Delete a document and its chunks from the vector store.

    Args:
        entity_type: Type of entity.
        entity_id: Entity ID.
        db: Database session.
        current_user: Authenticated admin user.

    Returns:
        Deletion results.
    """
    company_id, _ = _get_company_branch(current_user)

    rag = await get_rag_pipeline()
    deleted_count = await rag.delete(entity_type, entity_id)

    return {
        "success": True,
        "data": {
            "deleted_count": deleted_count,
            "entity_type": entity_type,
            "entity_id": entity_id,
        },
    }


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Vector store health check",
)
async def vector_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check vector store health and get statistics.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Health check results.
    """
    company_id, _ = _get_company_branch(current_user)

    rag = await get_rag_pipeline()
    stats = await rag.get_stats(company_id=company_id)

    return {
        "success": True,
        "data": stats,
    }


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get RAG knowledge base statistics",
)
async def rag_stats(
    branch_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["super_admin", "company_admin", "branch_manager"])
    ),
) -> Dict[str, Any]:
    """Get RAG knowledge base statistics.

    Args:
        branch_id: Optional branch filter.
        db: Database session.
        current_user: Authenticated admin/manager user.

    Returns:
        Statistics.
    """
    company_id, user_branch_id = _get_company_branch(current_user)
    effective_branch_id = branch_id or user_branch_id

    rag = await get_rag_pipeline()
    stats = await rag.get_stats(
        company_id=company_id,
        branch_id=effective_branch_id,
    )

    return {
        "success": True,
        "data": stats,
    }


# ---------------------------------------------------------------------------
# Branch Knowledge Stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats/branch/{branch_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get branch-specific knowledge statistics",
)
async def branch_stats(
    branch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["super_admin", "company_admin", "branch_manager"])
    ),
) -> Dict[str, Any]:
    """Get knowledge statistics for a specific branch.

    Args:
        branch_id: Branch ID.
        db: Database session.
        current_user: Authenticated admin/manager user.

    Returns:
        Branch statistics.
    """
    company_id, _ = _get_company_branch(current_user)

    rag = await get_rag_pipeline()
    stats = await rag.get_stats(
        company_id=company_id,
        branch_id=branch_id,
    )

    return {
        "success": True,
        "data": stats,
    }


# ---------------------------------------------------------------------------
# Trigger Re-index
# ---------------------------------------------------------------------------


@router.post(
    "/reindex",
    response_model=Dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger re-index for the current company",
)
async def trigger_reindex(
    entity_types: Optional[List[str]] = Query(
        default=None,
        description="Varlik turleri",
    ),
    incremental: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(["super_admin", "company_admin"])
    ),
) -> Dict[str, Any]:
    """Trigger a re-index task for the current company.

    Args:
        entity_types: Entity types to re-index.
        incremental: Only re-index changed entities.
        db: Database session.
        current_user: Authenticated admin user.

    Returns:
        Task dispatch information.
    """
    company_id, _ = _get_company_branch(current_user)

    from app.ai.reindex_tasks import reindex_company

    result = reindex_company.delay(
        company_id=company_id,
        entity_types=entity_types,
        incremental=incremental,
    )

    return {
        "success": True,
        "data": {
            "task_id": result.id,
            "company_id": company_id,
            "entity_types": entity_types or ["product", "post", "customer", "prompt"],
            "incremental": incremental,
            "status": "dispatched",
        },
    }
