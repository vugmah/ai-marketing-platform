"""Vector Embedding & Similarity Search Module.

Embedding uretimi ve benzerlik arama islemleri.
- sentence-transformers ile embedding uretimi
- Cosine similarity search
- In-memory ve Redis vector cache
- Batched embedding uretimi

Not: Tam vektor DB (Qdrant/Pinecone) entegrasyonu icin
migration path mevcuttur. Mevcut implementasyon JSON + cosine similarity.
"""

import json
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Sentence Transformers Lazy Import
# =============================================================================

# sentence-transformers opsiyonel dependency
# Model yuklenemezse fallback: random embedding (dev/test)
_transformers = None
_model = None
_model_name = None
_model_dim = None


def _get_transformers():
    """Lazy load transformers kutuphanesi."""
    global _transformers
    if _transformers is None:
        try:
            import sentence_transformers
            _transformers = sentence_transformers
        except ImportError:
            _transformers = False  # type: ignore[assignment]
            logger.warning("sentence-transformers not installed, using fallback embeddings")
    return _transformers


def _load_model(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """Embedding modelini yukle (lazy)."""
    global _model, _model_name, _model_dim
    if _model is not None and _model_name == model_name:
        return _model

    st = _get_transformers()
    if st:
        try:
            _model = st.SentenceTransformer(model_name)
            _model_name = model_name
            _model_dim = _model.get_sentence_embedding_dimension()
            logger.info("embedding_model_loaded", model=model_name, dimension=_model_dim)
            return _model
        except Exception as e:
            logger.error("embedding_model_load_failed", error=str(e), model=model_name)
            _model = False  # type: ignore[assignment]
    else:
        _model = False  # type: ignore[assignment]
    return _model


def get_embedding_dimension(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> int:
    """Model embedding boyutunu dondur."""
    global _model_dim
    if _model_dim is not None:
        return _model_dim

    model = _load_model(model_name)
    if model and model is not False:
        _model_dim = model.get_sentence_embedding_dimension()
        return _model_dim
    return 384  # Default fallback


# =============================================================================
# Embedding Generator
# =============================================================================

class EmbeddingGenerator:
    """Embedding uretim sinifi.

    Text chunk'larindan vektor embedding uretir.
    Batched isleme ile performans saglar.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        use_fallback: bool = False,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_fallback = use_fallback
        self._model = None
        self._dimension = 384  # Default

    def _ensure_model(self):
        """Modeli yukle (lazy)."""
        if self._model is None and not self.use_fallback:
            self._model = _load_model(self.model_name)
            if self._model and self._model is not False:
                self._dimension = self._model.get_sentence_embedding_dimension()

    def generate(self, texts: List[str]) -> List[List[float]]:
        """Metin listesi icin embedding uret.

        Args:
            texts: Embedding'i uretilecek metin listesi.

        Returns:
            Embedding vektorleri listesi.
        """
        if not texts:
            return []

        self._ensure_model()

        if self._model and self._model is not False:
            try:
                embeddings = self._model.encode(
                    texts,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                return embeddings.tolist()
            except Exception as e:
                logger.error("embedding_generation_failed", error=str(e), count=len(texts))
                return self._fallback_embeddings(texts)
        else:
            return self._fallback_embeddings(texts)

    def generate_single(self, text: str) -> List[float]:
        """Tek metin icin embedding uret.

        Args:
            text: Embedding'i uretilecek metin.

        Returns:
            Embedding vektoru.
        """
        embeddings = self.generate([text])
        return embeddings[0] if embeddings else []

    def _fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Fallback embedding (model yokken).

        Her metin icin sabit boyutlu deterministic embedding uretir.
        Gelistirme/test ortami icin uygundur.
        """
        import hashlib

        results = []
        for text in texts:
            # Metin hash'ini embedding vektorune donustur (deterministic)
            hash_bytes = hashlib.md5(text.encode("utf-8")).digest()
            # Hash'ten float degerler uret ve normalize et
            vector = []
            for i in range(self._dimension):
                val = (hash_bytes[i % len(hash_bytes)] / 255.0) * 2 - 1
                vector.append(float(val))
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0:
                vector = [v / norm for v in vector]
            results.append(vector)
        return results

    @property
    def dimension(self) -> int:
        """Embedding boyutunu dondur."""
        return self._dimension


# =============================================================================
# Similarity Search
# =============================================================================

class SimilarityEngine:
    """Benzerlik arama motoru.

    Cosine similarity ile vektor tabanli arama yapar.
    Gelecekte Qdrant/Pinecone entegrasyonuna migration path mevcuttur.
    """

    def __init__(self, embedding_dim: int = 384) -> None:
        self.embedding_dim = embedding_dim

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Iki vektor arasinda cosine similarity hesapla.

        Args:
            a: Birinci vektor.
            b: Ikinci vektor.

        Returns:
            Cosine similarity degeri (-1 ile 1 arasi).
        """
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    def search(
        self,
        query_embedding: List[float],
        document_embeddings: List[Tuple[int, List[float]]],  # (chunk_id, vector)
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """En yakin k chunk'i bul.

        Args:
            query_embedding: Sorgu embedding vektoru.
            document_embeddings: (chunk_id, embedding) listesi.
            top_k: Donulecek sonuc sayisi.
            min_score: Minimum benzerlik skoru.

        Returns:
            Sirali benzerlik sonuclari.
        """
        results = []

        for chunk_id, doc_embedding in document_embeddings:
            score = self.cosine_similarity(query_embedding, doc_embedding)
            if score >= min_score:
                results.append({
                    "chunk_id": chunk_id,
                    "similarity_score": round(score, 6),
                })

        # Sirala (buyukten kucuge)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def search_with_content(
        self,
        query_embedding: List[float],
        documents: List[Dict[str, Any]],  # {"chunk_id": int, "vector": list, "content": str, ...}
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Icerikli benzerlik arama.

        Args:
            query_embedding: Sorgu embedding vektoru.
            documents: Chunk bilgilerini iceren dict listesi.
            top_k: Donulecek sonuc sayisi.
            min_score: Minimum benzerlik skoru.

        Returns:
            Icerikli sirali benzerlik sonuclari.
        """
        results = []

        for doc in documents:
            chunk_id = doc.get("chunk_id", 0)
            doc_embedding = doc.get("vector", doc.get("vector_json", []))
            score = self.cosine_similarity(query_embedding, doc_embedding)
            if score >= min_score:
                result = {
                    "chunk_id": chunk_id,
                    "similarity_score": round(score, 6),
                    "content": doc.get("content", ""),
                    "chunk_type": doc.get("chunk_type", "paragraph"),
                    "source_section": doc.get("source_section"),
                    "keywords": doc.get("keywords", []),
                    "knowledge_base_id": doc.get("knowledge_base_id", 0),
                }
                results.append(result)

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]


# =============================================================================
# Vector Cache (Redis)
# =============================================================================

class VectorCache:
    """Redis tabanli vektor cache.

    Sorgu sonuclarini ve embedding'leri cache'ler.
    """

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._redis = None

    async def _get_redis(self):
        """Redis baglantisini al."""
        if self._redis is None:
            try:
                from app.redis_client import get_redis_client
                self._redis = await get_redis_client()
            except Exception as e:
                logger.warning("redis_unavailable_for_vector_cache", error=str(e))
                return None
        return self._redis

    def _cache_key(self, prefix: str, identifier: str) -> str:
        """Cache key olustur."""
        return f"knowledge:{prefix}:{identifier}"

    async def get_embedding(self, text_hash: str) -> Optional[List[float]]:
        """Cache'den embedding al."""
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            key = self._cache_key("emb", text_hash)
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("vector_cache_get_error", error=str(e))
        return None

    async def set_embedding(self, text_hash: str, embedding: List[float]) -> None:
        """Embedding'i cache'e kaydet."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            key = self._cache_key("emb", text_hash)
            await redis.setex(key, self.ttl, json.dumps(embedding))
        except Exception as e:
            logger.warning("vector_cache_set_error", error=str(e))

    async def get_search_results(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Arama sonuclarini cache'den al."""
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            key = self._cache_key("search", query_hash)
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("search_cache_get_error", error=str(e))
        return None

    async def set_search_results(
        self,
        query_hash: str,
        results: List[Dict[str, Any]],
        ttl: Optional[int] = None,
    ) -> None:
        """Arama sonuclarini cache'e kaydet."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            key = self._cache_key("search", query_hash)
            cache_ttl = ttl or self.ttl
            await redis.setex(key, cache_ttl, json.dumps(results))
        except Exception as e:
            logger.warning("search_cache_set_error", error=str(e))


# =============================================================================
# Batch Embedding Pipeline
# =============================================================================

class BatchEmbeddingPipeline:
    """Batch embedding pipeline.

    Toplu chunk'larin embedding'ini uretir ve veritabanina kaydeder.
    Celery task icin kullanilir.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
    ) -> None:
        self.generator = EmbeddingGenerator(model_name, batch_size)
        self.similarity = SimilarityEngine(self.generator.dimension)
        self.cache = VectorCache()

    def process_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Chunk listesinin embedding'ini uret.

        Args:
            chunks: {"content": str, "chunk_id": int, ...} dict listesi.

        Returns:
            Embedding eklenmis chunk listesi.
        """
        if not chunks:
            return []

        start_time = time.time()

        # Metinleri ayir
        texts = [c["content"] for c in chunks if c.get("content")]

        # Embedding uret
        embeddings = self.generator.generate(texts)

        # Chunk'lara embedding ekle
        result = []
        for i, chunk in enumerate(chunks):
            if i < len(embeddings):
                chunk["vector_json"] = embeddings[i]
                chunk["embedding_model"] = self.generator.model_name
                chunk["embedding_dimension"] = self.generator.dimension
                result.append(chunk)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            "batch_embedding_complete",
            count=len(result),
            dimension=self.generator.dimension,
            model=self.generator.model_name,
            time_ms=round(elapsed_ms, 2),
        )

        return result

    def search(
        self,
        query: str,
        chunk_embeddings: List[Dict[str, Any]],
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Semantik arama yap.

        Args:
            query: Arama sorgusu.
            chunk_embeddings: Embedding'li chunk listesi.
            top_k: Sonuc sayisi.
            min_score: Minimum skor.

        Returns:
            Benzerlik sonuclari.
        """
        start_time = time.time()

        query_embedding = self.generator.generate_single(query)
        results = self.similarity.search_with_content(
            query_embedding, chunk_embeddings, top_k, min_score
        )

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(
            "semantic_search_complete",
            query=query[:50],
            results=len(results),
            time_ms=round(elapsed_ms, 2),
        )

        return results


# =============================================================================
# Factory
# =============================================================================

def get_embedding_pipeline(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> BatchEmbeddingPipeline:
    """Embedding pipeline factory fonksiyonu."""
    return BatchEmbeddingPipeline(model_name, batch_size)
