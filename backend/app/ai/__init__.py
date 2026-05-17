"""
AI Module - Vector Memory & RAG System
"""

# Lazy imports to avoid circular dependency with companies model
try:
    from app.ai.embeddings import EmbeddingService, get_embedding_service
    from app.ai.rag import RAGPipeline, get_rag_pipeline
    from app.ai.retrieval import ContextRetriever, get_retriever
    from app.ai.vector_store import VectorStore, get_vector_store
except ImportError:
    EmbeddingService = None
    get_embedding_service = None
    RAGPipeline = None
    get_rag_pipeline = None
    ContextRetriever = None
    get_retriever = None
    VectorStore = None
    get_vector_store = None

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
