"""Celery tasks for Creative Studio & Media Pipeline.

Provides background tasks for media processing:
- generate_thumbnail: Generate thumbnail from image/video
- optimize_image: Optimize/compress images
- generate_image_variants: Generate responsive image variants
- process_video: Extract video frames and generate thumbnails
- cleanup_orphaned_media: Remove unreferenced media files

All tasks use exponential backoff retry (max 5) and are routed
to the 'media' queue by default.
"""

import logging
import os
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional

from celery import chain, shared_task
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
# Task: generate_thumbnail
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.media.tasks.generate_thumbnail",
    queue="media",
    **RETRY_CONFIG,
)
def generate_thumbnail(
    self,
    media_id: str,
    size: str = "thumbnail",
    force_regenerate: bool = False,
) -> Dict[str, Any]:
    """Generate a thumbnail for a media asset.

    Args:
        media_id: The media asset UUID.
        size: Thumbnail size (thumbnail, small, medium, large).
        force_regenerate: If True, regenerate even if thumbnail exists.

    Returns:
        Dict with generation results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.media.models import MediaAsset, MediaVariant, MediaStatus, VariantType
        from app.media.service import StorageService, ThumbnailService
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(MediaAsset).where(MediaAsset.id == media_id)
            )
            media = result.scalar_one_or_none()

            if not media:
                raise ValueError(f"Media asset {media_id} not found")

            if media.status not in (MediaStatus.PROCESSING, MediaStatus.READY):
                raise ValueError(f"Media asset {media_id} is not processable (status: {media.status})")

            # Read source file
            storage = StorageService()
            source_data = await storage._read_local(media.file_path)
            if source_data is None:
                raise FileNotFoundError(f"Source file not found: {media.file_path}")

            # Generate variants
            variants = []

            if media.category == "image":
                variants = await ThumbnailService.generate_image_variants(
                    db, media, source_data
                )
            elif media.category == "video":
                variant = await ThumbnailService.generate_video_thumbnail(
                    db, media, source_data
                )
                variants = [variant] if variant else []

            # Update media status
            media.status = MediaStatus.READY
            await db.commit()

            return {
                "media_id": media_id,
                "category": media.category,
                "variants_generated": len(variants),
                "variant_types": [v.variant_type.value for v in variants if v],
                "thumbnail_path": media.thumbnail_path,
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "generate_thumbnail",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("generate_thumbnail hit soft time limit for media %s", media_id)
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("generate_thumbnail failed for media %s: %s", media_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "generate_thumbnail exhausted all 5 retries for media %s. Task moved to dead letter.",
                media_id,
            )
            raise


# ---------------------------------------------------------------------------
# Task: optimize_image
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.media.tasks.optimize_image",
    queue="media",
    **RETRY_CONFIG,
)
def optimize_image(
    self,
    media_id: str,
    target_quality: int = 80,
    target_format: str = "webp",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> Dict[str, Any]:
    """Optimize an image: compress and optionally resize.

    Args:
        media_id: The media asset UUID.
        target_quality: JPEG/WebP quality (1-100).
        target_format: Output format (webp, jpeg, png).
        max_width: Optional max width.
        max_height: Optional max height.

    Returns:
        Dict with optimization results.
    """
    import asyncio

    async def _run():
        from PIL import Image, ImageOps

        from app.database import get_db_context
        from app.media.models import MediaAsset, MediaStatus
        from app.media.service import StorageService
        from app.media.constants import IMAGE_QUALITY_SETTINGS
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(MediaAsset).where(MediaAsset.id == media_id)
            )
            media = result.scalar_one_or_none()

            if not media:
                raise ValueError(f"Media asset {media_id} not found")

            if media.category != "image":
                raise ValueError(f"Media asset {media_id} is not an image")

            # Read source
            storage = StorageService()
            source_data = await storage._read_local(media.file_path)
            if source_data is None:
                raise FileNotFoundError(f"Source file not found: {media.file_path}")

            # Process image
            original_size = len(source_data)
            output = BytesIO()

            with Image.open(BytesIO(source_data)) as img:
                img = ImageOps.exif_transpose(img)

                # Resize if needed
                if max_width or max_height:
                    mw = max_width or img.width
                    mh = max_height or img.height
                    img.thumbnail((mw, mh), Image.Resampling.LANCZOS)

                # Save in target format
                fmt = target_format.upper()
                if fmt == "WEBP":
                    img.save(
                        output,
                        format="WEBP",
                        quality=target_quality,
                        method=6,
                    )
                elif fmt == "JPEG":
                    img.convert("RGB").save(
                        output,
                        format="JPEG",
                        quality=target_quality,
                        optimize=True,
                    )
                elif fmt == "PNG":
                    img.save(output, format="PNG", optimize=True)
                else:
                    img.save(output, format="WEBP", quality=target_quality)

            optimized_data = output.getvalue()
            optimized_size = len(optimized_data)
            compression_ratio = (
                (original_size - optimized_size) / original_size * 100
                if original_size > 0
                else 0
            )

            # Store optimized version
            base_name = os.path.splitext(media.filename)[0]
            ext = ".webp" if target_format == "webp" else f".{target_format}"
            optimized_filename = f"{base_name}_optimized{ext}"

            from app.media.constants import VARIANT_PATH_TEMPLATE
            from datetime import timezone

            now = datetime.now(timezone.utc)
            variant_path = VARIANT_PATH_TEMPLATE.format(
                company_id=str(media.company_id),
                year=str(now.year),
                month=f"{now.month:02d}",
                variant="optimized",
                filename=optimized_filename,
            )

            await storage._store_local(optimized_data, variant_path)

            return {
                "media_id": media_id,
                "original_size": original_size,
                "optimized_size": optimized_size,
                "compression_ratio": round(compression_ratio, 2),
                "format": target_format,
                "quality": target_quality,
                "dimensions": f"{img.width}x{img.height}",
                "output_path": variant_path,
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "optimize_image",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("optimize_image hit soft time limit for media %s", media_id)
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("optimize_image failed for media %s: %s", media_id, exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "optimize_image exhausted all 5 retries for media %s. Task moved to dead letter.",
                media_id,
            )
            raise


# ---------------------------------------------------------------------------
# Task: process_media_upload
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.media.tasks.process_media_upload",
    queue="media",
    **RETRY_CONFIG,
)
def process_media_upload(
    self,
    media_id: str,
    generate_thumbnails: bool = True,
    optimize: bool = True,
) -> Dict[str, Any]:
    """Process a newly uploaded media asset: thumbnails + optimization.

    Chains generate_thumbnail and optimize_image for a complete pipeline.

    Args:
        media_id: The media asset UUID.
        generate_thumbnails: Whether to generate thumbnails.
        optimize: Whether to optimize the image.

    Returns:
        Dict with processing results.
    """
    results = {
        "media_id": media_id,
        "timestamp": datetime.utcnow().isoformat(),
        "thumbnails": None,
        "optimization": None,
    }

    try:
        if generate_thumbnails:
            results["thumbnails"] = generate_thumbnail.delay(media_id).get(timeout=300)
    except Exception as exc:
        logger.error("Thumbnail generation failed for media %s: %s", media_id, exc)
        results["thumbnails_error"] = str(exc)

    try:
        if optimize:
            results["optimization"] = optimize_image.delay(media_id).get(timeout=300)
    except Exception as exc:
        logger.error("Optimization failed for media %s: %s", media_id, exc)
        results["optimization_error"] = str(exc)

    return results


# ---------------------------------------------------------------------------
# Task: cleanup_orphaned_media
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="app.media.tasks.cleanup_orphaned_media",
    queue="media",
    **RETRY_CONFIG,
)
def cleanup_orphaned_media(
    self,
    older_than_hours: int = 24,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Clean up orphaned/unreferenced media files.

    Scans for media assets that are no longer referenced and removes them.

    Args:
        older_than_hours: Only remove files older than this many hours.
        dry_run: If True, only report what would be deleted.

    Returns:
        Dict with cleanup results.
    """
    import asyncio

    async def _run():
        from app.database import get_db_context
        from app.media.models import MediaAsset, MediaStatus
        from app.media.service import StorageService
        from sqlalchemy import select, and_
        from datetime import timezone

        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)

        async with get_db_context() as db:
            # Find orphaned media: status=PROCESSING and older than cutoff
            result = await db.execute(
                select(MediaAsset).where(
                    and_(
                        MediaAsset.status == MediaStatus.PROCESSING,
                        MediaAsset.created_at < cutoff,
                    )
                )
            )
            orphaned = list(result.scalars().all())

            deleted = 0
            failed = 0
            details = []

            for media in orphaned:
                try:
                    if not dry_run:
                        # Delete file from storage
                        storage = StorageService()
                        await storage.delete_media_file(media)

                        # Delete from database
                        await db.delete(media)

                    deleted += 1
                    details.append(
                        {
                            "media_id": media.id,
                            "filename": media.filename,
                            "action": "deleted" if not dry_run else "would_delete",
                        }
                    )
                except Exception as exc:
                    failed += 1
                    details.append(
                        {
                            "media_id": media.id,
                            "filename": media.filename,
                            "action": "failed",
                            "error": str(exc),
                        }
                    )

            if not dry_run:
                await db.commit()

            return {
                "scanned": len(orphaned),
                "deleted": deleted,
                "failed": failed,
                "dry_run": dry_run,
                "cutoff": cutoff.isoformat(),
                "details": details,
            }

    try:
        result = asyncio.get_event_loop().run_until_complete(_run())
        return {
            "task": "cleanup_orphaned_media",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except SoftTimeLimitExceeded:
        logger.error("cleanup_orphaned_media hit soft time limit")
        raise self.retry(exc=Exception("Soft time limit exceeded"), countdown=30)
    except Exception as exc:
        logger.error("cleanup_orphaned_media failed: %s", exc, exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "cleanup_orphaned_media exhausted all 5 retries. Task moved to dead letter."
            )
            raise
