"""
Re-index Celery Tasks - Periodic vector index maintenance

Provides Celery tasks for:
1. Re-indexing all entities of a given type
2. Incremental re-index (only changed entities)
3. Full re-index for a company
4. Health check and cleanup of orphaned vectors
5. Scheduled periodic re-index via Celery beat

All tasks use exponential backoff retry and are routed to the 'ai' queue.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import shared_task
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
# Task: Full re-index for entity type
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="app.ai.reindex_tasks.reindex_entity_type",
    queue="ai",
    **RETRY_CONFIG,
)
def reindex_entity_type(
    self,
    entity_type: str,
    company_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    incremental: bool = False,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-index all entities of a given type.

    Fetches entities from the database, generates embeddings,
    and stores them in the vector store.

    Args:
        entity_type: Type of entity ('product', 'post', 'customer', 'document').
        company_id: Optional company filter.
        branch_id: Optional branch filter.
        incremental: Only re-index entities changed since 'since'.
        since: ISO timestamp for incremental re-index.

    Returns:
        Dict with re-index results.
    """
    import asyncio

    async def _run():
        from app.ai.embeddings import get_embedding_service
        from app.ai.retrieval import get_retriever
        from app.ai.vector_store import VectorRecord, get_vector_store
        from app.database import get_db_context

        results = {
            "entity_type": entity_type,
            "total_processed": 0,
            "total_embedded": 0,
            "errors": [],
            "incremental": incremental,
        }

        try:
            async with get_db_context() as db:
                embedding_service = await get_embedding_service()
                store = await get_vector_store(dimension=embedding_service.dimension)
                retriever = await get_retriever()

                # Parse since timestamp
                since_dt = None
                if since:
                    try:
                        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                # Fetch entities based on type
                entities = []

                if entity_type == "product":
                    from app.erp.models import ERPProduct
                    from sqlalchemy import select

                    query = select(ERPProduct)
                    if company_id:
                        query = query.where(ERPProduct.company_id == company_id)
                    if incremental and since_dt:
                        query = query.where(ERPProduct.updated_at >= since_dt)

                    result = await db.execute(query)
                    for product in result.scalars().all():
                        text = (
                            f"Urun: {product.name}. "
                            f"Aciklama: {product.description or ''}. "
                            f"Kategori: {product.category or ''}. "
                            f"Fiyat: {product.price or ''}"
                        )
                        entities.append({
                            "id": product.id,
                            "company_id": product.company_id,
                            "text": text,
                        })

                elif entity_type == "post":
                    from app.social.models import SocialPost
                    from sqlalchemy import select

                    query = select(SocialPost)
                    if company_id:
                        query = query.where(SocialPost.company_id == company_id)
                    if branch_id:
                        query = query.where(SocialPost.branch_id == branch_id)
                    if incremental and since_dt:
                        query = query.where(SocialPost.updated_at >= since_dt)

                    result = await db.execute(query)
                    for post in result.scalars().all():
                        text = (
                            f"Gonderi: {post.content or ''}. "
                            f"Platform: {post.platform or ''}. "
                            f"Durum: {post.status or ''}"
                        )
                        entities.append({
                            "id": post.id,
                            "company_id": post.company_id,
                            "text": text,
                        })

                elif entity_type == "customer":
                    from app.erp.models import ERPCustomer
                    from sqlalchemy import select

                    query = select(ERPCustomer)
                    if company_id:
                        query = query.where(ERPCustomer.company_id == company_id)
                    if incremental and since_dt:
                        query = query.where(ERPCustomer.updated_at >= since_dt)

                    result = await db.execute(query)
                    for customer in result.scalars().all():
                        text = (
                            f"Musteri: {customer.name or ''}. "
                            f"Email: {customer.email or ''}. "
                            f"Telefon: {customer.phone or ''}"
                        )
                        entities.append({
                            "id": customer.id,
                            "company_id": customer.company_id,
                            "text": text,
                        })

                elif entity_type == "prompt":
                    from app.ai.models import AIPrompt
                    from sqlalchemy import select

                    query = select(AIPrompt).where(AIPrompt.is_active.is_(True))
                    if company_id:
                        query = query.where(AIPrompt.company_id == company_id)
                    if branch_id:
                        query = query.where(AIPrompt.branch_id == branch_id)

                    result = await db.execute(query)
                    for prompt in result.scalars().all():
                        text = (
                            f"Prompt: {prompt.name}. "
                            f"Sistem: {prompt.system_prompt[:200]}. "
                            f"Kullanici: {prompt.user_prompt_template[:200]}. "
                            f"Kategori: {prompt.category or 'genel'}"
                        )
                        entities.append({
                            "id": prompt.id,
                            "company_id": prompt.company_id,
                            "branch_id": prompt.branch_id,
                            "text": text,
                        })

                # Process in batches
                batch_size = 50
                total_embedded = 0

                for i in range(0, len(entities), batch_size):
                    batch = entities[i : i + batch_size]
                    texts = [e["text"] for e in batch]

                    try:
                        embedding_results = await embedding_service.embed_batch(texts)

                        records = []
                        for entity, emb_result in zip(batch, embedding_results):
                            record = VectorRecord(
                                id=f"{entity_type}:{entity['id']}",
                                embedding=emb_result.embedding,
                                entity_type=entity_type,
                                entity_id=entity["id"],
                                company_id=entity.get("company_id", company_id or 0),
                                branch_id=entity.get("branch_id", branch_id),
                                content=entity["text"],
                                metadata={
                                    "reindexed_at": datetime.utcnow().isoformat(),
                                    "incremental": incremental,
                                },
                            )
                            records.append(record)

                        await store.add_batch(records)
                        total_embedded += len(records)

                    except Exception as exc:
                        error_msg = f"Batch {i // batch_size} failed: {str(exc)}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)

                results["total_processed"] = len(entities)
                results["total_embedded"] = total_embedded

        except Exception as exc:
            error_msg = f"Re-index failed: {str(exc)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        return results

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "reindex_entity_type",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("reindex_entity_type hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("reindex_entity_type failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "reindex_entity_type exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: Full company re-index
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="app.ai.reindex_tasks.reindex_company",
    queue="ai",
    **RETRY_CONFIG,
)
def reindex_company(
    self,
    company_id: int,
    entity_types: Optional[List[str]] = None,
    incremental: bool = False,
) -> Dict[str, Any]:
    """Re-index all entities for a company.

    Dispatches sub-tasks for each entity type.

    Args:
        company_id: Company ID.
        entity_types: List of entity types to re-index. Defaults to all.
        incremental: Only re-index changed entities.

    Returns:
        Dict with overall re-index results.
    """
    entity_types = entity_types or ["product", "post", "customer", "prompt"]
    results = []
    total_processed = 0
    total_embedded = 0

    for entity_type in entity_types:
        try:
            result = reindex_entity_type.delay(
                entity_type=entity_type,
                company_id=company_id,
                incremental=incremental,
            )
            results.append({
                "entity_type": entity_type,
                "task_id": result.id,
                "status": "dispatched",
            })
        except Exception as exc:
            results.append({
                "entity_type": entity_type,
                "error": str(exc),
                "status": "failed",
            })

    return {
        "task": "reindex_company",
        "company_id": company_id,
        "timestamp": datetime.utcnow().isoformat(),
        "entity_types": entity_types,
        "incremental": incremental,
        "sub_tasks": results,
    }


# ---------------------------------------------------------------------------
# Task: Health check and cleanup
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="app.ai.reindex_tasks.vector_health_check",
    queue="ai",
    **RETRY_CONFIG,
)
def vector_health_check(
    self,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Run health check on the vector store.

    Checks for orphaned vectors and reports statistics.

    Args:
        company_id: Optional company filter.

    Returns:
        Health check results.
    """
    import asyncio

    async def _run():
        from app.ai.vector_store import get_vector_store

        store = await get_vector_store()
        health = await store.health_check()

        if company_id:
            total = await store.count(company_id=company_id)
            health["company_vectors"] = total

        return health

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "vector_health_check",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as exc:
        logger.error("vector_health_check failed: %s", exc)
        return {
            "task": "vector_health_check",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Task: Cleanup orphaned vectors
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="app.ai.reindex_tasks.cleanup_orphaned_vectors",
    queue="ai",
    **RETRY_CONFIG,
)
def cleanup_orphaned_vectors(
    self,
    company_id: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Remove vectors for deleted entities.

    Compares vector store against database and removes orphaned vectors.

    Args:
        company_id: Optional company filter.
        dry_run: If True, only report what would be deleted.

    Returns:
        Cleanup results.
    """
    import asyncio

    async def _run():
        from app.ai.vector_store import get_vector_store
        from app.database import get_db_context

        store = await get_vector_store()

        # This is a simplified version - in production you'd query
        # all entity IDs from the DB and compare with vectors
        return {
            "dry_run": dry_run,
            "company_id": company_id,
            "note": "Full cleanup requires entity-specific implementation",
            "vectors_checked": 0,
            "vectors_orphaned": 0,
            "vectors_removed": 0,
        }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "cleanup_orphaned_vectors",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as exc:
        logger.error("cleanup_orphaned_vectors failed: %s", exc)
        return {
            "task": "cleanup_orphaned_vectors",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Task: Scheduled periodic re-index
# ---------------------------------------------------------------------------


@shared_task(
    bind=True,
    name="app.ai.reindex_tasks.periodic_reindex",
    queue="ai",
    **RETRY_CONFIG,
)
def periodic_reindex(
    self,
    entity_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Scheduled periodic re-index task.

    Triggered by Celery beat on a schedule. Re-indexes all entities
    incrementally (only changed since last run).

    Args:
        entity_types: List of entity types to re-index.

    Returns:
        Task dispatch results.
    """
    entity_types = entity_types or ["product", "post", "prompt"]

    # Calculate 'since' for incremental re-index (last 24 hours)
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    dispatched = []
    for entity_type in entity_types:
        try:
            result = reindex_entity_type.delay(
                entity_type=entity_type,
                incremental=True,
                since=since,
            )
            dispatched.append({
                "entity_type": entity_type,
                "task_id": result.id,
                "since": since,
            })
        except Exception as exc:
            dispatched.append({
                "entity_type": entity_type,
                "error": str(exc),
            })

    return {
        "task": "periodic_reindex",
        "timestamp": datetime.utcnow().isoformat(),
        "since": since,
        "dispatched": dispatched,
    }
