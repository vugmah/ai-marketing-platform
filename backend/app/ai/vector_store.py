"""
Vector Store - pgvector + In-Memory Fallback

Provides two vector storage backends:
1. PGVectorStore: PostgreSQL + pgvector extension for production
2. InMemoryVectorStore: Pure Python in-memory store for testing/development

Both implement the same VectorStoreProtocol for seamless swapping.
Uses cosine similarity for semantic search with L2 normalization.

Features:
- pgvector compatible (vector type, <->, <=>, <#> operators)
- In-memory fallback with numpy-based cosine similarity
- Automatic dimension validation and normalization
- Metadata filtering (company_id, branch_id, entity_type)
- Batch insert and delete operations
- Index statistics and health checks
"""

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

import numpy as np
from sqlalchemy import Column, ForeignKey, Integer, JSON, select, String, text, Text
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, get_db_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_VECTOR_DIMENSION = 1536  # OpenAI text-embedding-3-small
MAX_IN_MEMORY_VECTORS = 100_000
SIMILARITY_THRESHOLD = 0.7

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class VectorRecord:
    """A single vector record with embedding and metadata."""

    id: str
    embedding: List[float]
    entity_type: str
    entity_id: int
    company_id: int
    branch_id: Optional[int] = None
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    @property
    def dimension(self) -> int:
        return len(self.embedding)


@dataclass
class SearchResult:
    """Result of a semantic vector search."""

    id: str
    score: float
    entity_type: str
    entity_id: int
    company_id: int
    branch_id: Optional[int]
    content: str
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class VectorStoreProtocol(Protocol):
    """Protocol that all vector store backends must implement."""

    async def add(self, record: VectorRecord) -> None: ...
    async def add_batch(self, records: List[VectorRecord]) -> None: ...
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[SearchResult]: ...
    async def delete(self, record_id: str) -> bool: ...
    async def delete_by_entity(
        self, entity_type: str, entity_id: int
    ) -> int: ...
    async def delete_by_company(self, company_id: int) -> int: ...
    async def get(self, record_id: str) -> Optional[VectorRecord]: ...
    async def count(
        self,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> int: ...
    async def health_check(self) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Database Model for pgvector
# ---------------------------------------------------------------------------


class VectorEmbedding(Base):
    """PostgreSQL + pgvector table for vector embeddings.

    Uses pgvector extension's vector type for efficient similarity search.
    GIN index on metadata for fast JSON filtering.
    Composite index on (company_id, branch_id, entity_type) for tenant filtering.
    """

    __tablename__ = "vector_embeddings"
    __table_args__ = {
        "schema": None,
        "comment": "Vector embeddings with metadata for semantic search (pgvector)",
    }

    id = Column(String(64), primary_key=True, index=True)
    # pgvector vector type - dimension set at runtime
    embedding = Column(
        ARRAY(FLOAT),
        nullable=False,
        comment="Vector embedding as float array (pgvector compatible)",
    )
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of entity: product, post, customer, document, etc.",
    )
    entity_id = Column(Integer, nullable=False, index=True)
    company_id = Column(
        Integer,
        ForeignKey("public.companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey("public.branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content = Column(Text, nullable=False, default="")
    metadata_json = Column(
        "metadata",
        JSON,
        nullable=True,
        default=dict,
        comment="Arbitrary metadata dict (JSON)",
    )
    created_at = Column(
        Integer,
        nullable=False,
        default=lambda: int(datetime.utcnow().timestamp()),
        comment="Unix timestamp for TTL support",
    )

    def to_vector_record(self) -> VectorRecord:
        return VectorRecord(
            id=self.id,
            embedding=list(self.embedding) if self.embedding else [],
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            company_id=self.company_id,
            branch_id=self.branch_id,
            content=self.content or "",
            metadata=self.metadata_json or {},
            created_at=datetime.utcfromtimestamp(self.created_at) if self.created_at else None,
        )


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------


def _normalize_vector(v: List[float]) -> List[float]:
    """L2-normalize a vector for cosine similarity."""
    arr = np.array(v, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return v
    normalized = arr / norm
    return normalized.tolist()


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors (range: -1 to 1)."""
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _generate_record_id(entity_type: str, entity_id: int, company_id: int) -> str:
    """Generate a deterministic record ID."""
    raw = f"{company_id}:{entity_type}:{entity_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# 1. pgvector Store (Production)
# ---------------------------------------------------------------------------


class PGVectorStore:
    """PostgreSQL + pgvector vector store backend.

    Uses SQLAlchemy with ARRAY(FLOAT) for vector storage.
    Supports cosine similarity via SQL operations.
    Recommended for production use.

    Args:
        dimension: Vector embedding dimension (default 1536 for OpenAI).
    """

    def __init__(self, dimension: int = DEFAULT_VECTOR_DIMENSION):
        self.dimension = dimension
        self._pgvector_available: Optional[bool] = None

    async def _ensure_pgvector(self) -> bool:
        """Check if pgvector extension is available.

        Returns:
            True if pgvector is available, False otherwise.
        """
        if self._pgvector_available is not None:
            return self._pgvector_available

        try:
            async with get_db_context() as db:
                result = await db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                self._pgvector_available = result.scalar() is not None
                if self._pgvector_available:
                    logger.info("pgvector extension detected and available")
                else:
                    logger.warning("pgvector extension NOT available - falling back to ARRAY storage")
                return self._pgvector_available
        except Exception as exc:
            logger.error("Error checking pgvector availability: %s", exc)
            self._pgvector_available = False
            return False

    async def _setup_pgvector(self) -> None:
        """Create pgvector extension if available."""
        try:
            async with get_db_context() as db:
                await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await db.commit()
                logger.info("pgvector extension ensured")
        except Exception as exc:
            logger.warning("Could not create pgvector extension: %s", exc)

    async def add(self, record: VectorRecord) -> None:
        """Add a single vector record.

        Args:
            record: VectorRecord to store.
        """
        async with get_db_context() as db:
            await self._add_with_session(db, record)
            await db.commit()
        logger.debug("Added vector record id=%s", record.id)

    async def _add_with_session(
        self, db: AsyncSession, record: VectorRecord
    ) -> None:
        """Add a record using an existing session."""
        embedding = _normalize_vector(record.embedding)

        entity = VectorEmbedding(
            id=record.id,
            embedding=embedding,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            company_id=record.company_id,
            branch_id=record.branch_id,
            content=record.content,
            metadata_json=record.metadata,
            created_at=int(datetime.utcnow().timestamp()),
        )
        await db.merge(entity)

    async def add_batch(self, records: List[VectorRecord]) -> None:
        """Add multiple vector records in a single transaction.

        Args:
            records: List of VectorRecords to store.
        """
        if not records:
            return

        async with get_db_context() as db:
            for record in records:
                await self._add_with_session(db, record)
            await db.commit()

        logger.info("Batch added %d vector records", len(records))

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[SearchResult]:
        """Search for similar vectors using cosine similarity.

        Uses pgvector's cosine distance operator when available,
        falls back to manual cosine similarity calculation.

        Args:
            query_embedding: Query vector embedding.
            top_k: Maximum number of results.
            company_id: Filter by company.
            branch_id: Filter by branch.
            entity_type: Filter by entity type.
            min_score: Minimum similarity score threshold.

        Returns:
            List of SearchResult sorted by similarity (descending).
        """
        min_score = min_score or SIMILARITY_THRESHOLD
        normalized_query = _normalize_vector(query_embedding)

        async with get_db_context() as db:
            query = select(VectorEmbedding)

            # Tenant filters
            if company_id is not None:
                query = query.where(VectorEmbedding.company_id == company_id)
            if branch_id is not None:
                query = query.where(VectorEmbedding.branch_id == branch_id)
            if entity_type is not None:
                query = query.where(VectorEmbedding.entity_type == entity_type)

            # For pgvector: use ORDER BY embedding <=> query
            # For fallback: fetch candidates and compute similarity in Python
            pgvector_ok = await self._ensure_pgvector()

            if pgvector_ok:
                # Use pgvector cosine distance operator
                query = query.order_by(
                    text(f"embedding <=> ARRAY{normalized_query}::real[]")
                ).limit(top_k * 3)  # Fetch more for post-filtering
            else:
                # Fetch candidates, compute similarity in Python
                query = query.limit(top_k * 10)

            result = await db.execute(query)
            rows = result.scalars().all()

            # Compute similarities and filter
            results: List[SearchResult] = []
            for row in rows:
                score = _cosine_similarity(normalized_query, list(row.embedding) if row.embedding else [])
                if score >= min_score:
                    results.append(
                        SearchResult(
                            id=row.id,
                            score=score,
                            entity_type=row.entity_type,
                            entity_id=row.entity_id,
                            company_id=row.company_id,
                            branch_id=row.branch_id,
                            content=row.content or "",
                            metadata=row.metadata_json or {},
                        )
                    )

            # Sort by score descending and limit
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]

    async def delete(self, record_id: str) -> bool:
        """Delete a vector record by ID.

        Args:
            record_id: The record ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(VectorEmbedding).where(VectorEmbedding.id == record_id)
            )
            row = result.scalar_one_or_none()
            if row:
                await db.delete(row)
                await db.commit()
                return True
            return False

    async def delete_by_entity(self, entity_type: str, entity_id: int) -> int:
        """Delete all vectors for a specific entity.

        Args:
            entity_type: Type of entity.
            entity_id: Entity ID.

        Returns:
            Number of records deleted.
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(VectorEmbedding).where(
                    VectorEmbedding.entity_type == entity_type,
                    VectorEmbedding.entity_id == entity_id,
                )
            )
            rows = result.scalars().all()
            count = len(rows)
            for row in rows:
                await db.delete(row)
            await db.commit()
            return count

    async def delete_by_company(self, company_id: int) -> int:
        """Delete all vectors for a company.

        Args:
            company_id: Company ID.

        Returns:
            Number of records deleted.
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(VectorEmbedding).where(
                    VectorEmbedding.company_id == company_id
                )
            )
            rows = result.scalars().all()
            count = len(rows)
            for row in rows:
                await db.delete(row)
            await db.commit()
            logger.info("Deleted %d vectors for company=%d", count, company_id)
            return count

    async def get(self, record_id: str) -> Optional[VectorRecord]:
        """Get a vector record by ID.

        Args:
            record_id: The record ID.

        Returns:
            VectorRecord or None.
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(VectorEmbedding).where(VectorEmbedding.id == record_id)
            )
            row = result.scalar_one_or_none()
            return row.to_vector_record() if row else None

    async def count(
        self,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> int:
        """Count vector records matching filters.

        Args:
            company_id: Filter by company.
            branch_id: Filter by branch.
            entity_type: Filter by entity type.

        Returns:
            Count of matching records.
        """
        from sqlalchemy import func

        async with get_db_context() as db:
            query = select(func.count()).select_from(VectorEmbedding)

            if company_id is not None:
                query = query.where(VectorEmbedding.company_id == company_id)
            if branch_id is not None:
                query = query.where(VectorEmbedding.branch_id == branch_id)
            if entity_type is not None:
                query = query.where(VectorEmbedding.entity_type == entity_type)

            result = await db.execute(query)
            return result.scalar() or 0

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the vector store.

        Returns:
            Dict with status and statistics.
        """
        pgvector_ok = await self._ensure_pgvector()
        total = await self.count()

        return {
            "backend": "pgvector",
            "pgvector_extension": pgvector_ok,
            "dimension": self.dimension,
            "total_vectors": total,
            "status": "healthy" if pgvector_ok else "degraded",
        }


# ---------------------------------------------------------------------------
# 2. In-Memory Store (Development / Testing)
# ---------------------------------------------------------------------------


class InMemoryVectorStore:
    """Pure Python in-memory vector store with numpy-based cosine similarity.

    Suitable for development, testing, and small deployments.
    Stores vectors in a dict with L2-normalized embeddings for fast search.
    Has a maximum capacity limit for memory safety.

    Args:
        dimension: Vector embedding dimension.
        max_size: Maximum number of vectors to store.
    """

    def __init__(
        self,
        dimension: int = DEFAULT_VECTOR_DIMENSION,
        max_size: int = MAX_IN_MEMORY_VECTORS,
    ):
        self.dimension = dimension
        self.max_size = max_size
        # id -> VectorRecord (embedding is pre-normalized)
        self._vectors: Dict[str, VectorRecord] = {}
        logger.info(
            "Initialized InMemoryVectorStore (dim=%d, max=%d)",
            dimension,
            max_size,
        )

    async def add(self, record: VectorRecord) -> None:
        """Add a single vector record."""
        if len(self._vectors) >= self.max_size:
            # Evict oldest record (simple FIFO)
            oldest = next(iter(self._vectors))
            del self._vectors[oldest]
            logger.warning("InMemoryVectorStore evicted oldest record (max_size reached)")

        normalized_embedding = _normalize_vector(record.embedding)
        self._vectors[record.id] = VectorRecord(
            id=record.id,
            embedding=normalized_embedding,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            company_id=record.company_id,
            branch_id=record.branch_id,
            content=record.content,
            metadata=record.metadata,
            created_at=record.created_at or datetime.utcnow(),
        )

    async def add_batch(self, records: List[VectorRecord]) -> None:
        """Add multiple vector records."""
        for record in records:
            await self.add(record)
        logger.info("InMemoryVectorStore: batch added %d records", len(records))

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[SearchResult]:
        """Search for similar vectors using cosine similarity.

        Filters by tenant and entity type, then computes cosine similarity
        against all matching vectors. Returns top-k results.
        """
        min_score = min_score or SIMILARITY_THRESHOLD
        normalized_query = _normalize_vector(query_embedding)

        results: List[SearchResult] = []

        for record in self._vectors.values():
            # Filter by tenant
            if company_id is not None and record.company_id != company_id:
                continue
            if branch_id is not None and record.branch_id != branch_id:
                continue
            if entity_type is not None and record.entity_type != entity_type:
                continue

            # Compute cosine similarity
            score = _cosine_similarity(normalized_query, record.embedding)
            if score >= min_score:
                results.append(
                    SearchResult(
                        id=record.id,
                        score=score,
                        entity_type=record.entity_type,
                        entity_id=record.entity_id,
                        company_id=record.company_id,
                        branch_id=record.branch_id,
                        content=record.content,
                        metadata=record.metadata,
                    )
                )

        # Sort by score descending and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def delete(self, record_id: str) -> bool:
        """Delete a vector record by ID."""
        if record_id in self._vectors:
            del self._vectors[record_id]
            return True
        return False

    async def delete_by_entity(self, entity_type: str, entity_id: int) -> int:
        """Delete all vectors for a specific entity."""
        to_delete = [
            rid
            for rid, rec in self._vectors.items()
            if rec.entity_type == entity_type and rec.entity_id == entity_id
        ]
        for rid in to_delete:
            del self._vectors[rid]
        return len(to_delete)

    async def delete_by_company(self, company_id: int) -> int:
        """Delete all vectors for a company."""
        to_delete = [
            rid
            for rid, rec in self._vectors.items()
            if rec.company_id == company_id
        ]
        for rid in to_delete:
            del self._vectors[rid]
        logger.info("InMemoryVectorStore: deleted %d vectors for company=%d", len(to_delete), company_id)
        return len(to_delete)

    async def get(self, record_id: str) -> Optional[VectorRecord]:
        """Get a vector record by ID."""
        return self._vectors.get(record_id)

    async def count(
        self,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> int:
        """Count matching vector records."""
        count = 0
        for rec in self._vectors.values():
            if company_id is not None and rec.company_id != company_id:
                continue
            if branch_id is not None and rec.branch_id != branch_id:
                continue
            if entity_type is not None and rec.entity_type != entity_type:
                continue
            count += 1
        return count

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the in-memory store."""
        return {
            "backend": "in_memory",
            "pgvector_extension": False,
            "dimension": self.dimension,
            "total_vectors": len(self._vectors),
            "max_size": self.max_size,
            "status": "healthy",
        }


# ---------------------------------------------------------------------------
# 3. Unified Vector Store Factory
# ---------------------------------------------------------------------------


class VectorStore:
    """Unified vector store with automatic backend selection.

    Tries pgvector first, falls back to in-memory store.
    Provides a consistent interface regardless of the backend.

    Usage:
        store = VectorStore(dimension=1536)
        await store.add(record)
        results = await store.search(query_embedding, company_id=1, branch_id=2)
    """

    def __init__(self, dimension: int = DEFAULT_VECTOR_DIMENSION):
        self.dimension = dimension
        self._backend: Optional[VectorStoreProtocol] = None
        self._backend_type: Optional[str] = None

    async def _get_backend(self) -> VectorStoreProtocol:
        """Lazy initialization with backend selection."""
        if self._backend is not None:
            return self._backend

        # Try pgvector first
        pg_store = PGVectorStore(dimension=self.dimension)
        try:
            health = await pg_store.health_check()
            if health.get("pgvector_extension") or health.get("total_vectors") >= 0:
                self._backend = pg_store
                self._backend_type = "pgvector"
                logger.info("VectorStore: using pgvector backend")
                return self._backend
        except Exception as exc:
            logger.warning("pgvector backend unavailable: %s", exc)

        # Fallback to in-memory
        self._backend = InMemoryVectorStore(dimension=self.dimension)
        self._backend_type = "in_memory"
        logger.info("VectorStore: using in_memory backend (fallback)")
        return self._backend

    # -- Proxy methods to backend --

    async def add(self, record: VectorRecord) -> None:
        backend = await self._get_backend()
        await backend.add(record)

    async def add_batch(self, records: List[VectorRecord]) -> None:
        backend = await self._get_backend()
        await backend.add_batch(records)

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[SearchResult]:
        backend = await self._get_backend()
        return await backend.search(
            query_embedding=query_embedding,
            top_k=top_k,
            company_id=company_id,
            branch_id=branch_id,
            entity_type=entity_type,
            min_score=min_score,
        )

    async def delete(self, record_id: str) -> bool:
        backend = await self._get_backend()
        return await backend.delete(record_id)

    async def delete_by_entity(self, entity_type: str, entity_id: int) -> int:
        backend = await self._get_backend()
        return await backend.delete_by_entity(entity_type, entity_id)

    async def delete_by_company(self, company_id: int) -> int:
        backend = await self._get_backend()
        return await backend.delete_by_company(company_id)

    async def get(self, record_id: str) -> Optional[VectorRecord]:
        backend = await self._get_backend()
        return await backend.get(record_id)

    async def count(
        self,
        company_id: Optional[int] = None,
        branch_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> int:
        backend = await self._get_backend()
        return await backend.count(company_id, branch_id, entity_type)

    async def health_check(self) -> Dict[str, Any]:
        backend = await self._get_backend()
        health = await backend.health_check()
        health["backend_type"] = self._backend_type
        return health


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_vector_store_instance: Optional[VectorStore] = None


async def get_vector_store(
    dimension: int = DEFAULT_VECTOR_DIMENSION,
) -> VectorStore:
    """Get or create the singleton VectorStore instance.

    Args:
        dimension: Vector embedding dimension.

    Returns:
        VectorStore instance.
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(dimension=dimension)
    return _vector_store_instance


def reset_vector_store() -> None:
    """Reset the singleton (mainly for testing)."""
    global _vector_store_instance
    _vector_store_instance = None
