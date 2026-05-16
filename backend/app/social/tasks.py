"""Celery tasks for Social Media synchronization.

Provides background tasks for syncing social media data:
- sync_posts: Sync posts/content from social platforms
- sync_comments: Sync comments across platforms
- sync_messages: Sync direct messages/conversations
- sync_analytics: Sync analytics/metrics from platforms
- sync_competitors: Sync competitor data

All tasks use exponential backoff retry (max 5) and are routed
to the 'social' queue by default.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import chain, group, shared_task
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
# Helper: Get active social accounts
# ---------------------------------------------------------------------------

async def _get_active_accounts(db, account_id: Optional[int] = None):
    """Fetch active social accounts."""
    from app.social.models import SocialAccount, AccountStatus
    from sqlalchemy import select

    if account_id:
        result = await db.execute(
            select(SocialAccount).where(
                SocialAccount.id == account_id,
                SocialAccount.status == AccountStatus.ACTIVE,
            )
        )
        return [result.scalar_one_or_none()]

    result = await db.execute(
        select(SocialAccount).where(SocialAccount.status == AccountStatus.ACTIVE)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Task: sync_posts
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.sync_posts",
    queue="social",
    **RETRY_CONFIG,
)
def sync_posts(
    self,
    account_id: Optional[int] = None,
    platform: Optional[str] = None,
    company_id: Optional[int] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Sync posts/content from connected social media accounts.

    Args:
        account_id: Specific account to sync. If None, syncs all active accounts.
        platform: Filter by platform (instagram, facebook, tiktok, etc.)
        company_id: Optional company filter.
        limit: Maximum posts per account.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, AccountStatus, SocialPlatform
        from app.social.service import CredentialManager
        from sqlalchemy import select

        results = []
        cred_mgr = CredentialManager()

        async with get_db_context() as db:
            # Build query - only active accounts
            query = select(SocialAccount).where(SocialAccount.status == AccountStatus.ACTIVE)
            if account_id:
                query = query.where(SocialAccount.id == account_id)
            elif company_id:
                query = query.where(SocialAccount.company_id == company_id)

            result = await db.execute(query)
            accounts = list(result.scalars().all())

            for account in accounts:
                if not account:
                    continue

                if platform and account.platform.value != platform:
                    continue

                client = None
                try:
                    posts_synced = 0
                    errors = []

                    # Decrypt access token
                    access_token = cred_mgr.decrypt_access_token(account.access_token)

                    # Platform-specific sync logic
                    if account.platform == SocialPlatform.INSTAGRAM:
                        from app.social.service import InstagramClient
                        client = InstagramClient(
                            access_token=access_token,
                            instagram_account_id=account.account_id,
                        )
                        media_list = await client.get_media_list(limit=limit)
                        posts_synced = len(media_list)

                    elif account.platform == SocialPlatform.FACEBOOK:
                        from app.social.service import MetaClient
                        client = MetaClient(
                            access_token=access_token,
                            page_id=account.account_id,
                        )
                        posts = await client.get_page_posts(limit=limit)
                        posts_synced = len(posts)

                    elif account.platform == SocialPlatform.TIKTOK:
                        from app.social.service import TikTokClient
                        client = TikTokClient(
                            access_token=access_token,
                            open_id=account.account_id,
                        )
                        videos = await client.list_videos(max_count=limit)
                        posts_synced = len(videos.get("data", []))

                    else:
                        errors.append(f"Unsupported platform: {account.platform.value}")

                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "success",
                            "posts_synced": posts_synced,
                            "errors": errors,
                        }
                    )

                except Exception as exc:
                    logger.error(
                        "Post sync failed for account %s (%s): %s",
                        account.id,
                        account.platform.value,
                        exc,
                    )
                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )
                finally:
                    if client:
                        await client.close()

        return {
            "task": "sync_posts",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": len(accounts),
            "total_synced": sum(r.get("posts_synced", 0) for r in results),
            "total_failed": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_posts hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_posts failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_posts exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_comments
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.sync_comments",
    queue="social",
    **RETRY_CONFIG,
)
def sync_comments(
    self,
    account_id: Optional[int] = None,
    post_id: Optional[str] = None,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync comments from social media posts.

    Args:
        account_id: Specific account to sync. If None, syncs all active accounts.
        post_id: Specific post to sync comments for. If None, syncs recent posts.
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, SocialPost, SocialComment, SocialPlatform
        from sqlalchemy import select, desc

        results = []

        async with get_db_context() as db:
            query = select(SocialAccount)
            if account_id:
                query = query.where(SocialAccount.id == account_id)
            elif company_id:
                query = query.where(SocialAccount.company_id == company_id)

            result = await db.execute(query)
            accounts = list(result.scalars().all())

            for account in accounts:
                if not account:
                    continue

                try:
                    comments_synced = 0

                    if account.platform == SocialPlatform.INSTAGRAM:
                        from app.social.service import InstagramClient
                        client = InstagramClient(access_token=account.access_token)

                        # Get recent posts first
                        media_list = await client.get_media_list(limit=10)
                        for media in media_list:
                            media_comments = await client.get_media_comments(media["id"])
                            comments_synced += len(media_comments)

                    elif account.platform == SocialPlatform.FACEBOOK:
                        from app.social.service import MetaClient
                        client = MetaClient(
                            access_token=account.access_token,
                            page_id=account.external_id,
                        )
                        posts = await client.get_page_posts(limit=10)
                        for post in posts:
                            post_comments = await client.get_post_comments(post["id"])
                            comments_synced += len(post_comments)

                    elif account.platform == SocialPlatform.TIKTOK:
                        from app.social.service import TikTokClient
                        client = TikTokClient(access_token=account.access_token)
                        videos = await client.list_videos(max_count=10)
                        for video in videos.get("data", []):
                            video_id = video.get("id")
                            if video_id:
                                comments = await client.get_video_comments(video_id)
                                comments_synced += len(comments.get("data", []))

                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "success",
                            "comments_synced": comments_synced,
                        }
                    )

                except Exception as exc:
                    logger.error(
                        "Comment sync failed for account %s: %s",
                        account.id,
                        exc,
                    )
                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_comments",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": len(accounts),
            "total_comments_synced": sum(
                r.get("comments_synced", 0) for r in results
            ),
            "total_failed": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_comments hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_comments failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_comments exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_messages
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.sync_messages",
    queue="social",
    **RETRY_CONFIG,
)
def sync_messages(
    self,
    account_id: Optional[int] = None,
    conversation_id: Optional[str] = None,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Sync direct messages from social platforms.

    Args:
        account_id: Specific account to sync. If None, syncs all active accounts.
        conversation_id: Specific conversation to sync.
        company_id: Optional company filter.

    Returns:
        Dict with sync results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, SocialPlatform
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            query = select(SocialAccount)
            if account_id:
                query = query.where(SocialAccount.id == account_id)
            elif company_id:
                query = query.where(SocialAccount.company_id == company_id)

            result = await db.execute(query)
            accounts = list(result.scalars().all())

            for account in accounts:
                if not account:
                    continue

                try:
                    messages_synced = 0

                    # WhatsApp messages
                    if account.platform == SocialPlatform.WHATSAPP:
                        from app.social.service import WhatsAppClient
                        client = WhatsAppClient(
                            access_token=account.access_token,
                            phone_number_id=account.external_id,
                        )
                        # WhatsApp webhook-based, messages are received via webhook
                        messages_synced = 0

                    # Telegram messages
                    elif account.platform == SocialPlatform.TELEGRAM:
                        # Telegram uses bot webhooks
                        messages_synced = 0

                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "success",
                            "messages_synced": messages_synced,
                        }
                    )

                except Exception as exc:
                    logger.error(
                        "Message sync failed for account %s: %s",
                        account.id,
                        exc,
                    )
                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_messages",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": len(accounts),
            "total_messages_synced": sum(
                r.get("messages_synced", 0) for r in results
            ),
            "total_failed": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_messages hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_messages failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_messages exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: sync_analytics
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.sync_analytics",
    queue="social",
    **RETRY_CONFIG,
)
def sync_analytics(
    self,
    account_id: Optional[int] = None,
    company_id: Optional[int] = None,
    metric_period: str = "day",
) -> Dict[str, Any]:
    """Sync analytics/metrics from social platforms.

    Args:
        account_id: Specific account to sync.
        company_id: Optional company filter.
        metric_period: Time period for metrics (day, week, lifetime).

    Returns:
        Dict with analytics data.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, SocialPlatform
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            query = select(SocialAccount)
            if account_id:
                query = query.where(SocialAccount.id == account_id)
            elif company_id:
                query = query.where(SocialAccount.company_id == company_id)

            result = await db.execute(query)
            accounts = list(result.scalars().all())

            for account in accounts:
                if not account:
                    continue

                try:
                    insights = {}

                    if account.platform == SocialPlatform.INSTAGRAM:
                        from app.social.service import InstagramClient
                        client = InstagramClient(
                            access_token=account.access_token,
                            instagram_account_id=account.external_id,
                        )
                        insights = await client.get_insights(metric_period=metric_period)

                    elif account.platform == SocialPlatform.FACEBOOK:
                        from app.social.service import MetaClient
                        client = MetaClient(
                            access_token=account.access_token,
                            page_id=account.external_id,
                        )
                        insights = await client.get_page_insights(metric_period=metric_period)

                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "success",
                            "insights": insights,
                        }
                    )

                except Exception as exc:
                    logger.error(
                        "Analytics sync failed for account %s: %s",
                        account.id,
                        exc,
                    )
                    results.append(
                        {
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

        return {
            "task": "sync_analytics",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": len(accounts),
            "total_failed": sum(1 for r in results if r["status"] == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("sync_analytics hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("sync_analytics failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "sync_analytics exhausted all 5 retries. Task moved to dead letter."
            )
            raise


# ---------------------------------------------------------------------------
# Task: publish_scheduled_post
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.publish_scheduled_post",
    queue="social",
    **RETRY_CONFIG,
)
def publish_scheduled_post(
    self,
    account_id: int,
    content: str,
    media_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Publish a scheduled post to a social media account.

    Args:
        account_id: The social account to post to.
        content: Post content/text.
        media_urls: Optional list of media URLs to attach.

    Returns:
        Dict with publish results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, SocialPlatform
        from app.social.service import CredentialManager
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(SocialAccount).where(SocialAccount.id == account_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                raise ValueError(f"Social account {account_id} not found")

            # Decrypt the access token
            cred_mgr = CredentialManager()
            access_token = cred_mgr.decrypt_access_token(account.access_token)

            if account.platform == SocialPlatform.FACEBOOK:
                from app.social.service import MetaClient
                client = MetaClient(
                    access_token=access_token,
                    page_id=account.account_id,
                )
                result = await client.create_page_post(
                    message=content,
                    link=media_urls[0] if media_urls else None,
                )
                await client.close()
                return {
                    "account_id": account_id,
                    "platform": "facebook",
                    "post_id": result.get("id"),
                    "status": "published",
                }

            elif account.platform == SocialPlatform.INSTAGRAM:
                from app.social.service import InstagramClient
                client = InstagramClient(
                    access_token=access_token,
                    instagram_account_id=account.account_id,
                )
                # Instagram requires media container creation first
                result = await client.create_container(
                    image_url=media_urls[0] if media_urls else "",
                    caption=content,
                )
                creation_id = result.get("id")
                # Then publish the container
                if creation_id:
                    publish_result = await client.publish_container(creation_id)
                    await client.close()
                    return {
                        "account_id": account_id,
                        "platform": "instagram",
                        "post_id": publish_result.get("id"),
                        "status": "published",
                    }
                await client.close()
                return {
                    "account_id": account_id,
                    "platform": "instagram",
                    "container_id": creation_id,
                    "status": "container_created",
                }

            await client.close() if 'client' in dir() else None
            return {
                "account_id": account_id,
                "platform": account.platform.value,
                "status": "unsupported_platform",
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "publish_scheduled_post",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("publish_scheduled_post hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("publish_scheduled_post failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "publish_scheduled_post exhausted all 5 retries. Task moved to dead letter."
            )
            raise



# ---------------------------------------------------------------------------
# Task: process_publishing_queue
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.process_publishing_queue",
    queue="social",
    **RETRY_CONFIG,
)
def process_publishing_queue(
    self,
    company_id: int,
) -> Dict[str, Any]:
    """Process the publishing queue for a company.

    Publishes pending posts sequentially with rate limiting.

    Args:
        company_id: Company ID to process queue for.

    Returns:
        Dict with processing results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.social.service import PublishingQueueService

        async with get_db_context() as db:
            service = PublishingQueueService(db)
            result = await service.process_queue(company_id)
            return result

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("process_publishing_queue hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("process_publishing_queue failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "process_publishing_queue exhausted all 5 retries."
            )
            raise


# ---------------------------------------------------------------------------
# Task: refresh_all_tokens
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.refresh_all_tokens",
    queue="social",
    **RETRY_CONFIG,
)
def refresh_all_tokens(
    self,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Refresh access tokens for all connected accounts.

    Proactively refreshes tokens before they expire. Skips tokens
    that are still valid for more than 1 hour.

    Args:
        company_id: Optional company filter. If None, refreshes all accounts.

    Returns:
        Dict with refresh results.
    """
    import asyncio
    from datetime import datetime, timedelta

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialAccount, AccountStatus
        from app.social.service import SocialAccountService
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            query = (
                select(SocialAccount)
                .where(SocialAccount.status == AccountStatus.ACTIVE)
                .where(SocialAccount.refresh_token.isnot(None))
            )
            if company_id:
                query = query.where(SocialAccount.company_id == company_id)

            result = await db.execute(query)
            accounts = list(result.scalars().all())

            for account in accounts:
                if not account:
                    continue

                # Skip if token not near expiry
                if account.token_expires_at:
                    if account.token_expires_at > datetime.utcnow() + timedelta(hours=1):
                        results.append({
                            "account_id": account.id,
                            "platform": account.platform.value,
                            "status": "skipped",
                            "reason": "Token still valid",
                        })
                        continue

                try:
                    service = SocialAccountService(db)
                    refresh_result = await service.refresh_account_token(
                        account.id, account.company_id, force=False
                    )
                    results.append({
                        "account_id": account.id,
                        "platform": account.platform.value,
                        "status": "refreshed" if refresh_result.get("success") else "failed",
                        "message": refresh_result.get("message", ""),
                    })
                except Exception as exc:
                    logger.error(
                        "Token refresh failed for account %d: %s",
                        account.id,
                        exc,
                    )
                    results.append({
                        "account_id": account.id,
                        "platform": account.platform.value,
                        "status": "failed",
                        "error": str(exc),
                    })

        return {
            "task": "refresh_all_tokens",
            "timestamp": datetime.utcnow().isoformat(),
            "total_accounts": len(accounts),
            "refreshed": sum(1 for r in results if r.get("status") == "refreshed"),
            "failed": sum(1 for r in results if r.get("status") == "failed"),
            "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("refresh_all_tokens hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("refresh_all_tokens failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "refresh_all_tokens exhausted all 5 retries."
            )
            raise


# ---------------------------------------------------------------------------
# Task: auto_publish_scheduled_posts
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.social.tasks.auto_publish_scheduled_posts",
    queue="social",
    **RETRY_CONFIG,
)
def auto_publish_scheduled_posts(
    self,
    company_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Auto-publish posts that have reached their scheduled time.

    Scans for SCHEDULED posts where scheduled_at <= now and publishes them.

    Args:
        company_id: Optional company filter.

    Returns:
        Dict with publish results.
    """
    import asyncio
    from datetime import datetime

    async def _run():
        from app.database import get_db_context
        from app.social.models import SocialPost, PostStatus
        from app.social.service import PostService
        from sqlalchemy import select

        results = []

        async with get_db_context() as db:
            query = (
                select(SocialPost)
                .where(SocialPost.status == PostStatus.SCHEDULED)
                .where(SocialPost.scheduled_at <= datetime.utcnow())
            )
            if company_id:
                query = query.where(SocialPost.company_id == company_id)

            result = await db.execute(query)
            posts = list(result.scalars().all())

            for post in posts:
                try:
                    service = PostService(db)
                    publish_result = await service.publish_now(
                        post.id, post.company_id
                    )
                    results.append({
                        "post_id": post.id,
                        "platform": post.platform,
                        "status": "published" if publish_result.get("success") else "failed",
                        "external_post_id": publish_result.get("external_post_id"),
                        "message": publish_result.get("message", ""),
                    })
                except Exception as exc:
                    logger.error(
                        "Auto-publish failed for post %d: %s",
                        post.id,
                        exc,
                    )
                    results.append({
                        "post_id": post.id,
                        "platform": post.platform,
                        "status": "failed",
                        "error": str(exc),
                    })

        return {
            "task": "auto_publish_scheduled_posts",
            "timestamp": datetime.utcnow().isoformat(),
            "total_posts": len(posts),
            "published": sum(1 for r in results if r.get("status") == "published"),
            "failed": sum(1 for r in results if r.get("status") == "failed"),
            "details": results,
        }

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except SoftTimeLimitExceeded:
        logger.error("auto_publish_scheduled_posts hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("auto_publish_scheduled_posts failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "auto_publish_scheduled_posts exhausted all 5 retries."
            )
            raise
