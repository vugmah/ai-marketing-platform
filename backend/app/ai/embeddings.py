"""
Embeddings Service - sentence-transformers + OpenAI

Provides multiple embedding backends:
1. OpenAIEmbeddings: OpenAI API (text-embedding-3-small, text-embedding-3-large)
2. SentenceTransformersEmbeddings: Local sentence-transformers models
3. FallbackEmbeddings: Rule-based fallback when no ML model is available

Features:
- Unified interface for all embedding providers
- Ingestion cache to avoid recomputing embeddings
- Batch embedding support
- Async interface with httpx
- Dimension validation
- Cost tracking for OpenAI embeddings

Usage:
    service = EmbeddingService()
    embedding = await service.embed("text to embed")
    embeddings = await service.embed_batch(["text1", "text2"])
"""

import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

import httpx
import numpy as np

from app.redis_client import get_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OPENAI_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSION = 1536
EMBEDDING_CACHE_TTL = 86400 * 30  # 30 days
BATCH_SIZE = 100  # OpenAI max batch size

OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

OPENAI_EMBEDDING_COST_PER_1K = {
    "text-embedding-3-small": 0.00002,
    "text-embedding-3-large": 0.00013,
    "text-embedding-ada-002": 0.00010,
}

# Sentence-transformers models and their dimensions
ST_MODELS = {
    "all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "paraphrase-multilingual-MiniLM-L12-v2": 384,
}
DEFAULT_ST_MODEL = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""

    embedding: List[float]
    model: str
    dimension: int
    cached: bool = False
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Base Protocol
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        """Embed a single text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed multiple texts."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        ...


# ---------------------------------------------------------------------------
# 1. OpenAI Embeddings
# ---------------------------------------------------------------------------


class OpenAIEmbeddings(EmbeddingProvider):
    """OpenAI API embedding provider.

    Supports text-embedding-3-small, text-embedding-3-large, and ada-002.
    Tracks cost and latency for each request.

    Args:
        model: OpenAI embedding model name.
        api_key: OpenAI API key (optional, reads from settings).
    """

    def __init__(
        self,
        model: str = DEFAULT_OPENAI_MODEL,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self._api_key = api_key
        self._dimension = OPENAI_EMBEDDING_DIMENSIONS.get(model, DEFAULT_DIMENSION)
        self._base_url = "https://api.openai.com/v1"

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        try:
            from app.config import settings
            return getattr(settings, "OPENAI_API_KEY", "")
        except ImportError:
            return ""

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.model

    def _calculate_cost(self, num_texts: int) -> float:
        """Calculate estimated cost for embedding request."""
        cost_per_1k = OPENAI_EMBEDDING_COST_PER_1K.get(self.model, 0.00002)
        # Rough estimate: ~150 tokens per text on average
        estimated_tokens = num_texts * 150
        return (estimated_tokens / 1000.0) * cost_per_1k

    async def embed(self, text: str) -> EmbeddingResult:
        """Embed a single text via OpenAI API.

        Args:
            text: Text to embed.

        Returns:
            EmbeddingResult with vector and metadata.
        """
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed multiple texts via OpenAI API.

        Processes in batches of 100 (OpenAI limit).
        Returns embedding results with cost tracking.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("OpenAI API key not configured for embeddings")

        if not texts:
            return []

        cost_estimate = self._calculate_cost(len(texts))
        start_time = time.time()

        all_embeddings: List[List[float]] = []

        # Process in batches
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": batch,
                        "dimensions": self._dimension,
                    },
                )
                response.raise_for_status()
                data = response.json()

                for item in data["data"]:
                    all_embeddings.append(item["embedding"])

        latency_ms = int((time.time() - start_time) * 1000)

        return [
            EmbeddingResult(
                embedding=emb,
                model=self.model,
                dimension=self._dimension,
                cached=False,
                cost_usd=cost_estimate / len(texts),
                latency_ms=latency_ms // len(texts) if texts else 0,
            )
            for emb in all_embeddings
        ]


# ---------------------------------------------------------------------------
# 2. Sentence-Transformers Embeddings
# ---------------------------------------------------------------------------


class SentenceTransformersEmbeddings(EmbeddingProvider):
    """Local sentence-transformers embedding provider.

    Runs entirely locally without API calls. Good for:
    - Privacy-sensitive deployments
    - High-throughput scenarios
    - Cost-sensitive deployments

    Args:
        model: Sentence-transformers model name.
        device: Computation device ('cpu', 'cuda', 'mps').
    """

    def __init__(
        self,
        model: str = DEFAULT_ST_MODEL,
        device: Optional[str] = None,
    ):
        self.model_name_str = model
        self.device = device or self._auto_device()
        self._model: Optional[Any] = None
        self._dimension = ST_MODELS.get(model, 384)
        self._lock: Optional[Any] = None

    def _auto_device(self) -> str:
        """Auto-detect the best available device."""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _load_model(self) -> Any:
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading sentence-transformers model: %s (device=%s)",
                self.model_name_str,
                self.device,
            )
            self._model = SentenceTransformer(self.model_name_str, device=self.device)
            logger.info("Sentence-transformers model loaded successfully")
            return self._model
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            raise

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self.model_name_str

    async def embed(self, text: str) -> EmbeddingResult:
        """Embed a single text locally."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Embed multiple texts locally.

        Uses sentence-transformers for efficient batch encoding.
        """
        if not texts:
            return []

        import asyncio

        start_time = time.time()

        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()

        def _encode():
            model = self._load_model()
            embeddings = model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.tolist()

        embeddings = await loop.run_in_executor(None, _encode)
        latency_ms = int((time.time() - start_time) * 1000)

        return [
            EmbeddingResult(
                embedding=emb,
                model=self.model_name_str,
                dimension=self._dimension,
                cached=False,
                cost_usd=0.0,  # Local - no API cost
                latency_ms=latency_ms // len(texts) if texts else 0,
            )
            for emb in embeddings
        ]


# ---------------------------------------------------------------------------
# 3. Fallback Embeddings
# ---------------------------------------------------------------------------


class FallbackEmbeddings(EmbeddingProvider):
    """Rule-based fallback embedding provider.

    Uses a simple hash-based approach when no ML model is available.
    Not suitable for semantic search but allows the system to function.

    Args:
        dimension: Output embedding dimension.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return f"fallback-{self._dimension}d"

    async def embed(self, text: str) -> EmbeddingResult:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate deterministic pseudo-embeddings.

        Uses a combination of hash functions to create a deterministic
        but pseudo-random embedding. This allows the system to function
        even when no embedding model is available.
        """
        results: List[EmbeddingResult] = []
        for txt in texts:
            embedding = self._hash_to_embedding(txt)
            results.append(
                EmbeddingResult(
                    embedding=embedding,
                    model=self.model_name,
                    dimension=self._dimension,
                    cached=False,
                    cost_usd=0.0,
                    latency_ms=0,
                )
            )
        return results

    def _hash_to_embedding(self, text: str) -> List[float]:
        """Convert text to a deterministic embedding via hashing."""
        # Use multiple hash functions for better distribution
        hashes = [
            hashlib.md5(text.encode()).hexdigest(),
            hashlib.sha256(text.encode()).hexdigest(),
            hashlib.blake2b(text.encode(), digest_size=32).hexdigest(),
        ]

        # Convert hex to float values
        values: List[float] = []
        hash_str = "".join(hashes)

        # Generate dimension float values from the hash
        for i in range(self._dimension):
            start = (i * 8) % len(hash_str)
            chunk = hash_str[start : start + 8]
            val = int(chunk, 16) / (2**32)  # Normalize to [0, 1]
            values.append(val)

        # L2 normalize
        arr = np.array(values, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm

        return arr.tolist()


# ---------------------------------------------------------------------------
# 4. Ingestion Cache
# ---------------------------------------------------------------------------


class EmbeddingCache:
    """Cache for embeddings to avoid recomputing.

    Uses Redis with content-hash keys for deduplication.
    TTL-based expiration for cache freshness.

    Args:
        ttl: Cache TTL in seconds (default 30 days).
        prefix: Redis key prefix.
    """

    def __init__(
        self,
        ttl: int = EMBEDDING_CACHE_TTL,
        prefix: str = "embedding:cache",
    ):
        self.ttl = ttl
        self.prefix = prefix

    def _make_key(self, text: str, model: str) -> str:
        """Create a cache key from text hash and model name."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self.prefix}:{model}:{text_hash}"

    async def get(self, text: str, model: str) -> Optional[List[float]]:
        """Get cached embedding for text.

        Args:
            text: Original text.
            model: Model name used for embedding.

        Returns:
            Cached embedding vector or None.
        """
        try:
            cache = await get_cache()
            key = self._make_key(text, model)
            cached = await cache.get(key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.debug("Embedding cache get failed: %s", exc)
        return None

    async def set(self, text: str, model: str, embedding: List[float]) -> None:
        """Cache an embedding.

        Args:
            text: Original text.
            model: Model name used for embedding.
            embedding: The embedding vector to cache.
        """
        try:
            cache = await get_cache()
            key = self._make_key(text, model)
            await cache.setex(key, self.ttl, json.dumps(embedding))
        except Exception as exc:
            logger.debug("Embedding cache set failed: %s", exc)

    async def get_batch(
        self, items: List[Tuple[str, str]]
    ) -> Dict[int, List[float]]:
        """Get cached embeddings for multiple texts.

        Args:
            items: List of (text, model) tuples.

        Returns:
            Dict mapping index to cached embedding for hits.
        """
        hits: Dict[int, List[float]] = {}
        for i, (text, model) in enumerate(items):
            cached = await self.get(text, model)
            if cached is not None:
                hits[i] = cached
        return hits

    async def set_batch(
        self, items: List[Tuple[str, str, List[float]]]
    ) -> None:
        """Cache multiple embeddings.

        Args:
            items: List of (text, model, embedding) tuples.
        """
        for text, model, embedding in items:
            await self.set(text, model, embedding)


# ---------------------------------------------------------------------------
# 5. Unified Embedding Service
# ---------------------------------------------------------------------------


class EmbeddingService:
    """Unified embedding service with cache and multiple backends.

    Automatically selects the best available provider:
    1. OpenAI (if API key configured and USE_OPENAI_EMBEDDINGS=true)
    2. Sentence-transformers (if installed)
    3. Fallback (always available)

    Args:
        provider: Explicit provider override ('openai', 'sentence_transformers', 'fallback').
        model: Model name for the selected provider.
        cache_enabled: Whether to use the ingestion cache.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        cache_enabled: bool = True,
    ):
        self.provider_type = provider or self._detect_provider()
        self.model = model
        self.cache_enabled = cache_enabled
        self._provider: Optional[EmbeddingProvider] = None
        self._cache = EmbeddingCache() if cache_enabled else None

    def _detect_provider(self) -> str:
        """Auto-detect the best available embedding provider."""
        try:
            from app.config import settings

            if getattr(settings, "USE_OPENAI_EMBEDDINGS", True):
                api_key = getattr(settings, "OPENAI_API_KEY", "")
                if api_key:
                    return "openai"
        except ImportError:
            pass

        # Check if sentence-transformers is available
        try:
            import sentence_transformers  # noqa: F401
            return "sentence_transformers"
        except ImportError:
            pass

        return "fallback"

    def _get_provider(self) -> EmbeddingProvider:
        """Lazy-initialize the embedding provider."""
        if self._provider is not None:
            return self._provider

        if self.provider_type == "openai":
            model = self.model or DEFAULT_OPENAI_MODEL
            self._provider = OpenAIEmbeddings(model=model)
            logger.info("EmbeddingService: using OpenAI (%s)", model)

        elif self.provider_type == "sentence_transformers":
            model = self.model or DEFAULT_ST_MODEL
            self._provider = SentenceTransformersEmbeddings(model=model)
            logger.info("EmbeddingService: using sentence-transformers (%s)", model)

        else:
            dim = 384
            if self.model and self.model.isdigit():
                dim = int(self.model)
            self._provider = FallbackEmbeddings(dimension=dim)
            logger.info("EmbeddingService: using fallback (%dd)", dim)

        return self._provider

    @property
    def dimension(self) -> int:
        return self._get_provider().dimension

    @property
    def provider_name(self) -> str:
        return self._get_provider().model_name

    async def embed(
        self,
        text: str,
        use_cache: bool = True,
    ) -> EmbeddingResult:
        """Embed a single text.

        Checks cache first if enabled, then delegates to the provider.

        Args:
            text: Text to embed.
            use_cache: Whether to check cache first.

        Returns:
            EmbeddingResult with the embedding vector.
        """
        provider = self._get_provider()

        # Check cache
        if use_cache and self._cache:
            cached = await self._cache.get(text, provider.model_name)
            if cached is not None:
                return EmbeddingResult(
                    embedding=cached,
                    model=provider.model_name,
                    dimension=provider.dimension,
                    cached=True,
                    cost_usd=0.0,
                    latency_ms=0,
                )

        # Generate embedding
        result = await provider.embed(text)

        # Store in cache
        if use_cache and self._cache and not result.cached:
            await self._cache.set(text, provider.model_name, result.embedding)

        return result

    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[EmbeddingResult]:
        """Embed multiple texts with cache deduplication.

        Checks cache for all texts first, only generates embeddings
        for cache misses. Results are returned in the same order as input.

        Args:
            texts: List of texts to embed.
            use_cache: Whether to use cache.

        Returns:
            List of EmbeddingResult in the same order as input.
        """
        if not texts:
            return []

        provider = self._get_provider()

        if use_cache and self._cache:
            # Check cache for all texts
            cache_hits: Dict[int, List[float]] = {}
            cache_misses: List[Tuple[int, str]] = []

            for i, txt in enumerate(texts):
                cached = await self._cache.get(txt, provider.model_name)
                if cached is not None:
                    cache_hits[i] = cached
                else:
                    cache_misses.append((i, txt))

            if cache_misses:
                # Generate embeddings for misses
                miss_texts = [txt for _, txt in cache_misses]
                miss_results = await provider.embed_batch(miss_texts)

                # Cache new embeddings
                cache_items: List[Tuple[str, str, List[float]]] = []
                for (orig_idx, txt), result in zip(cache_misses, miss_results):
                    cache_items.append((txt, provider.model_name, result.embedding))
                await self._cache.set_batch(cache_items)

                # Merge results
                all_results: List[Optional[EmbeddingResult]] = [None] * len(texts)

                for idx, emb in cache_hits.items():
                    all_results[idx] = EmbeddingResult(
                        embedding=emb,
                        model=provider.model_name,
                        dimension=provider.dimension,
                        cached=True,
                        cost_usd=0.0,
                        latency_ms=0,
                    )

                for (orig_idx, _), result in zip(cache_misses, miss_results):
                    all_results[orig_idx] = EmbeddingResult(
                        embedding=result.embedding,
                        model=provider.model_name,
                        dimension=provider.dimension,
                        cached=False,
                        cost_usd=result.cost_usd,
                        latency_ms=result.latency_ms,
                    )

                return [r for r in all_results if r is not None]
            else:
                # All cache hits
                return [
                    EmbeddingResult(
                        embedding=cache_hits[i],
                        model=provider.model_name,
                        dimension=provider.dimension,
                        cached=True,
                        cost_usd=0.0,
                        latency_ms=0,
                    )
                    for i in range(len(texts))
                ]

        # No cache - generate all
        return await provider.embed_batch(texts)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_embedding_service: Optional[EmbeddingService] = None


async def get_embedding_service() -> EmbeddingService:
    """Get or create the singleton EmbeddingService.

    Returns:
        EmbeddingService instance.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def reset_embedding_service() -> None:
    """Reset the singleton (mainly for testing)."""
    global _embedding_service
    _embedding_service = None
