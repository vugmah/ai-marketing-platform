"""Celery tasks for AI/ML processing.

Provides background tasks for AI operations:
- generate_embedding: Generate vector embeddings for products, posts, etc.
- analyze_sentiment: Analyze sentiment of text (comments, reviews, messages)
- generate_suggestions: Generate AI marketing suggestions
- generate_recommendations: Generate marketing recommendations
- batch_analyze_sentiment: Batch sentiment analysis for multiple texts
- update_embeddings_index: Refresh vector index with new embeddings

All tasks use exponential backoff retry (max 5) and are routed
to the 'ai' queue by default.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import chord, group, shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------

RETRY_CONFIG = {
    "max_retries": 5,
    "default_retry_delay": 10,
    "retry_backoff": True,
    "retry_backoff_max": 300,
    "retry_jitter": True,
}


# ---------------------------------------------------------------------------
# Task: generate_embedding
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.ai.tasks.generate_embedding",
    queue="ai",
    **RETRY_CONFIG,
)
def generate_embedding(
    self,
    entity_type: str,
    entity_ids: Optional[List[int]] = None,
    company_id: Optional[int] = None,
    model: str = "text-embedding-3-small",
) -> Dict[str, Any]:
    """Generate vector embeddings for entities using OpenAI embeddings API.

    NOTE: This task stores embeddings in Redis for short-term caching only.
    Full RAG (vector search, retrieval, context injection) is NOT IMPLEMENTED.
    See app/ai/rag.py for planned RAG module details.

    Args:
        entity_type: Type of entity ('product', 'post', 'customer', 'comment').
        entity_ids: Specific entity IDs to embed. If None, processes all.
        company_id: Optional company filter.
        model: OpenAI embedding model to use.

    Returns:
        Dict with embedding generation results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.redis_client import get_redis_client

        embeddings_generated = 0
        errors = []

        async with get_db_context() as db:
            # Collect texts to embed based on entity type
            texts_to_embed = []

            if entity_type == "product":
                from app.erp.models import ERPProduct
                from sqlalchemy import select

                query = select(ERPProduct)
                if entity_ids:
                    query = query.where(ERPProduct.id.in_(entity_ids))
                if company_id:
                    query = query.where(ERPProduct.company_id == company_id)

                result = await db.execute(query)
                products = list(result.scalars().all())

                for product in products:
                    text = f"{product.name}. {product.description or ''}. Category: {product.category or ''}"
                    texts_to_embed.append({
                        "id": product.id,
                        "text": text,
                        "entity_type": "product",
                        "entity_id": product.id,
                    })

            elif entity_type == "post":
                from app.social.models import SocialPost
                from sqlalchemy import select

                query = select(SocialPost)
                if entity_ids:
                    query = query.where(SocialPost.id.in_(entity_ids))

                result = await db.execute(query)
                posts = list(result.scalars().all())

                for post in posts:
                    text = f"{post.content or ''}"
                    texts_to_embed.append({
                        "id": post.id,
                        "text": text,
                        "entity_type": "post",
                        "entity_id": post.id,
                    })

            elif entity_type == "customer":
                from app.erp.models import ERPCustomer
                from sqlalchemy import select

                query = select(ERPCustomer)
                if entity_ids:
                    query = query.where(ERPCustomer.id.in_(entity_ids))
                if company_id:
                    query = query.where(ERPCustomer.company_id == company_id)

                result = await db.execute(query)
                customers = list(result.scalars().all())

                for customer in customers:
                    text = f"{customer.name or ''}. {customer.email or ''}"
                    texts_to_embed.append({
                        "id": customer.id,
                        "text": text,
                        "entity_type": "customer",
                        "entity_id": customer.id,
                    })

            # Generate embeddings via OpenAI API
            if texts_to_embed:
                import httpx
                import json
                import hashlib

                from app.config import settings
                from app.ai.constants import OPENAI_CHAT_COMPLETIONS_ENDPOINT

                api_key = getattr(settings, "OPENAI_API_KEY", "")
                if not api_key:
                    raise ValueError("OpenAI API key not configured")

                # Process in batches of 100 (OpenAI limit)
                batch_size = 100
                redis = await get_redis_client()

                for i in range(0, len(texts_to_embed), batch_size):
                    batch = texts_to_embed[i : i + batch_size]
                    texts = [item["text"] for item in batch]

                    try:
                        async with httpx.AsyncClient(timeout=60.0) as client:
                            response = await client.post(
                                "https://api.openai.com/v1/embeddings",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "model": model,
                                    "input": texts,
                                },
                            )
                            response.raise_for_status()
                            data = response.json()

                            # Store embeddings in Redis with TTL
                            for item, embedding_data in zip(batch, data["data"]):
                                embedding = embedding_data["embedding"]
                                cache_key = f"embedding:{entity_type}:{item['entity_id']}"
                                await redis.setex(
                                    cache_key,
                                    86400 * 7,  # 7 days TTL
                                    json.dumps(embedding),
                                )
                                embeddings_generated += 1

                    except Exception as exc:
                        error_msg = f"Batch {i // batch_size} failed: {str(exc)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

        return {
            "entity_type": entity_type,
            "total_texts": len(texts_to_embed),
            "embeddings_generated": embeddings_generated,
            "errors": errors,
        }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "generate_embedding",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("generate_embedding hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("generate_embedding failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "generate_embedding exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: analyze_sentiment
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.ai.tasks.analyze_sentiment",
    queue="ai",
    **RETRY_CONFIG,
)
def analyze_sentiment(
    self,
    text: str,
    context: Optional[str] = None,
    language: str = "auto",
) -> Dict[str, Any]:
    """Analyze sentiment of a given text.

    Uses OpenAI API to classify sentiment as positive, negative, or neutral
    with a confidence score.

    Args:
        text: The text to analyze.
        context: Optional context (e.g., 'social_comment', 'review', 'message').
        language: Language hint or 'auto' for detection.

    Returns:
        Dict with sentiment analysis results.
    """
    import asyncio

    async def _run():
        import json

        import httpx

        from app.ai.constants import OPENAI_CHAT_COMPLETIONS_ENDPOINT
        from app.config import settings

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        system_prompt = (
            "You are a sentiment analysis expert. Analyze the sentiment of the given text. "
            "Respond ONLY with a JSON object in this exact format:\n"
            '{"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0, "score": -1.0 to 1.0, "key_phrases": ["phrase1", "phrase2"]}'
        )

        context_hint = f"\nContext: {context}" if context else ""
        user_prompt = f"Analyze this text:{context_hint}\n\n{text[:2000]}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 256,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)

            return {
                "text_preview": text[:100],
                "sentiment": result.get("sentiment", "unknown"),
                "confidence": float(result.get("confidence", 0)),
                "score": float(result.get("score", 0)),
                "key_phrases": result.get("key_phrases", []),
                "context": context,
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "analyze_sentiment",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("analyze_sentiment hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("analyze_sentiment failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "analyze_sentiment exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: batch_analyze_sentiment
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.ai.tasks.batch_analyze_sentiment",
    queue="ai",
    **RETRY_CONFIG,
)
def batch_analyze_sentiment(
    self,
    items: List[Dict[str, Any]],
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze sentiment for multiple texts in batch.

    Uses a single API call for efficiency with multiple texts.

    Args:
        items: List of dicts with 'id' and 'text' keys.
        context: Optional context for analysis.

    Returns:
        Dict with batch analysis results.
    """
    import asyncio

    async def _run():
        import json

        import httpx

        from app.config import settings

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        if not items:
            return {"results": [], "total": 0}

        system_prompt = (
            "You are a sentiment analysis expert. Analyze sentiment for each text. "
            "Respond ONLY with a JSON array where each element is:\n"
            '{"id": "item_id", "sentiment": "positive|negative|neutral", "confidence": 0.0-1.0, "score": -1.0 to 1.0}'
        )

        # Format items for the prompt
        formatted_items = []
        for item in items:
            item_id = item.get("id", "unknown")
            text = item.get("text", "")[:500]  # Limit text length
            formatted_items.append(f"[{item_id}] {text}")

        items_text = "\n---\n".join(formatted_items)
        context_hint = f"\nContext: {context}" if context else ""
        user_prompt = f"Analyze sentiment for each item:{context_hint}\n\n{items_text}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            # Handle both array and object with results key
            results = parsed if isinstance(parsed, list) else parsed.get("results", [])

        return {
            "total": len(items),
            "analyzed": len(results),
            "results": results,
            "context": context,
        }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "batch_analyze_sentiment",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("batch_analyze_sentiment hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("batch_analyze_sentiment failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "batch_analyze_sentiment exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: generate_suggestions
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.ai.tasks.generate_suggestions",
    queue="ai",
    **RETRY_CONFIG,
)
def generate_suggestions(
    self,
    company_id: int,
    branch_id: Optional[int] = None,
    trigger_type: str = "periodic",
    context: Optional[Dict[str, Any]] = None,
    count: int = 3,
) -> Dict[str, Any]:
    """Generate AI marketing suggestions for a company.

    Args:
        company_id: The company ID.
        branch_id: Optional branch ID.
        trigger_type: Type of trigger (periodic, event, manual).
        context: Contextual data for suggestion generation.
        count: Number of suggestions to generate.

    Returns:
        Dict with generated suggestions.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.ai.service import AISuggestionService

        context = context or {}

        async with get_db_context() as db:
            service = AISuggestionService(db=db)
            suggestions = await service.generate_suggestions(
                company_id=company_id,
                branch_id=branch_id,
                trigger_type=trigger_type,
                context=context,
                count=count,
            )

            return {
                "company_id": company_id,
                "suggestions_generated": len(suggestions),
                "suggestions": [
                    {
                        "id": s.id,
                        "trigger_type": s.trigger_type.value,
                        "context": s.context,
                        "response": s.response[:500] if s.response else None,
                        "tokens_used": s.tokens_used,
                    }
                    for s in suggestions
                ],
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "generate_suggestions",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("generate_suggestions hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("generate_suggestions failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "generate_suggestions exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: generate_recommendations
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.ai.tasks.generate_recommendations",
    queue="ai",
    **RETRY_CONFIG,
)
def generate_recommendations(
    self,
    company_id: int,
    branch_id: Optional[int] = None,
    categories: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    count: int = 5,
) -> Dict[str, Any]:
    """Generate AI marketing recommendations for a company.

    Args:
        company_id: The company ID.
        branch_id: Optional branch ID.
        categories: List of recommendation categories.
        context: Analytics data context.
        count: Number of recommendations to generate.

    Returns:
        Dict with generated recommendations.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.ai.service import RecommendationEngine

        context = context or {}

        async with get_db_context() as db:
            engine = RecommendationEngine(db=db)
            recommendations = await engine.generate_recommendations(
                company_id=company_id,
                branch_id=branch_id,
                categories=categories,
                context=context,
                count=count,
            )

            return {
                "company_id": company_id,
                "recommendations_generated": len(recommendations),
                "recommendations": [
                    {
                        "id": r.id,
                        "category": r.category.value,
                        "title": r.title,
                        "description": r.description[:200] if r.description else None,
                        "confidence_score": float(r.confidence_score),
                        "data_source": r.data_source,
                        "action_items": r.action_items,
                    }
                    for r in recommendations
                ],
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "generate_recommendations",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("generate_recommendations hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("generate_recommendations failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "generate_recommendations exhausted all 5 retries. Task moved to dead letter."
            )
            raise
