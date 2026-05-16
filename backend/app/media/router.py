"""
FastAPI router for the Creative Studio & Media Pipeline module.

Provides REST API endpoints for:
- Media upload (multipart form, presigned URL, direct upload)
- Media CRUD (list, get, update, delete, bulk operations)
- Thumbnails and variants (responsive sizes, signed URLs)
- AI analysis (OpenAI Vision: caption, hashtag, score, objects,
  brand alignment, Instagram optimization, creative audit)
- Brand identity management (CRUD per branch)
- Creative audit (per-asset and portfolio-wide)
- Social platform optimization (Instagram, Facebook, TikTok)
- Collections and tagging
- Statistics and analytics
- Async job status
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, get_current_user_optional
from app.auth.permissions import Permission, require_permissions
from app.auth.roles import UserRole
from app.auth.schemas import TokenData
from app.database import get_db_session
from app.dependencies import get_company_id, get_optional_company_id
from app.exceptions import NotFoundError, ValidationError
from app.media.constants import (
    AnalysisType,
    DEFAULT_PAGE_SIZE,
    JOB_TIMEOUT_SECONDS,
    JobType,
    MAX_PAGE_SIZE,
    MediaStatus,
    StorageProvider,
    VariantType,
)
from app.media.models import (
    AIImageAnalysis,
    BranchBrandIdentity,
    CreativeAudit,
    MediaAnalytics,
    MediaAsset,
    MediaCollection,
    MediaCollectionItem,
    MediaTag,
    MediaTagMapping,
    MediaVariant,
)
from app.media.schemas import (
    AIAnalysisRequest,
    AIAnalysisResult,
    AIAnalysisTypesResponse,
    AIScoreResult,
    BrandIdentityCreate,
    BrandIdentityResponse,
    BrandIdentityUpdate,
    BulkDeleteRequest,
    BulkOperationResponse,
    BulkTagRequest,
    CreativeAuditRequest,
    CreativeAuditResult,
    CreativeAuditSummary,
    JobStatusResponse,
    MediaAssetFilter,
    MediaAssetListItem,
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaAssetUpdate,
    MediaCollectionCreate,
    MediaCollectionItemAdd,
    MediaCollectionListResponse,
    MediaCollectionResponse,
    MediaCollectionUpdate,
    MediaStatsResponse,
    MediaTagCreate,
    MediaTagResponse,
    MediaTagUpdate,
    MultiPlatformOptimizationResponse,
    PaginatedResponse,
    PaginationParams,
    PlatformOptimizationResponse,
    PresignedUploadUrlResponse,
    SignedUrlResponse,
    SortParams,
    TagAddRequest,
    ThumbnailSizeParam,
    UploadCompleteRequest,
    UploadInitiateRequest,
    UploadResponse,
)
from app.config import settings
from app.media.service import (
    AIImageAnalysisService,
    CreativeStudioService,
    ImageOptimizationService,
    MediaOrganizerService,
    MediaOptimizationQueueService,
    SignedURLService,
    StorageService,
    UploadService,
    VirusScanningService,
)

router = APIRouter(prefix="/media", tags=["Media & Creative Studio"])


# ===========================================================================
# Helpers
# ===========================================================================


def _paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    """Build a paginated response dict."""
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


def _media_list_item(media: MediaAsset, base_url: str = "") -> Dict[str, Any]:
    """Build a MediaAssetListItem dict from a model."""
    thumbnail_url = None
    if media.thumbnail_path:
        thumbnail_url = (
            f"{base_url}/media/{media.id}/thumbnail"
            if not media.thumbnail_path.startswith("http")
            else media.thumbnail_path
        )
    tag_names = []
    for mapping in media.tag_mappings or []:
        if mapping.tag:
            tag_names.append(mapping.tag.name)

    return {
        "id": media.id,
        "filename": media.filename,
        "original_filename": media.original_filename,
        "mime_type": media.mime_type,
        "category": media.category,
        "file_size": media.file_size,
        "width": media.width,
        "height": media.height,
        "duration": media.duration,
        "status": media.status.value if hasattr(media.status, "value") else media.status,
        "thumbnail_url": thumbnail_url,
        "created_at": media.created_at.isoformat() if media.created_at else None,
        "tag_names": tag_names,
        "virus_scan_status": media.virus_scan_status,
    }


# ===========================================================================
# Media Upload
# ===========================================================================


@router.post("/upload", response_model=UploadResponse)
async def upload_media_file(
    request: Request,
    file: UploadFile = File(...),
    branch_id: Optional[int] = Query(None, description="Optional branch ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Upload a media file via multipart form data.

    Validates MIME type (magic bytes + extension), file size limits,
    and virus scanning. Generates thumbnails and queues optimization jobs.

    Args:
        file: The uploaded file.
        branch_id: Optional branch ID for sub-tenant isolation.

    Returns:
        UploadResponse with media asset details and access URL.

    Raises:
        ValidationError: If file type not allowed or size exceeds limit.
        HTTPException: If processing fails.
    """
    try:
        media = await UploadService.process_upload(
            db=db,
            user_id=current_user.user_id,
            company_id=company_id,
            branch_id=branch_id,
            upload_file=file,
        )

        base_url = str(request.base_url).rstrip("/")
        return {
            "media_id": media.id,
            "filename": media.filename,
            "original_filename": media.original_filename,
            "mime_type": media.mime_type,
            "file_size": media.file_size,
            "status": media.status.value,
            "url": f"{base_url}/media/{media.id}",
            "thumbnail_url": (
                f"{base_url}/media/{media.id}/thumbnail"
                if media.thumbnail_path
                else None
            ),
            "created_at": media.created_at.isoformat(),
        }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(exc)}",
        ) from exc


@router.post("/upload/presigned", response_model=PresignedUploadUrlResponse)
async def create_presigned_upload_url(
    request: Request,
    data: UploadInitiateRequest,
    branch_id: Optional[int] = Query(None, description="Optional branch ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Create a presigned URL for direct browser-to-S3 upload.

    Steps:
    1. Validate the upload request (MIME type, file size).
    2. Create a MediaAsset record in 'uploading' status.
    3. Generate a presigned S3 PUT URL.

    The client uploads directly to S3 using the returned URL, then
    calls POST /media/upload/complete to confirm.

    Args:
        data: Upload initiation request with filename, MIME type, size.
        branch_id: Optional branch ID.

    Returns:
        PresignedUploadUrlResponse with upload URL, media ID, and expiry.

    Raises:
        ValidationError: If file type or size is invalid.
    """
    try:
        media = await UploadService.create_upload_record(
            db=db,
            user_id=current_user.user_id,
            company_id=company_id,
            branch_id=branch_id,
            data=data,
        )

        presigned = await StorageService.generate_presigned_upload_url(media)
        return {
            "upload_url": presigned["upload_url"],
            "media_id": presigned["media_id"],
            "storage_key": presigned["storage_key"],
            "expires_in": int(presigned["expires_in"]),
            "fields": None,
        }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Presigned URL generation failed: {str(exc)}",
        ) from exc


@router.post("/upload/complete", response_model=UploadResponse)
async def complete_direct_upload(
    request: Request,
    data: UploadCompleteRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Confirm a completed direct upload and trigger post-processing.

    After the client uploads directly to S3, call this endpoint to:
    1. Verify the file exists in storage.
    2. Update MediaAsset status from 'uploading' to 'processing'.
    3. Queue thumbnail generation and optimization jobs.

    Args:
        data: Upload completion data with media ID and storage key.

    Returns:
        UploadResponse with updated media asset details.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == data.media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {data.media_id} not found",
        )

    if media.storage_key != data.storage_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage key mismatch",
        )

    # Update status and trigger processing
    media.status = MediaStatus.PROCESSING
    if data.checksum:
        media.checksum = data.checksum
    await db.commit()

    from app.media.constants import JobType
    queue = MediaOptimizationQueueService()
    await queue.enqueue_job(
        job_type=JobType.THUMBNAIL,
        media_id=media.id,
        company_id=company_id,
    )

    base_url = str(request.base_url).rstrip("/")
    return {
        "media_id": media.id,
        "filename": media.filename,
        "original_filename": media.original_filename,
        "mime_type": media.mime_type,
        "file_size": media.file_size,
        "status": media.status.value,
        "url": f"{base_url}/media/{media.id}",
        "thumbnail_url": None,
        "created_at": media.created_at.isoformat(),
    }


# ===========================================================================
# Media CRUD
# ===========================================================================


@router.get("", response_model=MediaAssetListResponse)
async def list_media_assets(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category: image/video/document"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[List[int]] = Query(None, description="Filter by tag IDs"),
    search: Optional[str] = Query(None, description="Search in filename"),
    date_from: Optional[datetime] = Query(None, description="Uploaded on or after"),
    date_to: Optional[datetime] = Query(None, description="Uploaded on or before"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort direction: asc/desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    List media assets with filtering, search, and pagination.

    Args:
        category: Filter by file category (image/video/document).
        status: Filter by processing status (uploading/processing/ready/error/deleted).
        tags: Filter by tag IDs (assets must have ALL specified tags).
        search: Full-text search in original and stored filenames.
        date_from/date_to: Date range filter on upload timestamp.
        sort_by: Sort field (created_at, file_size, filename).
        sort_order: Sort direction (asc/desc).
        page: Page number (1-based).
        page_size: Items per page (max 100).
        branch_id: Filter by branch ID.

    Returns:
        Paginated list of MediaAssetListItem with thumbnail URLs.
    """
    assets, total = await MediaOrganizerService.search_media(
        db=db,
        company_id=company_id,
        branch_id=branch_id,
        category=category,
        status=status,
        tags=tags,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

    base_url = str(request.base_url).rstrip("/")
    items = [_media_list_item(a, base_url) for a in assets]
    return _paginated_response(items, total, page, page_size)


@router.get("/{media_id}", response_model=Dict[str, Any])
async def get_media_asset(
    request: Request,
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get detailed information about a media asset.

    Args:
        media_id: Media asset UUID.

    Returns:
        MediaAssetResponse with all details, variants, tags, and URLs.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    base_url = str(request.base_url).rstrip("/")

    # Get analytics
    analytics = media.analytics
    views = analytics.views if analytics else 0
    downloads = analytics.downloads if analytics else 0

    # Get tags
    tag_list = []
    for mapping in media.tag_mappings or []:
        if mapping.tag:
            tag_list.append({
                "id": mapping.tag.id,
                "company_id": mapping.tag.company_id,
                "name": mapping.tag.name,
                "color": mapping.tag.color,
                "created_at": mapping.tag.created_at.isoformat() if mapping.tag.created_at else None,
            })

    # Get variants
    variant_list = []
    for v in media.variants or []:
        variant_list.append({
            "id": v.id,
            "media_id": v.media_id,
            "variant_type": v.variant_type.value if hasattr(v.variant_type, "value") else str(v.variant_type),
            "file_path": v.file_path,
            "width": v.width,
            "height": v.height,
            "file_size": v.file_size,
            "quality": v.quality,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "url": f"{base_url}/media/{media.id}/variant/{v.variant_type.value}",
        })

    return {
        "id": media.id,
        "company_id": media.company_id,
        "branch_id": media.branch_id,
        "filename": media.filename,
        "original_filename": media.original_filename,
        "file_path": media.file_path,
        "file_size": media.file_size,
        "mime_type": media.mime_type,
        "category": media.category,
        "width": media.width,
        "height": media.height,
        "duration": media.duration,
        "thumbnail_path": media.thumbnail_path,
        "storage_provider": media.storage_provider.value if hasattr(media.storage_provider, "value") else str(media.storage_provider),
        "storage_key": media.storage_key,
        "checksum": media.checksum,
        "status": media.status.value if hasattr(media.status, "value") else str(media.status),
        "metadata": media.metadata_,
        "exif_data": media.exif_data,
        "virus_scan_status": media.virus_scan_status,
        "created_by": media.created_by,
        "created_at": media.created_at.isoformat() if media.created_at else None,
        "updated_at": media.updated_at.isoformat() if media.updated_at else None,
        "tags": tag_list,
        "variants": variant_list,
        "views": views,
        "downloads": downloads,
        "url": f"{base_url}/media/{media.id}/download",
    }


@router.patch("/{media_id}", response_model=Dict[str, Any])
async def update_media_asset(
    request: Request,
    media_id: str = Path(..., description="Media asset UUID"),
    data: MediaAssetUpdate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Update a media asset's metadata.

    Args:
        media_id: Media asset UUID.
        data: Update fields (original_filename, metadata).

    Returns:
        Updated media asset details.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    if data.original_filename is not None:
        media.original_filename = data.original_filename
    if data.metadata is not None:
        media.metadata_ = data.metadata
    media.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(media)

    return {"id": media.id, "message": "Media asset updated", "updated_fields": list(data.model_dump(exclude_none=True).keys())}


@router.delete("/{media_id}")
async def delete_media_asset(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Delete a media asset and its stored files.

    Permanently removes the asset, all variants, and the underlying file
    from storage. This action cannot be undone.

    Args:
        media_id: Media asset UUID.

    Returns:
        Confirmation message.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    # Delete stored files and variants
    storage = StorageService()
    await StorageService.delete_media_file(media)
    for variant in media.variants or []:
        await storage._delete_local(variant.file_path)

    await db.delete(media)
    await db.commit()

    return {"message": f"Media {media_id} deleted successfully"}


@router.post("/bulk/delete", response_model=BulkOperationResponse)
async def bulk_delete_media(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Delete multiple media assets in bulk.

    Args:
        request: BulkDeleteRequest with list of media IDs.

    Returns:
        BulkOperationResponse with success/failure counts.
    """
    success_count, errors = await MediaOrganizerService.bulk_delete(
        db=db,
        media_ids=request.media_ids,
        company_id=company_id,
    )
    return {
        "success_count": success_count,
        "failed_count": len(errors),
        "errors": errors,
        "processed_ids": [mid for mid in request.media_ids if mid not in {e["id"] for e in errors}],
    }


@router.post("/bulk/tag", response_model=BulkOperationResponse)
async def bulk_tag_media(
    request: BulkTagRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Apply tags to multiple media assets in bulk.

    Args:
        request: BulkTagRequest with media IDs and tag IDs.

    Returns:
        BulkOperationResponse with success/failure counts.
    """
    success_count, errors = await MediaOrganizerService.bulk_tag(
        db=db,
        media_ids=request.media_ids,
        tag_ids=request.tag_ids,
        company_id=company_id,
    )
    return {
        "success_count": success_count,
        "failed_count": len(errors),
        "errors": errors,
        "processed_ids": [],
    }


# ===========================================================================
# Media Access & Download
# ===========================================================================


@router.get("/{media_id}/download")
async def download_media_file(
    media_id: str = Path(..., description="Media asset UUID"),
    variant: Optional[str] = Query(None, description="Optional variant type"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Download a media file via signed URL redirect.

    Generates a time-limited signed URL and redirects to it.
    For local storage, serves the file directly.

    Args:
        media_id: Media asset UUID.
        variant: Optional variant type (thumbnail/small/medium/large/webp).

    Returns:
        RedirectResponse to the signed download URL.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    # For local storage, redirect to the static file endpoint
    if media.storage_provider == StorageProvider.LOCAL:
        from fastapi.responses import FileResponse
        storage = StorageService()
        full_path = f"{storage._get_base_path()}/{media.file_path}"
        return FileResponse(
            path=full_path,
            filename=media.original_filename,
            media_type=media.mime_type,
        )

    # For S3/R2, generate a presigned download URL
    url = await SignedURLService.generate_presigned_download_url(media)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)


@router.get("/{media_id}/signed-url", response_model=SignedUrlResponse)
async def get_signed_url(
    media_id: str = Path(..., description="Media asset UUID"),
    variant: Optional[str] = Query(None, description="Optional variant type"),
    expiry: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get a time-limited signed URL for a media asset.

    Signed URLs use HMAC-based tokens that expire after a configurable
    duration. These URLs are tamper-proof and suitable for embedding in
    emails or sharing externally.

    Args:
        media_id: Media asset UUID.
        variant: Optional variant type.
        expiry: URL validity in seconds (60-86400).

    Returns:
        SignedUrlResponse with the signed URL and expiry.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    url = SignedURLService.generate_signed_url(
        media_id=media.id,
        filename=media.original_filename,
        variant=variant,
        expiry_seconds=expiry,
    )
    return {"url": url, "expires_in": expiry, "filename": media.original_filename}


# ===========================================================================
# Thumbnails & Variants
# ===========================================================================


@router.get("/{media_id}/thumbnail")
async def get_thumbnail(
    media_id: str = Path(..., description="Media asset UUID"),
    size: str = Query("t", pattern="^(s|m|l|t)$", description="Thumbnail size: s=small, m=medium, l=large, t=thumbnail"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get a media thumbnail in the requested size.

    Serves thumbnails directly from local storage or redirects to
    S3/R2 for remote storage.

    Args:
        media_id: Media asset UUID.
        size: Thumbnail size code (s/m/l/t).

    Returns:
        FileResponse with the thumbnail image or RedirectResponse.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    # Find the requested variant
    size_map = {"t": "THUMBNAIL", "s": "SMALL", "m": "MEDIUM", "l": "LARGE"}
    target_type = size_map.get(size, "THUMBNAIL")

    variant = None
    for v in media.variants or []:
        if v.variant_type.value == target_type:
            variant = v
            break

    # Fallback to thumbnail_path if no variant found
    if not variant and media.thumbnail_path:
        variant_path = media.thumbnail_path
    elif variant:
        variant_path = variant.file_path
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thumbnail not available for media {media_id}",
        )

    if media.storage_provider == StorageProvider.LOCAL:
        from fastapi.responses import FileResponse
        storage = StorageService()
        full_path = f"{storage._get_base_path()}/{variant_path}"
        return FileResponse(path=full_path, media_type="image/jpeg")

    # Redirect to CDN or S3/R2 with hybrid signed URL fallback
    from fastapi.responses import RedirectResponse

    # Build URL resolution chain: CDN > S3_PUBLIC_URL > R2_PUBLIC_URL > signed URL
    url = None
    if hasattr(settings, "CDN_URL") and settings.CDN_URL:
        url = f"{settings.CDN_URL.rstrip('/')}/{variant_path}"
    elif media.storage_provider == StorageProvider.S3:
        public_url = getattr(settings, "S3_PUBLIC_URL", "")
        if public_url:
            url = f"{public_url.rstrip('/')}/{variant_path}"
    elif media.storage_provider == StorageProvider.R2:
        public_url = getattr(settings, "R2_PUBLIC_URL", "")
        if public_url:
            url = f"{public_url.rstrip('/')}/{variant_path}"

    # Fall back to signed URL if no CDN/public URL is configured
    if not url:
        url = SignedURLService.generate_signed_url(
            media_id=media.id,
            filename=media.original_filename,
            variant=target_type.lower(),
            expiry_seconds=3600,
        )

    return RedirectResponse(url=url)


@router.get("/{media_id}/variant/{variant_type}")
async def get_variant(
    media_id: str = Path(..., description="Media asset UUID"),
    variant_type: str = Path(..., description="Variant type: thumbnail/small/medium/large/webp/optimized"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get a specific media variant.

    Args:
        media_id: Media asset UUID.
        variant_type: Variant type (thumbnail/small/medium/large/webp/optimized).

    Returns:
        FileResponse with the variant image or RedirectResponse.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    variant = None
    for v in media.variants or []:
        if v.variant_type.value.lower() == variant_type.lower():
            variant = v
            break

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant '{variant_type}' not found for media {media_id}",
        )

    if media.storage_provider == StorageProvider.LOCAL:
        from fastapi.responses import FileResponse
        storage = StorageService()
        full_path = f"{storage._get_base_path()}/{variant.file_path}"
        mime_type = "image/webp" if variant_type == "webp" else "image/jpeg"
        return FileResponse(path=full_path, media_type=mime_type)

    from fastapi.responses import RedirectResponse

    # CDN + signed URL hybrid resolution
    url = None
    cdn = getattr(settings, "CDN_URL", "")
    if cdn:
        url = f"{cdn.rstrip('/')}/{variant.file_path}"
    elif media.storage_provider == StorageProvider.S3:
        public_url = getattr(settings, "S3_PUBLIC_URL", "")
        if public_url:
            url = f"{public_url.rstrip('/')}/{variant.file_path}"
    elif media.storage_provider == StorageProvider.R2:
        public_url = getattr(settings, "R2_PUBLIC_URL", "")
        if public_url:
            url = f"{public_url.rstrip('/')}/{variant.file_path}"

    if not url:
        url = SignedURLService.generate_signed_url(
            media_id=media.id,
            filename=media.original_filename,
            variant=variant_type.lower(),
            expiry_seconds=3600,
        )

    return RedirectResponse(url=url)


# ===========================================================================
# AI Analysis
# ===========================================================================


@router.post("/{media_id}/analyze", response_model=AIAnalysisResult)
async def analyze_media(
    media_id: str = Path(..., description="Media asset UUID"),
    request: AIAnalysisRequest = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID for brand-aware analysis"),
):
    """
    Run AI analysis on a media asset using OpenAI Vision.

    Supported analysis types:
    - **caption**: Generate engaging caption
    - **hashtag**: Suggest relevant hashtags
    - **score**: Rate image quality (composition, lighting, color, sharpness, relevance)
    - **objects**: Detect objects, text, and brands
    - **brand_alignment**: Check alignment with branch brand identity
    - **instagram_optimize**: Get Instagram-specific optimization tips
    - **creative_audit**: Full creative audit with fatigue detection

    Results are cached. Set force_refresh=true to re-run analysis.

    Args:
        media_id: Media asset UUID (must be an image).
        request: AnalysisRequest with analysis_type and options.
        branch_id: Optional branch ID for brand-aware analysis.

    Returns:
        AIAnalysisResult with structured analysis output.

    Raises:
        ValidationError: If media is not an image.
        NotFoundError: If media not found.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        analysis_type = AnalysisType(request.analysis_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid analysis type: {request.analysis_type}",
        )

    try:
        analysis = await AIImageAnalysisService.analyze_media(
            db=db,
            media=media,
            analysis_type=analysis_type,
            force_refresh=request.force_refresh,
            branch_id=branch_id,
            platform=request.platform,
            language=request.language,
            max_chars=request.max_chars,
        )
        return {
            "id": analysis.id,
            "media_id": analysis.media_id,
            "analysis_type": analysis.analysis_type.value,
            "result": analysis.result,
            "confidence": analysis.confidence,
            "model_used": analysis.model_used,
            "brand_identity_applied": analysis.brand_identity_applied,
            "created_at": analysis.created_at.isoformat(),
        }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(exc)}",
        ) from exc


@router.get("/{media_id}/analyze", response_model=AIAnalysisTypesResponse)
async def list_analysis_results(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    List all AI analysis results for a media asset.

    Returns available analysis types and which ones have been run.

    Args:
        media_id: Media asset UUID.

    Returns:
        AIAnalysisTypesResponse with analysis types and existing analyses.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    analyses = await AIImageAnalysisService.get_analysis_results(
        db, media_id, company_id
    )
    existing = [a.analysis_type.value for a in analyses]

    return {
        "analysis_types": [at.value for at in AnalysisType],
        "media_id": media_id,
        "existing_analyses": existing,
    }


@router.get("/{media_id}/analyze/{analysis_type}", response_model=AIAnalysisResult)
async def get_specific_analysis(
    media_id: str = Path(..., description="Media asset UUID"),
    analysis_type: str = Path(..., description="Analysis type"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get a specific AI analysis result for a media asset.

    Args:
        media_id: Media asset UUID.
        analysis_type: Analysis type (caption/hashtag/score/objects/etc.).

    Returns:
        AIAnalysisResult with the cached analysis output.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        atype = AnalysisType(analysis_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid analysis type: {analysis_type}",
        )

    result = await db.execute(
        select(AIImageAnalysis).where(
            AIImageAnalysis.media_id == media_id,
            AIImageAnalysis.analysis_type == atype,
            AIImageAnalysis.company_id == company_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_type}' not found for media {media_id}",
        )

    return {
        "id": analysis.id,
        "media_id": analysis.media_id,
        "analysis_type": analysis.analysis_type.value,
        "result": analysis.result,
        "confidence": analysis.confidence,
        "model_used": analysis.model_used,
        "brand_identity_applied": analysis.brand_identity_applied,
        "created_at": analysis.created_at.isoformat(),
    }


# ===========================================================================
# Full Analysis Suite
# ===========================================================================


@router.post("/{media_id}/analyze/full", response_model=Dict[str, Any])
async def run_full_analysis(
    media_id: str = Path(..., description="Media asset UUID"),
    branch_id: Optional[int] = Query(None, description="Branch ID for brand-aware analysis"),
    platform: Optional[str] = Query(None, description="Target platform"),
    language: Optional[str] = Query(None, description="Output language"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Run all standard AI analysis types on a media asset.

    Executes caption, hashtag, score, and objects analysis in sequence.
    Brand identity is applied when branch_id is provided.

    Args:
        media_id: Media asset UUID (must be an image).
        branch_id: Optional branch for brand-aware analysis.
        platform: Target platform for platform-specific results.
        language: Output language (e.g., 'tr', 'en').

    Returns:
        Dict mapping analysis type to results.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        results = await AIImageAnalysisService.run_full_analysis(
            db=db,
            media=media,
            branch_id=branch_id,
            platform=platform,
            language=language,
        )
        return {
            atype: {
                "id": a.id,
                "result": a.result,
                "confidence": a.confidence,
                "model_used": a.model_used,
                "brand_identity_applied": a.brand_identity_applied,
            }
            for atype, a in results.items()
            if a is not None
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full analysis failed: {str(exc)}",
        ) from exc


# ===========================================================================
# Instagram / Social Platform Optimization
# ===========================================================================


@router.post("/{media_id}/optimize/instagram", response_model=PlatformOptimizationResponse)
async def optimize_for_instagram(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID"),
):
    """
    Get Instagram-specific optimization recommendations for a media asset.

    Analyzes the image and provides recommendations for:
    - Recommended format (feed/story/reel/carousel)
    - Optimal aspect ratio and dimensions
    - Crop suggestions and text overlay ideas
    - Color adjustment values
    - Best posting time
    - Engagement prediction
    - Content tips and accessibility notes

    Args:
        media_id: Media asset UUID (must be an image).
        branch_id: Optional branch for brand-aware optimization.

    Returns:
        PlatformOptimizationResponse with Instagram-specific recommendations.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        analysis = await AIImageAnalysisService.analyze_media(
            db=db,
            media=media,
            analysis_type=AnalysisType.INSTAGRAM_OPTIMIZE,
            branch_id=branch_id,
            platform="instagram",
        )

        # Merge with Instagram specs
        result_data = dict(analysis.result)
        result_data["platform"] = "instagram"
        result_data["specs"] = INSTAGRAM_FORMAT_SPECS
        return result_data

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Instagram optimization failed: {str(exc)}",
        ) from exc


@router.post("/{media_id}/optimize/facebook", response_model=PlatformOptimizationResponse)
async def optimize_for_facebook(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID"),
):
    """
    Get Facebook-specific optimization recommendations.

    Args:
        media_id: Media asset UUID.
        branch_id: Optional branch ID.

    Returns:
        PlatformOptimizationResponse with Facebook-specific recommendations.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        analysis = await AIImageAnalysisService.analyze_media(
            db=db,
            media=media,
            analysis_type=AnalysisType.INSTAGRAM_OPTIMIZE,
            branch_id=branch_id,
            platform="facebook",
        )

        result_data = dict(analysis.result)
        result_data["platform"] = "facebook"
        result_data["specs"] = FACEBOOK_FORMAT_SPECS
        return result_data

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Facebook optimization failed: {str(exc)}",
        ) from exc


@router.post("/{media_id}/optimize/tiktok", response_model=PlatformOptimizationResponse)
async def optimize_for_tiktok(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID"),
):
    """
    Get TikTok-specific optimization recommendations.

    Args:
        media_id: Media asset UUID.
        branch_id: Optional branch ID.

    Returns:
        PlatformOptimizationResponse with TikTok-specific recommendations.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        analysis = await AIImageAnalysisService.analyze_media(
            db=db,
            media=media,
            analysis_type=AnalysisType.INSTAGRAM_OPTIMIZE,
            branch_id=branch_id,
            platform="tiktok",
        )

        result_data = dict(analysis.result)
        result_data["platform"] = "tiktok"
        result_data["specs"] = TIKTOK_FORMAT_SPECS
        return result_data

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TikTok optimization failed: {str(exc)}",
        ) from exc


@router.post("/{media_id}/optimize/all", response_model=MultiPlatformOptimizationResponse)
async def optimize_for_all_platforms(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID"),
):
    """
    Get optimization recommendations for all social platforms.

    Runs platform-specific optimization for Instagram, Facebook, and TikTok.

    Args:
        media_id: Media asset UUID.
        branch_id: Optional branch ID.

    Returns:
        MultiPlatformOptimizationResponse with recommendations for all platforms.
    """
    platforms = []
    errors = []

    for platform_name, endpoint_func in [
        ("instagram", optimize_for_instagram),
        ("facebook", optimize_for_facebook),
        ("tiktok", optimize_for_tiktok),
    ]:
        try:
            result_data = await endpoint_func(
                media_id=media_id,
                db=db,
                current_user=current_user,
                company_id=company_id,
                branch_id=branch_id,
            )
            platforms.append(result_data)
        except Exception as exc:
            errors.append(f"{platform_name}: {str(exc)}")

    return {
        "media_id": media_id,
        "platforms": platforms,
        "universal_tips": [
            "Always maintain consistent brand colors",
            "Use high-quality images for better engagement",
            "Test different caption styles to find what resonates",
            "Monitor engagement metrics and adjust strategy",
        ] + errors,
    }


# ===========================================================================
# Brand Identity Management
# ===========================================================================


@router.post("/brand-identities", response_model=BrandIdentityResponse)
async def create_brand_identity(
    branch_id: int = Query(..., description="Branch ID"),
    data: BrandIdentityCreate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Create a brand identity for a branch.

    Brand identities define the visual and tonal guidelines that AI-generated
    content should follow. Includes brand colors, tone of voice, target
    audience, hashtag rules, and competitor differentiation.

    Args:
        branch_id: Branch ID to associate with.
        data: BrandIdentityCreate with brand details.

    Returns:
        BrandIdentityResponse with the created identity.

    Raises:
        ValidationError: If identity already exists for branch.
    """
    try:
        identity = await CreativeStudioService.create_brand_identity(
            db=db,
            company_id=company_id,
            branch_id=branch_id,
            data=data,
        )
        return {
            "id": identity.id,
            "branch_id": identity.branch_id,
            "company_id": identity.company_id,
            "brand_name": identity.brand_name,
            "primary_color": identity.primary_color,
            "secondary_color": identity.secondary_color,
            "accent_color": identity.accent_color,
            "brand_tone": identity.brand_tone.value if hasattr(identity.brand_tone, "value") else str(identity.brand_tone),
            "target_audience": identity.target_audience,
            "industry": identity.industry,
            "language": identity.language,
            "font_style": identity.font_style,
            "visual_style": identity.visual_style,
            "hashtags_always_include": identity.hashtags_always_include,
            "hashtags_never_include": identity.hashtags_never_include,
            "competitors_to_differentiate": identity.competitors_to_differentiate,
            "is_active": identity.is_active,
            "created_at": identity.created_at.isoformat(),
            "updated_at": identity.updated_at.isoformat(),
        }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail
        ) from exc


@router.get("/brand-identities", response_model=Dict[str, Any])
async def list_brand_identities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    List all brand identities for the current company.

    Args:
        page: Page number (1-based).
        page_size: Items per page (max 100).

    Returns:
        Paginated list of BrandIdentityResponse.
    """
    identities, total = await CreativeStudioService.list_brand_identities(
        db=db,
        company_id=company_id,
        page=page,
        page_size=page_size,
    )

    items = []
    for i in identities:
        items.append({
            "id": i.id,
            "branch_id": i.branch_id,
            "company_id": i.company_id,
            "brand_name": i.brand_name,
            "primary_color": i.primary_color,
            "secondary_color": i.secondary_color,
            "accent_color": i.accent_color,
            "brand_tone": i.brand_tone.value if hasattr(i.brand_tone, "value") else str(i.brand_tone),
            "target_audience": i.target_audience,
            "industry": i.industry,
            "language": i.language,
            "font_style": i.font_style,
            "visual_style": i.visual_style,
            "hashtags_always_include": i.hashtags_always_include,
            "hashtags_never_include": i.hashtags_never_include,
            "competitors_to_differentiate": i.competitors_to_differentiate,
            "is_active": i.is_active,
            "created_at": i.created_at.isoformat(),
            "updated_at": i.updated_at.isoformat(),
        })

    return _paginated_response(items, total, page, page_size)


@router.get("/brand-identities/{branch_id}", response_model=BrandIdentityResponse)
async def get_brand_identity(
    branch_id: int = Path(..., description="Branch ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get the brand identity for a specific branch.

    Args:
        branch_id: Branch ID.

    Returns:
        BrandIdentityResponse or 404 if not found.
    """
    identity = await CreativeStudioService.get_brand_identity(
        db=db, branch_id=branch_id, company_id=company_id
    )
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brand identity for branch {branch_id} not found",
        )
    return {
        "id": identity.id,
        "branch_id": identity.branch_id,
        "company_id": identity.company_id,
        "brand_name": identity.brand_name,
        "primary_color": identity.primary_color,
        "secondary_color": identity.secondary_color,
        "accent_color": identity.accent_color,
        "brand_tone": identity.brand_tone.value if hasattr(identity.brand_tone, "value") else str(identity.brand_tone),
        "target_audience": identity.target_audience,
        "industry": identity.industry,
        "language": identity.language,
        "font_style": identity.font_style,
        "visual_style": identity.visual_style,
        "hashtags_always_include": identity.hashtags_always_include,
        "hashtags_never_include": identity.hashtags_never_include,
        "competitors_to_differentiate": identity.competitors_to_differentiate,
        "is_active": identity.is_active,
        "created_at": identity.created_at.isoformat(),
        "updated_at": identity.updated_at.isoformat(),
    }


@router.patch("/brand-identities/{branch_id}", response_model=BrandIdentityResponse)
async def update_brand_identity(
    branch_id: int = Path(..., description="Branch ID"),
    data: BrandIdentityUpdate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Update the brand identity for a branch.

    Args:
        branch_id: Branch ID.
        data: BrandIdentityUpdate with fields to update.

    Returns:
        Updated BrandIdentityResponse.
    """
    try:
        identity = await CreativeStudioService.update_brand_identity(
            db=db, company_id=company_id, branch_id=branch_id, data=data
        )
        return {
            "id": identity.id,
            "branch_id": identity.branch_id,
            "company_id": identity.company_id,
            "brand_name": identity.brand_name,
            "primary_color": identity.primary_color,
            "secondary_color": identity.secondary_color,
            "accent_color": identity.accent_color,
            "brand_tone": identity.brand_tone.value if hasattr(identity.brand_tone, "value") else str(identity.brand_tone),
            "target_audience": identity.target_audience,
            "industry": identity.industry,
            "language": identity.language,
            "font_style": identity.font_style,
            "visual_style": identity.visual_style,
            "hashtags_always_include": identity.hashtags_always_include,
            "hashtags_never_include": identity.hashtags_never_include,
            "competitors_to_differentiate": identity.competitors_to_differentiate,
            "is_active": identity.is_active,
            "created_at": identity.created_at.isoformat(),
            "updated_at": identity.updated_at.isoformat(),
        }
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc


@router.delete("/brand-identities/{branch_id}")
async def delete_brand_identity(
    branch_id: int = Path(..., description="Branch ID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Deactivate the brand identity for a branch.

    Soft-delete by setting is_active=False. Data is preserved for audit.

    Args:
        branch_id: Branch ID.

    Returns:
        Confirmation message.
    """
    try:
        await CreativeStudioService.delete_brand_identity(
            db=db, company_id=company_id, branch_id=branch_id
        )
        return {"message": f"Brand identity for branch {branch_id} deactivated"}
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc


# ===========================================================================
# Creative Audit
# ===========================================================================


@router.post("/{media_id}/audit", response_model=CreativeAuditResult)
async def run_creative_audit(
    media_id: str = Path(..., description="Media asset UUID"),
    audit_request: CreativeAuditRequest = Body(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
    branch_id: Optional[int] = Query(None, description="Branch ID"),
):
    """
    Run a comprehensive creative audit on a media asset.

    Performs AI analysis for creative quality assessment including:
    - Originality scoring (1-10)
    - Fatigue signal detection
    - Trend alignment analysis
    - Competitor similarity risk assessment
    - Best practices checklist
    - Engagement prediction
    - Similar creative detection in company history
    - Actionable refresh recommendations

    Args:
        media_id: Media asset UUID (must be an image).
        audit_request: Optional CreativeAuditRequest with configuration.
        branch_id: Optional branch for branch-scoped audit.

    Returns:
        CreativeAuditResult with comprehensive audit data.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    try:
        audit_request = audit_request or CreativeAuditRequest()
        audit = await CreativeStudioService.run_creative_audit(
            db=db,
            media=media,
            audit_request=audit_request,
            branch_id=branch_id,
        )
        return {
            "id": audit.id,
            "media_id": audit.media_id,
            "originality_score": audit.originality_score,
            "fatigue_level": audit.fatigue_level.value if hasattr(audit.fatigue_level, "value") else str(audit.fatigue_level),
            "fatigue_signals": audit.fatigue_signals,
            "trend_alignment": audit.trend_alignment,
            "competitor_similarity_risk": audit.competitor_similarity_risk,
            "best_practices_checklist": audit.best_practices_checklist,
            "refresh_recommendations": audit.refresh_recommendations,
            "engagement_prediction": audit.engagement_prediction,
            "similar_media_ids": audit.similar_media_ids,
            "created_at": audit.created_at.isoformat(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Creative audit failed: {str(exc)}",
        ) from exc


@router.get("/audit/summary", response_model=CreativeAuditSummary)
async def get_audit_summary(
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get a portfolio-wide creative audit summary.

    Provides aggregate statistics across all audited media assets:
    - Average originality score
    - Fatigue level distribution
    - Count of high-fatigue assets
    - Trend alignment percentage
    - Top portfolio-wide recommendations
    - Assets needing creative refresh

    Args:
        branch_id: Optional branch filter.

    Returns:
        CreativeAuditSummary with portfolio-wide metrics.
    """
    try:
        summary = await CreativeStudioService.get_portfolio_audit_summary(
            db=db,
            company_id=company_id,
            branch_id=branch_id,
        )
        return summary
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit summary failed: {str(exc)}",
        ) from exc


@router.get("/{media_id}/audit", response_model=CreativeAuditResult)
async def get_media_audit(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get the cached creative audit result for a media asset.

    Args:
        media_id: Media asset UUID.

    Returns:
        CreativeAuditResult or 404 if not audited.
    """
    result = await db.execute(
        select(CreativeAudit).where(
            CreativeAudit.media_id == media_id,
            CreativeAudit.company_id == company_id,
        )
    )
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit not found for media {media_id}. Run POST /media/{media_id}/audit first.",
        )
    return {
        "id": audit.id,
        "media_id": audit.media_id,
        "originality_score": audit.originality_score,
        "fatigue_level": audit.fatigue_level.value if hasattr(audit.fatigue_level, "value") else str(audit.fatigue_level),
        "fatigue_signals": audit.fatigue_signals,
        "trend_alignment": audit.trend_alignment,
        "competitor_similarity_risk": audit.competitor_similarity_risk,
        "best_practices_checklist": audit.best_practices_checklist,
        "refresh_recommendations": audit.refresh_recommendations,
        "engagement_prediction": audit.engagement_prediction,
        "similar_media_ids": audit.similar_media_ids,
        "created_at": audit.created_at.isoformat(),
    }


# ===========================================================================
# Collections
# ===========================================================================


@router.post("/collections", response_model=MediaCollectionResponse)
async def create_collection(
    request: Request,
    data: MediaCollectionCreate = Body(...),
    branch_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Create a new media collection."""
    collection = await MediaOrganizerService.create_collection(
        db=db, company_id=company_id, branch_id=branch_id, data=data
    )
    base_url = str(request.base_url).rstrip("/")
    cover_url = None
    if collection.cover_media_id:
        cover_url = f"{base_url}/media/{collection.cover_media_id}/thumbnail"
    return {
        "id": collection.id,
        "company_id": collection.company_id,
        "branch_id": collection.branch_id,
        "name": collection.name,
        "description": collection.description,
        "cover_media_id": collection.cover_media_id,
        "cover_url": cover_url,
        "item_count": collection.item_count,
        "created_at": collection.created_at.isoformat(),
        "updated_at": collection.updated_at.isoformat(),
        "items": [],
    }


@router.get("/collections", response_model=MediaCollectionListResponse)
async def list_collections(
    request: Request,
    search: Optional[str] = Query(None, description="Search by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    branch_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """List media collections with optional search."""
    collections, total = await MediaOrganizerService.list_collections(
        db=db, company_id=company_id, branch_id=branch_id,
        page=page, page_size=page_size, search=search,
    )
    base_url = str(request.base_url).rstrip("/")
    items = []
    for c in collections:
        cover_url = None
        if c.cover_media_id:
            cover_url = f"{base_url}/media/{c.cover_media_id}/thumbnail"
        items.append({
            "id": c.id,
            "company_id": c.company_id,
            "branch_id": c.branch_id,
            "name": c.name,
            "description": c.description,
            "cover_media_id": c.cover_media_id,
            "cover_url": cover_url,
            "item_count": c.item_count,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "items": [],
        })
    return _paginated_response(items, total, page, page_size)


@router.get("/collections/{collection_id}", response_model=MediaCollectionResponse)
async def get_collection(
    request: Request,
    collection_id: int = Path(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Get a collection with its items."""
    collection = await MediaOrganizerService.get_collection(
        db=db, collection_id=collection_id, company_id=company_id
    )
    base_url = str(request.base_url).rstrip("/")
    cover_url = None
    if collection.cover_media_id:
        cover_url = f"{base_url}/media/{collection.cover_media_id}/thumbnail"

    items = []
    for item in collection.items or []:
        if item.media:
            items.append(_media_list_item(item.media, base_url))

    return {
        "id": collection.id,
        "company_id": collection.company_id,
        "branch_id": collection.branch_id,
        "name": collection.name,
        "description": collection.description,
        "cover_media_id": collection.cover_media_id,
        "cover_url": cover_url,
        "item_count": collection.item_count,
        "created_at": collection.created_at.isoformat(),
        "updated_at": collection.updated_at.isoformat(),
        "items": items,
    }


@router.patch("/collections/{collection_id}", response_model=MediaCollectionResponse)
async def update_collection(
    collection_id: int = Path(...),
    data: MediaCollectionUpdate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Update a collection."""
    collection = await MediaOrganizerService.update_collection(
        db=db, collection_id=collection_id, company_id=company_id, data=data
    )
    return {
        "id": collection.id,
        "company_id": collection.company_id,
        "branch_id": collection.branch_id,
        "name": collection.name,
        "description": collection.description,
        "cover_media_id": collection.cover_media_id,
        "cover_url": None,
        "item_count": collection.item_count,
        "created_at": collection.created_at.isoformat(),
        "updated_at": collection.updated_at.isoformat(),
        "items": [],
    }


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: int = Path(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Delete a collection."""
    await MediaOrganizerService.delete_collection(
        db=db, collection_id=collection_id, company_id=company_id
    )
    return {"message": f"Collection {collection_id} deleted"}


@router.post("/collections/{collection_id}/items", response_model=MediaCollectionResponse)
async def add_items_to_collection(
    collection_id: int = Path(...),
    data: MediaCollectionItemAdd = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Add media items to a collection."""
    collection = await MediaOrganizerService.add_items_to_collection(
        db=db, collection_id=collection_id, company_id=company_id,
        media_ids=data.media_ids, order_index=data.order_index,
    )
    return {
        "id": collection.id,
        "company_id": collection.company_id,
        "branch_id": collection.branch_id,
        "name": collection.name,
        "description": collection.description,
        "cover_media_id": collection.cover_media_id,
        "cover_url": None,
        "item_count": collection.item_count,
        "created_at": collection.created_at.isoformat(),
        "updated_at": collection.updated_at.isoformat(),
        "items": [],
    }


@router.delete("/collections/{collection_id}/items/{media_id}")
async def remove_item_from_collection(
    collection_id: int = Path(...),
    media_id: str = Path(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Remove a media item from a collection."""
    await MediaOrganizerService.remove_item_from_collection(
        db=db, collection_id=collection_id, media_id=media_id, company_id=company_id
    )
    return {"message": f"Item {media_id} removed from collection {collection_id}"}


# ===========================================================================
# Tags
# ===========================================================================


@router.post("/tags", response_model=MediaTagResponse)
async def create_tag(
    data: MediaTagCreate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Create a new media tag."""
    tag = await MediaOrganizerService.create_tag(db=db, company_id=company_id, data=data)
    return {
        "id": tag.id,
        "company_id": tag.company_id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
        "usage_count": 0,
    }


@router.get("/tags", response_model=List[MediaTagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """List all media tags for the company."""
    tags = await MediaOrganizerService.list_tags(db=db, company_id=company_id)
    return [
        {
            "id": tag.id,
            "company_id": tag.company_id,
            "name": tag.name,
            "color": tag.color,
            "created_at": tag.created_at.isoformat(),
            "usage_count": len(tag.mappings) if tag.mappings else 0,
        }
        for tag in tags
    ]


@router.patch("/tags/{tag_id}", response_model=MediaTagResponse)
async def update_tag(
    tag_id: int = Path(...),
    data: MediaTagUpdate = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Update a media tag."""
    result = await db.execute(
        select(MediaTag).where(
            MediaTag.id == tag_id,
            MediaTag.company_id == company_id,
        )
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag {tag_id} not found",
        )
    if data.name is not None:
        tag.name = data.name
    if data.color is not None:
        tag.color = data.color
    await db.commit()
    await db.refresh(tag)
    return {
        "id": tag.id,
        "company_id": tag.company_id,
        "name": tag.name,
        "color": tag.color,
        "created_at": tag.created_at.isoformat(),
        "usage_count": len(tag.mappings) if tag.mappings else 0,
    }


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: int = Path(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Delete a media tag."""
    await MediaOrganizerService.delete_tag(db=db, tag_id=tag_id, company_id=company_id)
    return {"message": f"Tag {tag_id} deleted"}


@router.post("/{media_id}/tags", response_model=Dict[str, Any])
async def add_tags_to_media(
    media_id: str = Path(...),
    data: TagAddRequest = Body(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Add tags to a media asset."""
    media = await MediaOrganizerService.add_tags_to_media(
        db=db, media_id=media_id, company_id=company_id, tag_ids=data.tag_ids
    )
    return {"media_id": media_id, "added_tags": data.tag_ids}


@router.delete("/{media_id}/tags/{tag_id}")
async def remove_tag_from_media(
    media_id: str = Path(...),
    tag_id: int = Path(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """Remove a tag from a media asset."""
    await MediaOrganizerService.remove_tag_from_media(
        db=db, media_id=media_id, tag_id=tag_id, company_id=company_id
    )
    return {"message": f"Tag {tag_id} removed from media {media_id}"}


# ===========================================================================
# Statistics
# ===========================================================================


@router.get("/stats", response_model=MediaStatsResponse)
async def get_media_stats(
    branch_id: Optional[int] = Query(None, description="Filter by branch"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get comprehensive media usage statistics.

    Returns totals, category breakdowns, storage provider distribution,
    virus scan summary, analytics counters, and recent uploads.

    Args:
        branch_id: Optional branch filter.

    Returns:
        MediaStatsResponse with comprehensive statistics.
    """
    stats = await MediaOrganizerService.get_media_stats(
        db=db, company_id=company_id, branch_id=branch_id
    )

    # Get recent uploads (last 5)
    recent, _ = await MediaOrganizerService.search_media(
        db=db, company_id=company_id, branch_id=branch_id,
        sort_by="created_at", sort_order="desc", page=1, page_size=5,
    )

    stats["recent_uploads"] = [_media_list_item(a, "") for a in recent]
    return stats


# ===========================================================================
# Job Status
# ===========================================================================


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str = Path(..., description="Job ID"),
):
    """
    Get the status of an async processing job.

    Args:
        job_id: Job identifier returned by upload/optimization endpoints.

    Returns:
        JobStatusResponse with current status, progress, and result/error.
    """
    queue = MediaOptimizationQueueService()
    job = await queue.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or expired",
        )
    return {
        "job_id": job.get("job_id", job_id),
        "job_type": job.get("job_type", "unknown"),
        "status": job.get("status", "unknown"),
        "progress": job.get("progress"),
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "completed_at": job.get("completed_at"),
    }


# ===========================================================================
# Image Optimization & Processing
# ===========================================================================


@router.get("/{media_id}/info", response_model=Dict[str, Any])
async def get_media_info(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Get detailed technical information about an image media asset.

    Returns image format, dimensions, color mode, ICC profile status,
    bit depth estimation, and EXIF metadata summary.

    Args:
        media_id: Media asset UUID (must be an image).

    Returns:
        Dict with technical image information.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    if media.category != "image":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media info is only available for image files",
        )

    storage = StorageService()
    source_data = await storage.read_media_file(media)
    if not source_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source file not available",
        )

    info = await ImageOptimizationService.get_image_info(source_data)
    info["media_id"] = media.id
    info["mime_type"] = media.mime_type
    info["file_size"] = media.file_size
    info["checksum"] = media.checksum
    info["exif_summary"] = {
        "camera": media.exif_data.get("camera") if media.exif_data else None,
        "gps_available": bool(
            media.exif_data.get("gps") if media.exif_data else False
        ),
        "icc_profile_available": bool(
            media.exif_data.get("has_icc_profile") if media.exif_data else False
        ),
    }

    # Available variants
    info["variants"] = [
        {
            "type": v.variant_type.value,
            "width": v.width,
            "height": v.height,
            "file_size": v.file_size,
        }
        for v in (media.variants or [])
    ]

    # CDN access URL (hybrid)
    access_url = SignedURLService.generate_access_url(
        media=media, variant=None, force_signed=False
    )
    info["access_url"] = access_url

    return info


@router.post("/{media_id}/process-optimize", response_model=Dict[str, Any])
async def trigger_media_optimization(
    media_id: str = Path(..., description="Media asset UUID"),
    db: AsyncSession = Depends(get_db_session),
    current_user: TokenData = Depends(get_current_user),
    company_id: int = Depends(get_company_id),
):
    """
    Trigger on-demand optimization for a media asset.

    Creates optimized JPEG and WebP variants using ImageOptimizationService
    with thread pool execution. Non-blocking: returns a job ID.

    Args:
        media_id: Media asset UUID (must be an image).

    Returns:
        Dict with job_id and status.
    """
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.company_id == company_id,
        )
    )
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media {media_id} not found",
        )

    if media.category != "image":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Optimization is only available for image files",
        )

    queue = MediaOptimizationQueueService()
    job_id = await queue.enqueue_job(
        job_type=JobType.OPTIMIZE,
        media_id=media.id,
        company_id=company_id,
    )

    return {
        "media_id": media_id,
        "job_id": job_id,
        "status": "queued",
        "message": "Optimization job queued. Check /media/jobs/{job_id} for progress.",
    }


# ===========================================================================
# Signed URL Verification (CDN edge compatibility)
# ===========================================================================


@router.get("/signed/verify")
async def verify_signed_url_endpoint(
    token: str = Query(..., description="Signed URL token"),
):
    """
    Verify a signed URL token and return decoded payload.

    CDN edge servers can use this endpoint to validate signed URLs
    before serving cached content.

    Args:
        token: The signed URL token from the URL path.

    Returns:
        Decoded payload if valid, 403 if invalid or expired.
    """
    payload = SignedURLService.verify_signed_url(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired signed URL",
        )
    return {
        "valid": True,
        "media_id": payload["media_id"],
        "filename": payload["filename"],
        "variant": payload["variant"],
        "expires": datetime.fromtimestamp(payload["expires"], tz=timezone.utc).isoformat(),
    }
