"""
Retrieval Layer - Company/Branch-Aware Semantic Search

Provides context-aware document retrieval for RAG (Retrieval-Augmented Generation).

Features:
- Semantic search over vector store with cosine similarity
- Company-aware retrieval: scope results to a company
- Branch-aware retrieval: scope results to a specific branch
- Hybrid retrieval: combine semantic + keyword search
- Reranking: re-rank results for better relevance
- Context assembly: format retrieved documents for LLM context injection
- Document chunking: split large documents into retrievable chunks

Usage:
    retriever = ContextRetriever()
    results = await retriever.search(
        query="summer campaign ideas",
        company_id=1,
        branch_id=2,
        top_k=5,
    )
    context = retriever.assemble_context(results)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.ai.embeddings import EmbeddingService, get_embedding_service
from app.ai.vector_store import SearchResult, VectorRecord, get_vector_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 5
DEFAULT_MIN_SCORE = 0.6
MAX_CONTEXT_TOKENS = 4000
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class RetrievedDocument:
    """A retrieved document with relevance score and metadata."""

    id: str
    content: str
    score: float
    entity_type: str
    entity_id: int
    company_id: int
    branch_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0


@dataclass
class RetrievalContext:
    """Assembled context for LLM injection."""

    documents: List[RetrievedDocument]
    context_text: str
    total_tokens_estimate: int
    query: str


# ---------------------------------------------------------------------------
# Document Chunking
# ---------------------------------------------------------------------------


class DocumentChunker:
    """Split documents into chunks for vector storage.

    Uses a sliding window approach with overlap to ensure
    no important context is lost at chunk boundaries.

    Args:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks.

        Args:
            text: Input text to chunk.

        Returns:
            List of text chunks.
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                # Find the last sentence break in the chunk
                for sep in [".\n", "!\n", "?\n", ". ", "! ", "? ", "\n\n", "\n"]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size * 0.5:
                        chunk = chunk[: last_sep + len(sep)]
                        end = start + len(chunk)
                        break

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        return chunks

    def chunk_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Chunk a document and return chunk info.

        Args:
            document_id: Original document ID.
            content: Document content.
            metadata: Document metadata.

        Returns:
            List of chunk dicts with text and metadata.
        """
        chunks = self.chunk_text(content)
        results: List[Dict[str, Any]] = []

        for i, chunk_text in enumerate(chunks):
            chunk_meta = {
                **(metadata or {}),
                "chunk_index": i,
                "total_chunks": len(chunks),
                "original_doc_id": document_id,
            }
            results.append({
                "text": chunk_text,
                "metadata": chunk_meta,
                "chunk_id": f"{document_id}:chunk:{i}",
            })

        return results


# ---------------------------------------------------------------------------
# Context Retriever
# ---------------------------------------------------------------------------


class ContextRetriever:
    """Company/branch-aware context retriever for RAG.

    Provides semantic search over the vector store with tenant isolation.
    Supports hybrid retrieval (semantic + keyword) and reranking.

    Usage:
        retriever = ContextRetriever()

        # Simple semantic search
        results = await retriever.search(
            query="campaign optimization",
            company_id=1,
            top_k=5,
        )

        # Branch-aware search
        results = await retriever.search(
            query="local promotions",
            company_id=1,
            branch_id=3,
            entity_types=["document", "product"],
            top_k=10,
        )

        # Get assembled context for LLM
        context = await retriever.retrieve_context(
            query="summer sale ideas",
            company_id=1,
            branch_id=2,
        )
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self._embedding_service = embedding_service
        self._chunker = DocumentChunker()

    async def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = await get_embedding_service()
        return self._embedding_service

    # ------------------------------------------------------------------
    # Core Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        min_score: Optional[float] = None,
    ) -> List[RetrievedDocument]:
        """Perform semantic search over the vector store.

        Args:
            query: Search query text.
            company_id: Filter by company (tenant isolation).
            branch_id: Filter by branch (branch-aware).
            entity_types: Filter by entity types.
            top_k: Maximum number of results.
            min_score: Minimum similarity threshold.

        Returns:
            List of RetrievedDocument sorted by relevance.
        """
        min_score = min_score or DEFAULT_MIN_SCORE

        # 1. Generate query embedding
        embedding_service = await self._get_embedding_service()
        query_embedding_result = await embedding_service.embed(query)
        query_embedding = query_embedding_result.embedding

        # 2. Search vector store
        store = await get_vector_store(dimension=embedding_service.dimension)

        # If multiple entity types, search each and merge
        all_results: List[SearchResult] = []

        if entity_types:
            per_type_k = max(top_k // len(entity_types), 2)
            for etype in entity_types:
                results = await store.search(
                    query_embedding=query_embedding,
                    top_k=per_type_k,
                    company_id=company_id,
                    branch_id=branch_id,
                    entity_type=etype,
                    min_score=min_score,
                )
                all_results.extend(results)
        else:
            all_results = await store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                company_id=company_id,
                branch_id=branch_id,
                entity_type=None,
                min_score=min_score,
            )

        # 3. Sort by score and deduplicate
        all_results.sort(key=lambda r: r.score, reverse=True)

        seen_ids: set = set()
        documents: List[RetrievedDocument] = []

        for rank, result in enumerate(all_results, 1):
            if result.id in seen_ids:
                continue
            seen_ids.add(result.id)

            documents.append(
                RetrievedDocument(
                    id=result.id,
                    content=result.content,
                    score=result.score,
                    entity_type=result.entity_type,
                    entity_id=result.entity_id,
                    company_id=result.company_id,
                    branch_id=result.branch_id,
                    metadata=result.metadata,
                    rank=rank,
                )
            )

            if len(documents) >= top_k:
                break

        logger.info(
            "Retrieved %d documents for query='%s' company=%s branch=%s",
            len(documents),
            query[:50],
            company_id,
            branch_id,
        )

        return documents

    # ------------------------------------------------------------------
    # Hybrid Search (Semantic + Keyword)
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query: str,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> List[RetrievedDocument]:
        """Hybrid search combining semantic and keyword matching.

        Args:
            query: Search query text.
            company_id: Filter by company.
            branch_id: Filter by branch.
            entity_types: Filter by entity types.
            top_k: Maximum number of results.
            semantic_weight: Weight for semantic scores (0-1).
            keyword_weight: Weight for keyword scores (0-1).

        Returns:
            List of RetrievedDocument with combined scores.
        """
        # Semantic search
        semantic_results = await self.search(
            query=query,
            company_id=company_id,
            branch_id=branch_id,
            entity_types=entity_types,
            top_k=top_k * 3,
            min_score=0.3,  # Lower threshold for hybrid
        )

        # Keyword scoring
        query_terms = self._extract_keywords(query)
        scored_docs: Dict[str, RetrievedDocument] = {}

        for doc in semantic_results:
            # Semantic score (already 0-1)
            sem_score = doc.score

            # Keyword score
            kw_score = self._keyword_score(doc.content, query_terms)

            # Combined score
            combined = (semantic_weight * sem_score) + (keyword_weight * kw_score)

            doc.score = combined
            scored_docs[doc.id] = doc

        # Sort by combined score
        results = sorted(scored_docs.values(), key=lambda d: d.score, reverse=True)

        # Re-rank
        for i, doc in enumerate(results, 1):
            doc.rank = i

        return results[:top_k]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        # Simple keyword extraction
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "out", "off", "over", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "both", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "and", "but", "if",
            "or", "because", "until", "while", "what", "which", "who",
            "whom", "this", "that", "these", "those", "am", "it", "its",
        }
        return [w for w in words if w not in stop_words and len(w) > 2]

    def _keyword_score(self, content: str, keywords: List[str]) -> float:
        """Compute keyword match score (0-1)."""
        if not keywords or not content:
            return 0.0

        content_lower = content.lower()
        matches = sum(1 for kw in keywords if kw in content_lower)
        return min(matches / len(keywords), 1.0)

    # ------------------------------------------------------------------
    # Context Assembly
    # ------------------------------------------------------------------

    async def retrieve_context(
        self,
        query: str,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_types: Optional[List[str]] = None,
        top_k: int = DEFAULT_TOP_K,
        max_context_tokens: int = MAX_CONTEXT_TOKENS,
    ) -> RetrievalContext:
        """Retrieve and assemble context for LLM injection.

        Performs semantic search, then formats results into a context
        string suitable for injection into an LLM prompt.

        Args:
            query: User query.
            company_id: Company filter.
            branch_id: Branch filter.
            entity_types: Entity type filter.
            top_k: Maximum documents to retrieve.
            max_context_tokens: Maximum estimated tokens for context.

        Returns:
            RetrievalContext with documents and formatted context text.
        """
        documents = await self.search(
            query=query,
            company_id=company_id,
            branch_id=branch_id,
            entity_types=entity_types,
            top_k=top_k,
        )

        context_text = self.assemble_context(documents, query)
        token_estimate = len(context_text) // 4  # Rough estimate

        # Trim if too long
        if token_estimate > max_context_tokens:
            context_text = self._trim_context(context_text, max_context_tokens)
            token_estimate = len(context_text) // 4

        return RetrievalContext(
            documents=documents,
            context_text=context_text,
            total_tokens_estimate=token_estimate,
            query=query,
        )

    def assemble_context(
        self,
        documents: List[RetrievedDocument],
        query: str = "",
    ) -> str:
        """Format retrieved documents into a context string.

        Args:
            documents: Retrieved documents.
            query: Original query for context.

        Returns:
            Formatted context string for LLM injection.
        """
        if not documents:
            return ""

        parts: List[str] = []
        parts.append("=== BILGI KAYNAKLARI ===")
        parts.append("")

        for i, doc in enumerate(documents, 1):
            parts.append(f"[{i}] Kaynak: {doc.entity_type} (ID: {doc.entity_id})")
            if doc.metadata:
                meta_str = ", ".join(
                    f"{k}={v}" for k, v in doc.metadata.items()
                    if k not in ("chunk_index", "total_chunks", "original_doc_id")
                )
                if meta_str:
                    parts.append(f"    Meta: {meta_str}")
            parts.append(f"    Icerik: {doc.content[:500]}")
            parts.append("")

        parts.append("=== BILGI KAYNAKLARI SONU ===")

        return "\n".join(parts)

    def _trim_context(self, context: str, max_tokens: int) -> str:
        """Trim context to fit within token limit.

        Tries to keep complete document sections.
        """
        max_chars = max_tokens * 4
        if len(context) <= max_chars:
            return context

        # Find the last complete section before the limit
        sections = context.split("\n\n[")
        trimmed = sections[0]
        for section in sections[1:]:
            candidate = trimmed + "\n\n[" + section
            if len(candidate) > max_chars:
                break
            trimmed = candidate

        return trimmed + "\n\n... (icerik kisaltildi)"

    # ------------------------------------------------------------------
    # Document Ingestion
    # ------------------------------------------------------------------

    async def ingest_document(
        self,
        content: str,
        entity_type: str,
        entity_id: int,
        company_id: int,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk: bool = True,
    ) -> int:
        """Ingest a document into the vector store.

        Chunks the document, generates embeddings, and stores in the
        vector store with tenant metadata.

        Args:
            content: Document content.
            entity_type: Type of entity (product, post, document, etc.).
            entity_id: Entity ID.
            company_id: Company ID.
            branch_id: Optional branch ID.
            metadata: Additional metadata.
            chunk: Whether to chunk the document.

        Returns:
            Number of chunks ingested.
        """
        from app.ai.vector_store import VectorRecord, get_vector_store

        embedding_service = await self._get_embedding_service()
        store = await get_vector_store(dimension=embedding_service.dimension)

        if chunk and len(content) > CHUNK_SIZE:
            chunks = self._chunker.chunk_document(
                document_id=f"{entity_type}:{entity_id}",
                content=content,
                metadata=metadata,
            )
        else:
            chunks = [{
                "text": content,
                "metadata": metadata or {},
                "chunk_id": f"{entity_type}:{entity_id}:chunk:0",
            }]

        # Generate embeddings for all chunks
        texts = [c["text"] for c in chunks]
        embedding_results = await embedding_service.embed_batch(texts)

        # Create vector records
        records: List[VectorRecord] = []
        for chunk_info, emb_result in zip(chunks, embedding_results):
            record = VectorRecord(
                id=chunk_info["chunk_id"],
                embedding=emb_result.embedding,
                entity_type=entity_type,
                entity_id=entity_id,
                company_id=company_id,
                branch_id=branch_id,
                content=chunk_info["text"],
                metadata={
                    **(metadata or {}),
                    **chunk_info["metadata"],
                },
            )
            records.append(record)

        # Store in vector store
        await store.add_batch(records)

        logger.info(
            "Ingested %d chunks for %s:%d (company=%d, branch=%s)",
            len(records),
            entity_type,
            entity_id,
            company_id,
            branch_id,
        )

        return len(records)

    async def delete_document(
        self,
        entity_type: str,
        entity_id: int,
    ) -> int:
        """Delete a document and its chunks from the vector store.

        Args:
            entity_type: Type of entity.
            entity_id: Entity ID.

        Returns:
            Number of chunks deleted.
        """
        store = await get_vector_store()
        count = await store.delete_by_entity(entity_type, entity_id)
        logger.info(
            "Deleted %d vectors for %s:%d", count, entity_type, entity_id
        )
        return count

    # ------------------------------------------------------------------
    # Company/Branch aware helpers
    # ------------------------------------------------------------------

    async def get_company_knowledge_stats(
        self,
        company_id: int,
    ) -> Dict[str, Any]:
        """Get knowledge base statistics for a company.

        Args:
            company_id: Company ID.

        Returns:
            Dict with statistics.
        """
        store = await get_vector_store()
        total = await store.count(company_id=company_id)

        # Count by entity type (we'd need to query distinct, simplified here)
        return {
            "company_id": company_id,
            "total_vectors": total,
            "entity_types": {},  # Would need additional query
        }

    async def get_branch_knowledge_stats(
        self,
        company_id: int,
        branch_id: int,
    ) -> Dict[str, Any]:
        """Get knowledge base statistics for a branch.

        Args:
            company_id: Company ID.
            branch_id: Branch ID.

        Returns:
            Dict with statistics.
        """
        store = await get_vector_store()
        total = await store.count(company_id=company_id, branch_id=branch_id)

        return {
            "company_id": company_id,
            "branch_id": branch_id,
            "total_vectors": total,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_retriever_instance: Optional[ContextRetriever] = None


async def get_retriever() -> ContextRetriever:
    """Get or create the singleton ContextRetriever.

    Returns:
        ContextRetriever instance.
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = ContextRetriever()
    return _retriever_instance


def reset_retriever() -> None:
    """Reset the singleton (mainly for testing)."""
    global _retriever_instance
    _retriever_instance = None
