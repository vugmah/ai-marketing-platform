"""
AI Module - Vector Memory & RAG System

Provides:
- Vector store (pgvector + in-memory fallback)
- Embedding service (OpenAI + sentence-transformers + fallback)
- Semantic search with cosine similarity
- Company/branch-aware retrieval
- RAG pipeline (retrieval + generation)
- Document chunking and ingestion
- Re-index Celery tasks
- Ingestion cache for embeddings
"""

from app.ai.embeddings import EmbeddingService, get_embedding_service
from app.ai.rag import RAGPipeline, get_rag_pipeline
from app.ai.retrieval import ContextRetriever, get_retriever
from app.ai.vector_store import VectorStore, get_vector_store

__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "RAGPipeline",
    "get_rag_pipeline",
    "ContextRetriever",
    "get_retriever",
    "VectorStore",
    "get_vector_store",
]
