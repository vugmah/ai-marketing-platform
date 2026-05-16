"""
Service layer for the Creative Studio & Media Pipeline module.

Provides eight core services:
- UploadService: File upload handling, validation, and storage
- ThumbnailService: Image/video thumbnail generation via Pillow/ffmpeg
- StorageService: Abstract storage backend (local + S3-compatible)
- MediaOrganizerService: Collections, tagging, search/filter, bulk operations
- AIImageAnalysisService: OpenAI Vision integration for image analysis with
  brand-aware caption/hashtag generation, creative scoring, object detection,
  Instagram optimization, and brand alignment checking
- CreativeStudioService: Creative audit, fatigue detection, portfolio analysis,
  and brand identity management
- MediaOptimizationQueueService: Redis-based async job queue
- SignedURLService: Time-limited signed URLs for secure media access
"""

import asyncio
import base64
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from fastapi import UploadFile
from PIL import Image, ImageOps
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import NotFoundError, ValidationError
from app.media.constants import (
    AI_ANALYSIS_DETAIL_LEVEL,
    AI_ANALYSIS_MAX_TOKENS,
    AI_ANALYSIS_PROMPTS,
    AI_ANALYSIS_TIMEOUT_SECONDS,
    AI_ANALYSIS_VISION_MODEL,
    ALLOWED_MIME_TYPES,
    BRAND_AWARE_CAPTION_PROMPT,
    BRAND_AWARE_HASHTAG_PROMPT,
    CHECKSUM_ALGORITHM,
    CLAMAV_HOST,
    CLAMAV_PORT,
    CLAMAV_TIMEOUT_SECONDS,
    CREATIVE_FATIGUE_CONFIG,
    DEFAULT_PAGE_SIZE,
    EXTENSION_TO_MIME,
    FACEBOOK_FORMAT_SPECS,
    IMAGE_PROCESSING_MAX_WORKERS,
    IMAGE_PROCESSING_TIMEOUT_SECONDS,
    IMAGE_QUALITY_SETTINGS,
    INSTAGRAM_FORMAT_SPECS,
    JOB_QUEUE_PREFIX,
    JOB_STATUS_PREFIX,
    JOB_TIMEOUT_SECONDS,
    LOCAL_THUMBNAIL_DIR,
    LOCAL_UPLOAD_DIR,
    LOCAL_VARIANTS_DIR,
    MAX_DOCUMENT_SIZE,
    MAX_IMAGE_SIZE,
    MAX_VIDEO_SIZE,
    MEDIA_PATH_TEMPLATE,
    MIME_MAGIC_BYTES,
    MIME_TYPE_CATEGORIES,
    OPTIMIZATION_COLOR_PROFILE_ACTION,
    OPTIMIZATION_MAX_DIMENSION,
    OPTIMIZATION_MAX_HEIGHT,
    OPTIMIZATION_MAX_WIDTH,
    OPTIMIZATION_PROGRESSIVE_JPEG,
    OPTIMIZATION_QUALITY_JPEG,
    OPTIMIZATION_QUALITY_WEBP,
    OPTIMIZATION_STRIP_EXIF,
    OPTIMIZATION_STRIP_ICC,
    OPTIMIZATION_TARGET_SIZE_BYTES,
    PDF_VERSION_MAP,
    PRESIGNED_UPLOAD_EXPIRY_SECONDS,
    PROCESSABLE_IMAGE_TYPES,
    PROCESSABLE_VIDEO_TYPES,
    SIGNED_URL_EXPIRY_SECONDS,
    THUMBNAIL_DIMENSIONS,
    THUMBNAIL_SIZE_MAP,
    THUMBNAIL_PATH_TEMPLATE,
    TIKTOK_FORMAT_SPECS,
    VARIANT_PATH_TEMPLATE,
    VIRUS_SCAN_ENABLED,
    VIRUS_SCAN_MAX_FILE_SIZE,
    AnalysisType,
    JobType,
    MediaStatus,
    StorageProvider,
    VariantType,
    VirusScanStatus,
)
from app.media.models import (
    AIImageAnalysis,
    BranchBrandIdentity,
    BrandTone,
    CreativeAudit,
    FatigueLevel,
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
    BrandIdentityCreate,
    BrandIdentityUpdate,
    CreativeAuditRequest,
    MediaCollectionCreate,
    MediaCollectionUpdate,
    MediaTagCreate,
    UploadInitiateRequest,
)
from app.redis_client import get_redis_client


# ===========================================================================
# UploadService
# ===========================================================================


class UploadService:
    """Handles multipart file upload, validation, and storage coordination."""

    ALLOWED_TYPES = ALLOWED_MIME_TYPES
    MAX_SIZES = {
        "image": MAX_IMAGE_SIZE,
        "video": MAX_VIDEO_SIZE,
        "document": MAX_DOCUMENT_SIZE,
    }

    # ------------------------------------------------------------------
    # MIME type validation via magic bytes (filename-independent)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_magic_bytes(file_data: bytes, declared_mime: str) -> Tuple[bool, str]:
        """
        Validate file content against declared MIME type using magic bytes.

        Returns (is_valid, detected_mime_type).
        Falls back to declared MIME if magic bytes are ambiguous.
        """
        if len(file_data) < 8:
            return True, declared_mime

        # Check specific PDF version signatures
        for sig, mime in PDF_VERSION_MAP.items():
            if file_data.startswith(sig):
                return True, mime

        # Check generic magic bytes
        for magic, mime in MIME_MAGIC_BYTES.items():
            if mime is None:
                continue
            if file_data.startswith(magic):
                # Special handling for WebP (RIFF....WEBP)
                if magic == b"RIFF" and len(file_data) >= 12:
                    if file_data[WEBP_MAGIC_OFFSET:WEBP_MAGIC_OFFSET + 4] == WEBP_MAGIC_EXPECTED:
                        return True, "image/webp"
                    # Could be AVI or other RIFF format
                    if len(file_data) >= 12 and file_data[8:12] == b"AVI ":
                        return True, "video/avi"
                    continue
                return True, mime

        # Check MP4/MOV (ftyp-based)
        if len(file_data) >= 20 and file_data[4:8] == b"ftyp":
            brand = file_data[8:12]
            brand_map = {
                b"qt  ": "video/quicktime",
                b"isom": "video/mp4",
                b"mp41": "video/mp4",
                b"mp42": "video/mp4",
                b"avc1": "video/mp4",
                b"M4V ": "video/mp4",
                b"M4A ": "video/mp4",
                b"3gp4": "video/mp4",
                b"3gp5": "video/mp4",
                b"3g2a": "video/mp4",
                b"webm": "video/webm",
            }
            detected = brand_map.get(brand)
            if detected:
                return True, detected
            return True, declared_mime  # ftyp but unknown brand

        # Unrecognized magic bytes - trust the declared MIME if in whitelist
        if declared_mime in ALLOWED_MIME_TYPES:
            return True, declared_mime

        return False, declared_mime

    # ------------------------------------------------------------------
    # Extension whitelist validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_extension(filename: str) -> bool:
        """Validate that file extension is in the allowed whitelist."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in EXTENSION_TO_MIME

    # ------------------------------------------------------------------
    # EXIF / metadata extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_exif_metadata(file_data: bytes) -> Dict[str, Any]:
        """
        Extract EXIF metadata from image file data using Pillow.

        Returns a dict with camera info, dimensions, orientation, GPS, etc.
        Returns empty dict if no EXIF data or not an image.
        """
        metadata: Dict[str, Any] = {}
        try:
            with Image.open(BytesIO(file_data)) as img:
                # Basic image info
                metadata["format"] = img.format
                metadata["mode"] = img.mode
                if hasattr(img, "info"):
                    info = img.info
                    if "dpi" in info:
                        metadata["dpi"] = info["dpi"]

                # EXIF data
                exif = img._getexif()
                if exif:
                    exif_dict: Dict[str, Any] = {}
                    for tag_id, value in exif.items():
                        # Map known EXIF tag IDs to names
                        tag_name = UploadService._exif_tag_name(tag_id)
                        # Handle binary/unserializable values
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="replace").strip("\x00")
                            except Exception:
                                value = value.hex()
                        elif isinstance(value, (tuple, list)):
                            value = list(value)
                        exif_dict[tag_name] = value
                    metadata["exif"] = exif_dict

                    # Extract camera info summary
                    camera_info = UploadService._extract_camera_info(exif_dict)
                    if camera_info:
                        metadata["camera"] = camera_info

                    # Extract GPS info
                    gps_info = UploadService._extract_gps_info(exif_dict)
                    if gps_info:
                        metadata["gps"] = gps_info

                # ICC color profile
                if "icc_profile" in img.info:
                    metadata["has_icc_profile"] = True
                if "color_profile" in img.info:
                    metadata["color_profile"] = img.info["color_profile"]

        except Exception:
            pass

        return metadata

    @staticmethod
    def _exif_tag_name(tag_id: int) -> str:
        """Map common EXIF tag IDs to human-readable names."""
        tag_map = {
            0x010F: "make",
            0x0110: "model",
            0x0112: "orientation",
            0x011A: "x_resolution",
            0x011B: "y_resolution",
            0x0128: "resolution_unit",
            0x0131: "software",
            0x0132: "datetime",
            0x013B: "artist",
            0x829D: "exposure_time",
            0x829F: "f_number",
            0x8822: "exposure_program",
            0x8827: "iso_speed_ratings",
            0x9000: "exif_version",
            0x9003: "datetime_original",
            0x9004: "datetime_digitized",
            0x9201: "shutter_speed_value",
            0x9202: "aperture_value",
            0x9203: "brightness_value",
            0x9204: "exposure_bias",
            0x9205: "max_aperture_value",
            0x9206: "subject_distance",
            0x9207: "metering_mode",
            0x9208: "light_source",
            0x9209: "flash",
            0x920A: "focal_length",
            0x927C: "maker_note",
            0x9286: "user_comment",
            0xA001: "color_space",
            0xA002: "pixel_x_dimension",
            0xA003: "pixel_y_dimension",
            0xA20E: "focal_plane_x_resolution",
            0xA20F: "focal_plane_y_resolution",
            0xA210: "focal_plane_resolution_unit",
            0xA217: "sensing_method",
            0xA404: "digital_zoom_ratio",
            0xA405: "focal_length_in_35mm",
            0xA420: "image_unique_id",
            0x8825: "gps_info",  # GPS IFD pointer
        }
        return tag_map.get(tag_id, f"tag_{tag_id:04X}")

    @staticmethod
    def _extract_camera_info(exif_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract camera/lens info from EXIF dict."""
        camera = {}
        if "make" in exif_dict:
            camera["make"] = str(exif_dict["make"]).strip()
        if "model" in exif_dict:
            camera["model"] = str(exif_dict["model"]).strip()
        if "software" in exif_dict:
            camera["software"] = str(exif_dict["software"]).strip()
        if "focal_length" in exif_dict:
            fl = exif_dict["focal_length"]
            camera["focal_length_mm"] = round(float(fl), 1) if not isinstance(fl, str) else fl
        if "f_number" in exif_dict:
            fn = exif_dict["f_number"]
            camera["aperture"] = round(float(fn), 1) if not isinstance(fn, str) else fn
        if "iso_speed_ratings" in exif_dict:
            camera["iso"] = exif_dict["iso_speed_ratings"]
        if "exposure_time" in exif_dict:
            camera["exposure_time"] = str(exif_dict["exposure_time"])
        if "flash" in exif_dict:
            camera["flash"] = exif_dict["flash"]
        return camera if camera else None

    @staticmethod
    def _extract_gps_info(exif_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract GPS coordinates from EXIF dict if present."""
        raw_gps = exif_dict.get("gps_info")
        if not raw_gps:
            return None
        gps = {}
        try:
            if isinstance(raw_gps, dict):
                lat_ref = raw_gps.get("GPSLatitudeRef")
                lat_vals = raw_gps.get("GPSLatitude")
                lon_ref = raw_gps.get("GPSLongitudeRef")
                lon_vals = raw_gps.get("GPSLongitude")
                if lat_vals and lon_vals:
                    gps["latitude"] = UploadService._dms_to_decimal(lat_vals, lat_ref)
                    gps["longitude"] = UploadService._dms_to_decimal(lon_vals, lon_ref)
            else:
                # Raw GPS EXIF as flat dict entries
                for key in ["GPSLatitude", "GPSLongitude", "GPSLatitudeRef", "GPSLongitudeRef",
                            "GPSAltitude", "GPSTimeStamp", "GPSDateStamp"]:
                    if key in exif_dict:
                        gps[key] = exif_dict[key]
        except Exception:
            pass
        return gps if gps else None

    @staticmethod
    def _dms_to_decimal(dms_vals, ref) -> float:
        """Convert DMS (degrees, minutes, seconds) to decimal degrees."""
        try:
            if isinstance(dms_vals, (list, tuple)) and len(dms_vals) == 3:
                d = float(dms_vals[0])
                m = float(dms_vals[1])
                s = float(dms_vals[2])
                decimal = d + m / 60 + s / 3600
                if ref in ("S", "W"):
                    decimal = -decimal
                return round(decimal, 6)
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _detect_category(mime_type: str) -> str:
        """Categorize a MIME type into image/video/document."""
        for category, types in MIME_TYPE_CATEGORIES.items():
            if mime_type in types:
                return category
        return "unknown"

    @staticmethod
    def _generate_unique_filename(original: str, mime_type: str) -> str:
        """Generate a unique filename preserving the original extension."""
        uid = uuid.uuid4().hex[:16]
        name_part = os.path.splitext(original)[0]
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name_part)[:50]
        ext = UploadService._extension_for_mime(mime_type) or ".bin"
        return f"{safe_name}_{uid}{ext}"

    @staticmethod
    def _extension_for_mime(mime_type: str) -> Optional[str]:
        """Get a file extension for a given MIME type."""
        for ext, mt in EXTENSION_TO_MIME.items():
            if mt == mime_type:
                return ext
        return None

    @staticmethod
    def _generate_checksum(data: bytes) -> str:
        """Generate SHA-256 checksum for file data."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    async def validate_upload(
        filename: str,
        mime_type: str,
        file_size: int,
        category: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Validate a file upload request.

        Args:
            filename: Original filename.
            mime_type: Detected MIME type.
            file_size: File size in bytes.
            category: Optional category override.

        Returns:
            Tuple of (category, detected_mime_type).

        Raises:
            ValidationError: If validation fails.
        """
        if not mime_type:
            raise ValidationError(detail="Could not determine MIME type")

        if mime_type not in UploadService.ALLOWED_TYPES:
            raise ValidationError(
                detail=f"File type '{mime_type}' not allowed. "
                "Allowed types: image/*, video/*, application/pdf"
            )

        detected_category = category or UploadService._detect_category(mime_type)
        max_size = UploadService.MAX_SIZES.get(detected_category, MAX_IMAGE_SIZE)

        if file_size > max_size:
            raise ValidationError(
                detail=f"File size {file_size} bytes exceeds maximum of {max_size} bytes "
                f"for {detected_category} files"
            )

        if file_size <= 0:
            raise ValidationError(detail="File must have content (size > 0)")

        return detected_category, mime_type

    @staticmethod
    async def process_upload(
        db: AsyncSession,
        user_id: int,
        company_id: int,
        branch_id: Optional[int],
        upload_file: UploadFile,
        storage_provider: Optional[StorageProvider] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MediaAsset:
        # Resolve storage provider from settings if not explicitly passed
        if storage_provider is None:
            provider_name = StorageService._default_provider()
            try:
                storage_provider = StorageProvider(provider_name)
            except ValueError:
                storage_provider = StorageProvider.LOCAL
        """
        Process a complete file upload: validate, store, and create database record.

        Args:
            db: Async database session.
            user_id: ID of the uploading user.
            company_id: Tenant company ID.
            branch_id: Optional branch ID.
            upload_file: FastAPI UploadFile.
            storage_provider: Target storage backend.
            metadata: Optional metadata dict.

        Returns:
            Created MediaAsset record.
        """
        original = upload_file.filename or "unnamed"
        mime_type = upload_file.content_type or "application/octet-stream"

        # Read file data
        file_data = await upload_file.read()
        file_size = len(file_data)

        # Validate extension whitelist
        if not UploadService.validate_extension(original):
            raise ValidationError(
                detail=f"File extension not allowed for '{original}'. "
                "Allowed extensions: jpg, jpeg, png, gif, webp, svg, bmp, tiff, "
                "heic, heif, avif, mp4, webm, mov, avi, mkv, ogv, mpeg, pdf"
            )

        # Validate magic bytes (content-based MIME verification)
        magic_valid, detected_mime = UploadService.validate_magic_bytes(
            file_data[:8192], mime_type
        )
        if not magic_valid:
            raise ValidationError(
                detail=f"File content does not match declared MIME type '{mime_type}'. "
                "Possible file type spoofing attempt."
            )
        # Trust detected MIME if it's more specific
        if detected_mime and detected_mime != mime_type:
            mime_type = detected_mime

        # Validate size and MIME type
        category, mime_type = await UploadService.validate_upload(
            original, mime_type, file_size
        )

        # Generate unique filename and storage paths
        unique_name = UploadService._generate_unique_filename(original, mime_type)
        checksum = UploadService._generate_checksum(file_data)

        now = datetime.now(timezone.utc)
        path_ctx = {
            "company_id": str(company_id),
            "year": str(now.year),
            "month": f"{now.month:02d}",
            "filename": unique_name,
        }
        file_path = MEDIA_PATH_TEMPLATE.format(**path_ctx)
        storage_key = file_path

        # Store file
        storage = StorageService()
        if storage_provider == StorageProvider.LOCAL:
            full_path = await storage._store_local(file_data, file_path)
            storage_key = full_path
        else:
            await storage._store_remote(file_data, storage_key, storage_provider.value)

        # Extract dimensions for images
        width, height = None, None
        exif_metadata: Dict[str, Any] = {}
        if mime_type in PROCESSABLE_IMAGE_TYPES:
            width, height = UploadService._extract_image_dimensions(file_data)
            # Extract EXIF metadata
            exif_metadata = UploadService.extract_exif_metadata(file_data)

        # Determine virus scan status (skip for large files, scan enabled)
        scan_status = VirusScanStatus.SKIPPED
        if VIRUS_SCAN_ENABLED and file_size <= VIRUS_SCAN_MAX_FILE_SIZE:
            scan_status = VirusScanStatus.PENDING

        # Create media asset record
        media = MediaAsset(
            id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            filename=unique_name,
            original_filename=original,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            category=category,
            width=width,
            height=height,
            storage_provider=storage_provider,
            storage_key=storage_key,
            checksum=checksum,
            status=MediaStatus.PROCESSING,
            metadata_=metadata or {},
            exif_data=exif_metadata,
            virus_scan_status=scan_status.value,
            created_by=user_id,
        )

        db.add(media)
        await db.commit()
        await db.refresh(media)

        # Create analytics record
        analytics = MediaAnalytics(media_id=media.id)
        db.add(analytics)
        await db.commit()

        # Queue thumbnail generation and optimization
        queue = MediaOptimizationQueueService()
        await queue.enqueue_job(
            job_type=JobType.THUMBNAIL,
            media_id=media.id,
            company_id=company_id,
        )

        # Queue virus scan if enabled
        if VIRUS_SCAN_ENABLED and scan_status == VirusScanStatus.PENDING:
            await queue.enqueue_job(
                job_type=JobType.VIRUS_SCAN,
                media_id=media.id,
                company_id=company_id,
            )

        return media

    @staticmethod
    def _extract_image_dimensions(data: bytes) -> Tuple[Optional[int], Optional[int]]:
        """Extract image width and height using Pillow."""
        try:
            with Image.open(BytesIO(data)) as img:
                return img.width, img.height
        except Exception:
            return None, None

    @staticmethod
    async def create_upload_record(
        db: AsyncSession,
        user_id: int,
        company_id: int,
        branch_id: Optional[int],
        data: UploadInitiateRequest,
        storage_provider: Optional[StorageProvider] = None,
    ) -> MediaAsset:
        # Resolve storage provider from settings if not explicitly passed
        if storage_provider is None:
            provider_name = StorageService._default_provider()
            try:
                storage_provider = StorageProvider(provider_name)
            except ValueError:
                storage_provider = StorageProvider.LOCAL
        """
        Create a media asset record for a presigned upload (before file arrives).

        Args:
            db: Async database session.
            user_id: Uploading user ID.
            company_id: Tenant company ID.
            branch_id: Optional branch ID.
            data: Upload initiation request data.
            storage_provider: Target storage backend.

        Returns:
            Created MediaAsset record in 'uploading' status.
        """
        category = UploadService._detect_category(data.mime_type)
        unique_name = UploadService._generate_unique_filename(data.filename, data.mime_type)

        now = datetime.now(timezone.utc)
        path_ctx = {
            "company_id": str(company_id),
            "year": str(now.year),
            "month": f"{now.month:02d}",
            "filename": unique_name,
        }
        file_path = MEDIA_PATH_TEMPLATE.format(**path_ctx)

        media = MediaAsset(
            id=str(uuid.uuid4()),
            company_id=company_id,
            branch_id=branch_id,
            filename=unique_name,
            original_filename=data.filename,
            file_path=file_path,
            file_size=data.file_size,
            mime_type=data.mime_type,
            category=category,
            storage_provider=storage_provider,
            storage_key=file_path,
            status=MediaStatus.UPLOADING,
            metadata_=data.metadata or {},
            exif_data={},
            virus_scan_status=VirusScanStatus.PENDING.value
            if VIRUS_SCAN_ENABLED
            else VirusScanStatus.SKIPPED.value,
            created_by=user_id,
        )

        db.add(media)
        await db.commit()
        await db.refresh(media)

        return media


# ===========================================================================
# ThumbnailService
# ===========================================================================


class ThumbnailService:
    """
    Generates image thumbnails and video preview frames.

    Uses Pillow for image processing and ffmpeg for video thumbnail extraction.
    Creates responsive size variants (thumbnail/small/medium/large) and WebP
    optimized versions.
    """

    @staticmethod
    async def generate_image_variants(
        db: AsyncSession,
        media: MediaAsset,
        source_data: bytes,
    ) -> List[MediaVariant]:
        """
        Generate all image variant types from source data.

        Args:
            db: Async database session.
            media: Parent MediaAsset record.
            source_data: Raw image file bytes.

        Returns:
            List of created MediaVariant records.
        """
        variants: List[MediaVariant] = []

        for size_key, (max_w, max_h) in THUMBNAIL_DIMENSIONS.items():
            variant_type = VariantType(size_key.upper())
            variant_data = await ThumbnailService._resize_image(
                source_data, max_w, max_h, media.mime_type
            )
            if variant_data is None:
                continue

            variant_path = ThumbnailService._variant_path(
                media, size_key, media.mime_type
            )

            storage = StorageService()
            if media.storage_provider == StorageProvider.LOCAL:
                await storage._store_local(variant_data, variant_path)
            else:
                await storage._store_remote(
                    variant_data, variant_path, media.storage_provider.value
                )

            img = Image.open(BytesIO(variant_data))
            quality = IMAGE_QUALITY_SETTINGS.get(size_key, 80)

            variant = MediaVariant(
                media_id=media.id,
                variant_type=variant_type,
                file_path=variant_path,
                width=img.width,
                height=img.height,
                file_size=len(variant_data),
                quality=quality,
            )
            db.add(variant)
            variants.append(variant)

        # WebP variant (from original size, optimized)
        webp_data = await ThumbnailService._convert_to_webp(source_data)
        if webp_data:
            webp_path = ThumbnailService._variant_path(media, "optimized", "image/webp")
            if media.storage_provider == StorageProvider.LOCAL:
                await storage._store_local(webp_data, webp_path)
            else:
                await storage._store_remote(
                    webp_data, webp_path, media.storage_provider.value
                )

            img = Image.open(BytesIO(webp_data))
            variant = MediaVariant(
                media_id=media.id,
                variant_type=VariantType.WEBP,
                file_path=webp_path,
                width=img.width,
                height=img.height,
                file_size=len(webp_data),
                quality=IMAGE_QUALITY_SETTINGS.get("webp", 80),
            )
            db.add(variant)
            variants.append(variant)

        if variants:
            await db.commit()
            for v in variants:
                await db.refresh(v)

            # Update media thumbnail path
            thumbnail = next(
                (v for v in variants if v.variant_type == VariantType.THUMBNAIL), None
            )
            if thumbnail:
                media.thumbnail_path = thumbnail.file_path
                await db.commit()

        return variants

    @staticmethod
    async def generate_video_thumbnail(
        db: AsyncSession,
        media: MediaAsset,
        source_data: bytes,
    ) -> Optional[MediaVariant]:
        """
        Generate a thumbnail frame from a video file using ffmpeg.

        Args:
            db: Async database session.
            media: Parent MediaAsset record.
            source_data: Raw video file bytes.

        Returns:
            Created MediaVariant record or None.
        """
        frame_data = await ThumbnailService._extract_video_frame(source_data)
        if frame_data is None:
            return None

        # Resize to thumbnail dimensions
        thumb_data = await ThumbnailService._resize_image(
            frame_data,
            THUMBNAIL_DIMENSIONS["thumbnail"][0],
            THUMBNAIL_DIMENSIONS["thumbnail"][1],
            "image/jpeg",
        )
        if thumb_data is None:
            return None

        variant_path = ThumbnailService._variant_path(
            media, "video_thumbnail", "image/jpeg"
        )
        storage = StorageService()
        if media.storage_provider == StorageProvider.LOCAL:
            await storage._store_local(thumb_data, variant_path)
        else:
            await storage._store_remote(
                thumb_data, variant_path, media.storage_provider.value
            )

        img = Image.open(BytesIO(thumb_data))
        variant = MediaVariant(
            media_id=media.id,
            variant_type=VariantType.VIDEO_THUMBNAIL,
            file_path=variant_path,
            width=img.width,
            height=img.height,
            file_size=len(thumb_data),
            quality=IMAGE_QUALITY_SETTINGS.get("thumbnail", 75),
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)

        media.thumbnail_path = variant_path
        await db.commit()

        return variant

    @staticmethod
    async def _resize_image(
        data: bytes,
        max_width: int,
        max_height: int,
        mime_type: str,
    ) -> Optional[bytes]:
        """Resize an image to fit within max dimensions while maintaining aspect ratio."""
        try:
            with Image.open(BytesIO(data)) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                output = BytesIO()
                fmt = "JPEG"
                if mime_type == "image/png":
                    fmt = "PNG"
                elif mime_type == "image/webp":
                    fmt = "WEBP"
                elif mime_type == "image/gif":
                    fmt = "GIF"

                img.save(output, format=fmt, quality=IMAGE_QUALITY_SETTINGS.get("thumbnail", 75))
                return output.getvalue()
        except Exception:
            return None

    @staticmethod
    async def _convert_to_webp(data: bytes) -> Optional[bytes]:
        """Convert an image to WebP format with optimized quality."""
        try:
            with Image.open(BytesIO(data)) as img:
                img = ImageOps.exif_transpose(img)
                output = BytesIO()
                img.save(
                    output,
                    format="WEBP",
                    quality=IMAGE_QUALITY_SETTINGS.get("webp", 80),
                    method=6,
                )
                return output.getvalue()
        except Exception:
            return None

    @staticmethod
    async def _extract_video_frame(data: bytes) -> Optional[bytes]:
        """Extract a frame from video data at 25% duration using ffmpeg."""
        try:
            with BytesIO(data) as bio:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-i", "-",
                    "-ss", "00:00:01",
                    "-vframes", "1",
                    "-f", "image2pipe",
                    "-vcodec", "mjpeg",
                    "-",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(input=bio.getvalue()),
                    timeout=30,
                )
                if proc.returncode == 0 and stdout:
                    return stdout
                return None
        except Exception:
            return None

    @staticmethod
    def _variant_path(media: MediaAsset, variant_name: str, mime_type: str) -> str:
        """Generate a file path for a media variant."""
        now = datetime.now(timezone.utc)
        ext = UploadService._extension_for_mime(mime_type) or ".jpg"
        ctx = {
            "company_id": str(media.company_id),
            "year": str(now.year),
            "month": f"{now.month:02d}",
            "variant": variant_name,
            "filename": f"{os.path.splitext(media.filename)[0]}{ext}",
        }
        return THUMBNAIL_PATH_TEMPLATE.format(**ctx)


# ===========================================================================
# StorageService
# ===========================================================================


class StorageService:
    """
    Abstract storage backend supporting local filesystem and S3-compatible storage.

    Generates presigned URLs for direct browser uploads and signed download URLs
    for secure media access. CDN-ready with URL transformation support.

    PRODUCTION RULE: local storage is blocked in production/staging.
    S3 or R2 must be configured via settings.
    """

    # ------------------------------------------------------------------
    # Config helpers - read from settings, not os.environ directly
    # ------------------------------------------------------------------

    @staticmethod
    def _get_provider_config(provider: str) -> Dict[str, str]:
        """Get endpoint/access/bucket config for a provider from settings."""
        p = provider.upper()
        return {
            "endpoint": getattr(settings, f"{p}_ENDPOINT_URL", ""),
            "region": getattr(settings, f"{p}_REGION", "auto"),
            "access_key": getattr(settings, f"{p}_ACCESS_KEY_ID", ""),
            "secret_key": getattr(settings, f"{p}_SECRET_ACCESS_KEY", ""),
            "bucket": getattr(settings, f"{p}_BUCKET_NAME", "media"),
        }

    @staticmethod
    def _get_base_path() -> str:
        """Get the base storage path from settings (dev only)."""
        base = getattr(settings, "MEDIA_STORAGE_PATH", "./media_storage")
        return os.path.abspath(base)

    @staticmethod
    def _default_provider() -> str:
        """Return the configured default storage provider."""
        return getattr(settings, "STORAGE_PROVIDER", "local").lower()

    @staticmethod
    def _require_non_local() -> None:
        """Fail fast if local storage is used in production/staging."""
        env = os.environ.get("ENVIRONMENT", "development").lower()
        if env in ("production", "staging"):
            raise RuntimeError(
                "Local filesystem storage is NOT allowed in production/staging. "
                "Set STORAGE_PROVIDER to 's3' or 'r2' and configure endpoint credentials."
            )

    # ------------------------------------------------------------------
    # Local storage (DEVELOPMENT ONLY)
    # ------------------------------------------------------------------

    @staticmethod
    async def _store_local(data: bytes, relative_path: str) -> str:
        """
        Store file data on local filesystem.

        Args:
            data: File bytes.
            relative_path: Relative path within storage.

        Returns:
            Full absolute path to stored file.
        """
        StorageService._require_non_local()
        base = StorageService._get_base_path()
        full_path = os.path.join(base, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(data)
        return full_path

    @staticmethod
    async def _read_local(relative_path: str) -> Optional[bytes]:
        """Read file data from local filesystem."""
        base = StorageService._get_base_path()
        full_path = os.path.join(base, relative_path)
        if os.path.exists(full_path):
            with open(full_path, "rb") as f:
                return f.read()
        return None

    @staticmethod
    async def _delete_local(relative_path: str) -> bool:
        """Delete a file from local filesystem."""
        try:
            base = StorageService._get_base_path()
            full_path = os.path.join(base, relative_path)
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Remote storage (S3 / R2)
    # ------------------------------------------------------------------

    @staticmethod
    async def _store_remote(data: bytes, key: str, provider: str) -> None:
        """
        Store file data to S3-compatible remote storage.

        Args:
            data: File bytes.
            key: Storage object key.
            provider: 's3' or 'r2'.
        """
        import aiobotocore.session

        cfg = StorageService._get_provider_config(provider)
        endpoint, region, access_key, secret_key, bucket = (
            cfg["endpoint"], cfg["region"], cfg["access_key"], cfg["secret_key"], cfg["bucket"]
        )

        if not all([endpoint, access_key, secret_key]):
            raise RuntimeError(f"{provider} storage not configured")

        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        ) as client:
            await client.put_object(Bucket=bucket, Key=key, Body=data)

    @staticmethod
    async def _read_remote(key: str, provider: str) -> Optional[bytes]:
        """Read file data from S3-compatible remote storage."""
        import aiobotocore.session

        cfg = StorageService._get_provider_config(provider)
        endpoint, region, access_key, secret_key, bucket = (
            cfg["endpoint"], cfg["region"], cfg["access_key"], cfg["secret_key"], cfg["bucket"]
        )

        if not all([endpoint, access_key, secret_key]):
            return None

        try:
            session = aiobotocore.session.get_session()
            async with session.create_client(
                "s3",
                region_name=region,
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            ) as client:
                response = await client.get_object(Bucket=bucket, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except Exception:
            return None

    @staticmethod
    async def _delete_remote(key: str, provider: str) -> bool:
        """Delete an object from S3-compatible remote storage."""
        import aiobotocore.session

        cfg = StorageService._get_provider_config(provider)
        endpoint, region, access_key, secret_key, bucket = (
            cfg["endpoint"], cfg["region"], cfg["access_key"], cfg["secret_key"], cfg["bucket"]
        )

        if not all([endpoint, access_key, secret_key]):
            return False

        try:
            session = aiobotocore.session.get_session()
            async with session.create_client(
                "s3",
                region_name=region,
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            ) as client:
                await client.delete_object(Bucket=bucket, Key=key)
                return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Unified storage operations
    # ------------------------------------------------------------------

    @staticmethod
    async def read_media_file(media: MediaAsset) -> Optional[bytes]:
        """Read a media file from its storage backend."""
        if media.storage_provider == StorageProvider.LOCAL:
            return await StorageService._read_local(media.file_path)
        else:
            return await StorageService._read_remote(
                media.storage_key or media.file_path,
                media.storage_provider.value,
            )

    @staticmethod
    async def delete_media_file(media: MediaAsset) -> bool:
        """Delete a media file from its storage backend."""
        if media.storage_provider == StorageProvider.LOCAL:
            return await StorageService._delete_local(media.file_path)
        else:
            return await StorageService._delete_remote(
                media.storage_key or media.file_path,
                media.storage_provider.value,
            )

    @staticmethod
    async def generate_presigned_upload_url(
        media: MediaAsset,
        provider: str = "",
        expiry: int = PRESIGNED_UPLOAD_EXPIRY_SECONDS,
    ) -> Dict[str, str]:
        """
        Generate a presigned URL for direct browser upload.

        Args:
            media: MediaAsset with pre-allocated storage_key.
            provider: 's3' or 'r2' (defaults to STORAGE_PROVIDER setting).
            expiry: URL expiry in seconds.

        Returns:
            Dict with upload_url, fields, and media_id.
        """
        import aiobotocore.session

        provider = provider or StorageService._default_provider()
        cfg = StorageService._get_provider_config(provider)
        endpoint, region, access_key, secret_key, bucket = (
            cfg["endpoint"], cfg["region"], cfg["access_key"], cfg["secret_key"], cfg["bucket"]
        )

        if not all([endpoint, access_key, secret_key]):
            raise RuntimeError(f"{provider} storage not configured for presigned URLs")

        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        ) as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": media.storage_key,
                    "ContentType": media.mime_type,
                },
                ExpiresIn=expiry,
            )
            return {
                "upload_url": url,
                "media_id": media.id,
                "storage_key": media.storage_key,
                "expires_in": str(expiry),
            }


# ===========================================================================
# VirusScanningService (ClamAV placeholder - future integration)
# ===========================================================================


class VirusScanningService:
    """
    Virus scanning service using ClamAV (placeholder for future activation).

    Currently a skeleton that logs scan requests. When VIRUS_SCAN_ENABLED
    is set in environment, it will attempt to connect to a ClamAV daemon.

    FUTURE: Activate by setting VIRUS_SCAN_ENABLED=true and CLAMAV_HOST.
    The service supports:
    - Streaming scan via clamd INSTREAM protocol
    - Batch scanning for bulk operations
    - Status tracking per media asset
    - Quarantine handling for infected files
    """

    @staticmethod
    async def scan_file(file_data: bytes) -> Dict[str, Any]:
        """
        Scan file data for viruses using ClamAV.

        If VIRUS_SCAN_ENABLED is False, returns SKIPPED status immediately.
        If clamd is unreachable, returns ERROR status with details.

        Returns:
            Dict with status (clean/infected/error/skipped), engine_version,
            scan_time_ms, and optional threat_name.
        """
        if not VIRUS_SCAN_ENABLED:
            return {
                "status": VirusScanStatus.SKIPPED.value,
                "engine": "clamav",
                "version": "not_configured",
                "scan_time_ms": 0,
                "threat": None,
                "details": "Virus scanning is disabled. Set VIRUS_SCAN_ENABLED=true to activate.",
            }

        start_time = datetime.now(timezone.utc)

        try:
            # Attempt connection to ClamAV daemon
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(CLAMAV_HOST, CLAMAV_PORT),
                timeout=CLAMAV_TIMEOUT_SECONDS,
            )

            # Send PING to verify connection
            writer.write(b"zPING\x00")
            await writer.drain()
            pong = await asyncio.wait_for(reader.read(1024), timeout=5)
            if b"PONG" not in pong:
                return VirusScanningService._error_result("ClamAV did not respond to PING")

            # INSTREAM scan: send file data in chunks
            chunk_size = 8192
            total = len(file_data)
            writer.write(b"zINSTREAM\x00")

            for offset in range(0, total, chunk_size):
                chunk = file_data[offset:offset + chunk_size]
                size_prefix = len(chunk).to_bytes(4, "big")
                writer.write(size_prefix + chunk)
                await writer.drain()

            # Terminate stream with zero-length chunk
            writer.write(b"\x00\x00\x00\x00")
            await writer.drain()

            # Read scan result
            result = await asyncio.wait_for(reader.read(4096), timeout=CLAMAV_TIMEOUT_SECONDS)
            writer.close()
            await writer.wait_closed()

            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            result_str = result.decode("utf-8", errors="replace").strip()

            if "OK" in result_str and "FOUND" not in result_str:
                return {
                    "status": VirusScanStatus.CLEAN.value,
                    "engine": "clamav",
                    "version": "unknown",
                    "scan_time_ms": elapsed,
                    "threat": None,
                    "details": result_str,
                }

            if "FOUND" in result_str:
                # Extract threat name from "stream: <THREAT> FOUND"
                threat = result_str.split("FOUND")[0].split(":")[-1].strip() if ":" in result_str else "unknown"
                return {
                    "status": VirusScanStatus.INFECTED.value,
                    "engine": "clamav",
                    "version": "unknown",
                    "scan_time_ms": elapsed,
                    "threat": threat,
                    "details": result_str,
                }

            return {
                "status": VirusScanStatus.ERROR.value,
                "engine": "clamav",
                "version": "unknown",
                "scan_time_ms": elapsed,
                "threat": None,
                "details": f"Unexpected response: {result_str}",
            }

        except asyncio.TimeoutError:
            return VirusScanningService._error_result(
                f"ClamAV connection timed out after {CLAMAV_TIMEOUT_SECONDS}s"
            )
        except ConnectionRefusedError:
            return VirusScanningService._error_result(
                f"ClamAV refused connection at {CLAMAV_HOST}:{CLAMAV_PORT}"
            )
        except Exception as exc:
            return VirusScanningService._error_result(str(exc))

    @staticmethod
    def _error_result(details: str) -> Dict[str, Any]:
        """Return a standardized error result dict."""
        return {
            "status": VirusScanStatus.ERROR.value,
            "engine": "clamav",
            "version": "unavailable",
            "scan_time_ms": 0,
            "threat": None,
            "details": details,
        }

    @staticmethod
    async def update_media_scan_status(
        db: AsyncSession,
        media_id: str,
        scan_result: Dict[str, Any],
    ) -> None:
        """Update the virus_scan_status field on a media asset after scanning."""
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.id == media_id)
        )
        media = result.scalar_one_or_none()
        if not media:
            return

        media.virus_scan_status = scan_result.get("status", VirusScanStatus.ERROR.value)
        # Store scan result details in metadata
        meta = dict(media.metadata_ or {})
        meta["virus_scan"] = {
            "status": scan_result.get("status"),
            "engine": scan_result.get("engine"),
            "scan_time_ms": scan_result.get("scan_time_ms"),
            "threat": scan_result.get("threat"),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "details": scan_result.get("details"),
        }
        media.metadata_ = meta
        await db.commit()

    @staticmethod
    async def handle_infected_file(
        db: AsyncSession,
        media: MediaAsset,
    ) -> None:
        """
        Quarantine an infected file by deleting it from storage.

        FUTURE: Instead of deletion, move to a quarantine bucket/prefix.
        """
        await StorageService.delete_media_file(media)
        media.status = MediaStatus.ERROR
        media.virus_scan_status = VirusScanStatus.INFECTED.value
        await db.commit()


# ===========================================================================
# SignedURLService
# ===========================================================================


class SignedURLService:
    """
    Generates time-limited signed URLs for secure media access.

    Uses JWT-style HMAC signatures to create tamper-proof URLs that expire
    after a configurable duration. This ensures media files are only
    accessible to authorized users with valid short-lived links.
    """

    @staticmethod
    def _signing_secret() -> str:
        """Get the URL signing secret from application settings."""
        return getattr(settings, "SECRET_KEY", "media-url-signing-key")

    @staticmethod
    def generate_signed_url(
        media_id: str,
        filename: str,
        variant: Optional[str] = None,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
    ) -> str:
        """
        Generate a signed download URL for a media asset.

        Args:
            media_id: Media asset UUID.
            filename: Original filename.
            variant: Optional variant type (thumbnail/small/medium/large).
            expiry_seconds: URL validity duration.

        Returns:
            Signed URL string.
        """
        import base64
        import hmac

        expires = int(datetime.now(timezone.utc).timestamp()) + expiry_seconds
        payload = f"{media_id}:{filename}:{variant or 'original'}:{expires}"
        secret = SignedURLService._signing_secret().encode()
        sig = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
        token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()

        base = getattr(settings, "CDN_URL", "")
        if not base:
            base = "/media"
        return f"{base}/signed/{token}"

    @staticmethod
    def verify_signed_url(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a signed URL token.

        Args:
            token: Base64-encoded signed token.

        Returns:
            Dict with media_id, filename, variant, expires if valid, else None.
        """
        import base64
        import hmac

        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            parts = decoded.rsplit(":", 1)
            if len(parts) != 2:
                return None
            payload, received_sig = parts
            media_id, filename, variant, expires_str = payload.rsplit(":", 3)
            expires = int(expires_str)

            if datetime.now(timezone.utc).timestamp() > expires:
                return None

            secret = SignedURLService._signing_secret().encode()
            expected_sig = hmac.new(
                secret, payload.encode(), hashlib.sha256
            ).hexdigest()[:16]
            if not hmac.compare_digest(expected_sig, received_sig):
                return None

            return {
                "media_id": media_id,
                "filename": filename,
                "variant": variant if variant != "original" else None,
                "expires": expires,
            }
        except Exception:
            return None

    @staticmethod
    def generate_access_url(
        media: MediaAsset,
        variant: Optional[str] = None,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
        force_signed: bool = False,
    ) -> str:
        """
        Generate a public access URL for a media asset.

        URL resolution order:
        1. S3_PUBLIC_URL (custom CDN domain per provider) - if configured
        2. CDN_URL (global CDN) - if configured
        3. Signed URL (time-limited, HMAC) - fallback for private access
           or when force_signed=True

        Args:
            media: MediaAsset record.
            variant: Optional variant type (thumbnail/small/medium/large/webp).
            expiry_seconds: Signed URL expiry when falling back.
            force_signed: Always return a signed URL (for private files).

        Returns:
            Accessible URL string.
        """
        if force_signed or media.storage_provider == StorageProvider.LOCAL:
            return SignedURLService.generate_signed_url(
                media.id, media.original_filename, variant, expiry_seconds
            )

        # Build a prioritized list of CDN/public URL prefixes
        url_prefixes: List[str] = []

        # 1. Provider-specific public URL (e.g. R2 public URL / custom domain)
        if media.storage_provider in (StorageProvider.S3, StorageProvider.R2):
            provider_name = media.storage_provider.value.upper()
            public_url = getattr(settings, f"{provider_name}_PUBLIC_URL", "")
            if public_url:
                url_prefixes.append(public_url.rstrip("/"))

        # 2. Global CDN URL
        cdn_url = getattr(settings, "CDN_URL", "")
        if cdn_url:
            url_prefixes.append(cdn_url.rstrip("/"))

        # If any CDN/public URL is available, construct the public URL
        if url_prefixes:
            prefix = url_prefixes[0]
            if variant:
                # Try to find the matching variant record
                variant_record = next(
                    (v for v in (media.variants or []) if v.variant_type.value == variant),
                    None,
                )
                if variant_record:
                    return f"{prefix}/{variant_record.file_path}"
            # Fallback to original file
            return f"{prefix}/{media.storage_key or media.file_path}"

        # No CDN/public URL configured - use signed URL
        return SignedURLService.generate_signed_url(
            media.id, media.original_filename, variant, expiry_seconds
        )

    @staticmethod
    async def generate_presigned_download_url(
        media: MediaAsset,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
    ) -> str:
        """
        Generate a time-limited presigned S3 download URL (boto3 style).

        Uses aiobotocore to create a presigned GET URL for the stored object.
        Falls back to HMAC signed URL if S3 credentials are unavailable.

        Args:
            media: MediaAsset record.
            expiry_seconds: URL expiry in seconds.

        Returns:
            Presigned S3 URL or HMAC signed URL.
        """
        if media.storage_provider == StorageProvider.LOCAL:
            return SignedURLService.generate_signed_url(
                media.id, media.original_filename, None, expiry_seconds
            )

        import aiobotocore.session

        provider = media.storage_provider.value
        cfg = StorageService._get_provider_config(provider)
        endpoint, region, access_key, secret_key, bucket = (
            cfg["endpoint"], cfg["region"], cfg["access_key"], cfg["secret_key"], cfg["bucket"]
        )

        if not all([endpoint, access_key, secret_key]):
            return SignedURLService.generate_signed_url(
                media.id, media.original_filename, None, expiry_seconds
            )

        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        ) as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": media.storage_key or media.file_path,
                    "ResponseContentDisposition": (
                        f'attachment; filename="{media.original_filename}"'
                    ),
                },
                ExpiresIn=expiry_seconds,
            )
            return url


# ===========================================================================
# MediaOrganizerService
# ===========================================================================


class MediaOrganizerService:
    """
    Manages media organization: collections, tagging, search/filter, and bulk operations.
    """

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    @staticmethod
    async def create_collection(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int],
        data: MediaCollectionCreate,
    ) -> MediaCollection:
        """Create a new media collection."""
        collection = MediaCollection(
            company_id=company_id,
            branch_id=branch_id,
            name=data.name,
            description=data.description,
            cover_media_id=data.cover_media_id,
            item_count=0,
        )
        db.add(collection)
        await db.commit()
        await db.refresh(collection)
        return collection

    @staticmethod
    async def list_collections(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        search: Optional[str] = None,
    ) -> Tuple[List[MediaCollection], int]:
        """List media collections with optional search."""
        query = select(MediaCollection).where(
            MediaCollection.company_id == company_id
        )
        if branch_id is not None:
            query = query.where(MediaCollection.branch_id == branch_id)
        if search:
            query = query.where(
                MediaCollection.name.ilike(f"%{search}%")
            )

        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(desc(MediaCollection.updated_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        collections = result.scalars().all()
        return list(collections), total

    @staticmethod
    async def get_collection(
        db: AsyncSession,
        collection_id: int,
        company_id: int,
    ) -> MediaCollection:
        """Get a collection by ID with items loaded."""
        result = await db.execute(
            select(MediaCollection)
            .where(
                MediaCollection.id == collection_id,
                MediaCollection.company_id == company_id,
            )
            .options(selectinload(MediaCollection.items))
        )
        collection = result.scalar_one_or_none()
        if not collection:
            raise NotFoundError(f"Collection {collection_id} not found")
        return collection

    @staticmethod
    async def update_collection(
        db: AsyncSession,
        collection_id: int,
        company_id: int,
        data: MediaCollectionUpdate,
    ) -> MediaCollection:
        """Update a collection."""
        collection = await MediaOrganizerService.get_collection(
            db, collection_id, company_id
        )
        if data.name is not None:
            collection.name = data.name
        if data.description is not None:
            collection.description = data.description
        if data.cover_media_id is not None:
            collection.cover_media_id = data.cover_media_id
        await db.commit()
        await db.refresh(collection)
        return collection

    @staticmethod
    async def delete_collection(
        db: AsyncSession,
        collection_id: int,
        company_id: int,
    ) -> None:
        """Delete a collection and all its items."""
        collection = await MediaOrganizerService.get_collection(
            db, collection_id, company_id
        )
        await db.delete(collection)
        await db.commit()

    @staticmethod
    async def add_items_to_collection(
        db: AsyncSession,
        collection_id: int,
        company_id: int,
        media_ids: List[str],
        order_index: Optional[int] = None,
    ) -> MediaCollection:
        """Add media items to a collection."""
        collection = await MediaOrganizerService.get_collection(
            db, collection_id, company_id
        )

        if order_index is None:
            order_index = len(collection.items)

        for idx, media_id in enumerate(media_ids):
            existing = next(
                (i for i in collection.items if i.media_id == media_id), None
            )
            if existing:
                continue
            item = MediaCollectionItem(
                collection_id=collection_id,
                media_id=media_id,
                order_index=order_index + idx,
            )
            db.add(item)

        collection.item_count = len(collection.items) + len(media_ids)
        await db.commit()
        await db.refresh(collection)
        return collection

    @staticmethod
    async def remove_item_from_collection(
        db: AsyncSession,
        collection_id: int,
        media_id: str,
        company_id: int,
    ) -> MediaCollection:
        """Remove a media item from a collection."""
        collection = await MediaOrganizerService.get_collection(
            db, collection_id, company_id
        )

        item_to_remove = next(
            (i for i in collection.items if i.media_id == media_id), None
        )
        if item_to_remove:
            await db.delete(item_to_remove)
            collection.item_count = max(0, collection.item_count - 1)
            await db.commit()
            await db.refresh(collection)
        return collection

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    @staticmethod
    async def create_tag(
        db: AsyncSession,
        company_id: int,
        data: MediaTagCreate,
    ) -> MediaTag:
        """Create a new media tag."""
        existing = await db.execute(
            select(MediaTag).where(
                MediaTag.company_id == company_id,
                MediaTag.name == data.name,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(f"Tag '{data.name}' already exists")

        tag = MediaTag(
            company_id=company_id,
            name=data.name,
            color=data.color,
        )
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag

    @staticmethod
    async def list_tags(
        db: AsyncSession,
        company_id: int,
    ) -> List[MediaTag]:
        """List all tags for a company."""
        result = await db.execute(
            select(MediaTag)
            .where(MediaTag.company_id == company_id)
            .order_by(MediaTag.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_tag(db: AsyncSession, tag_id: int, company_id: int) -> None:
        """Delete a tag and all its mappings."""
        result = await db.execute(
            select(MediaTag).where(
                MediaTag.id == tag_id,
                MediaTag.company_id == company_id,
            )
        )
        tag = result.scalar_one_or_none()
        if not tag:
            raise NotFoundError(f"Tag {tag_id} not found")
        await db.delete(tag)
        await db.commit()

    @staticmethod
    async def add_tags_to_media(
        db: AsyncSession,
        media_id: str,
        company_id: int,
        tag_ids: List[int],
    ) -> MediaAsset:
        """Add tags to a media asset."""
        result = await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == media_id,
                MediaAsset.company_id == company_id,
            )
        )
        media = result.scalar_one_or_none()
        if not media:
            raise NotFoundError(f"Media {media_id} not found")

        for tag_id in tag_ids:
            existing = await db.execute(
                select(MediaTagMapping).where(
                    MediaTagMapping.media_id == media_id,
                    MediaTagMapping.tag_id == tag_id,
                )
            )
            if existing.scalar_one_or_none():
                continue
            mapping = MediaTagMapping(media_id=media_id, tag_id=tag_id)
            db.add(mapping)

        await db.commit()
        await db.refresh(media)
        return media

    @staticmethod
    async def remove_tag_from_media(
        db: AsyncSession,
        media_id: str,
        tag_id: int,
        company_id: int,
    ) -> MediaAsset:
        """Remove a tag from a media asset."""
        result = await db.execute(
            select(MediaAsset).where(
                MediaAsset.id == media_id,
                MediaAsset.company_id == company_id,
            )
        )
        media = result.scalar_one_or_none()
        if not media:
            raise NotFoundError(f"Media {media_id} not found")

        await db.execute(
            delete(MediaTagMapping).where(
                MediaTagMapping.media_id == media_id,
                MediaTagMapping.tag_id == tag_id,
            )
        )
        await db.commit()
        await db.refresh(media)
        return media

    # ------------------------------------------------------------------
    # Search / Filter
    # ------------------------------------------------------------------

    @staticmethod
    async def search_media(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[int]] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Tuple[List[MediaAsset], int]:
        """
        Search and filter media assets with pagination.

        Args:
            db: Async database session.
            company_id: Tenant company ID.
            branch_id: Optional branch filter.
            category: Filter by 'image', 'video', 'document'.
            status: Filter by processing status.
            tags: Filter by tag IDs (assets must have ALL specified tags).
            search: Full-text search in filename.
            date_from: Uploaded on or after.
            date_to: Uploaded on or before.
            sort_by: Sort field name.
            sort_order: 'asc' or 'desc'.
            page: Page number (1-based).
            page_size: Items per page.

        Returns:
            Tuple of (list of MediaAsset, total count).
        """
        query = select(MediaAsset).where(MediaAsset.company_id == company_id)

        if branch_id is not None:
            query = query.where(
                or_(
                    MediaAsset.branch_id == branch_id,
                    MediaAsset.branch_id.is_(None),
                )
            )
        if category:
            query = query.where(MediaAsset.category == category)
        if status:
            query = query.where(MediaAsset.status == status)
        if search:
            query = query.where(
                or_(
                    MediaAsset.original_filename.ilike(f"%{search}%"),
                    MediaAsset.filename.ilike(f"%{search}%"),
                )
            )
        if date_from:
            query = query.where(MediaAsset.created_at >= date_from)
        if date_to:
            query = query.where(MediaAsset.created_at <= date_to)

        # Tag filtering: assets that have ALL specified tags
        if tags:
            for tag_id in tags:
                subq = (
                    select(MediaTagMapping.media_id)
                    .where(MediaTagMapping.tag_id == tag_id)
                    .scalar_subquery()
                )
                query = query.where(MediaAsset.id.in_(subq))

        # Count total
        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Sorting
        sort_column = getattr(MediaAsset, sort_by, MediaAsset.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Pagination
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    @staticmethod
    async def bulk_delete(
        db: AsyncSession,
        media_ids: List[str],
        company_id: int,
    ) -> Tuple[int, List[Dict[str, str]]]:
        """
        Delete multiple media assets and their stored files.

        Returns:
            Tuple of (success_count, list of error dicts).
        """
        errors: List[Dict[str, str]] = []
        success_count = 0
        storage = StorageService()

        for media_id in media_ids:
            try:
                result = await db.execute(
                    select(MediaAsset).where(
                        MediaAsset.id == media_id,
                        MediaAsset.company_id == company_id,
                    )
                )
                media = result.scalar_one_or_none()
                if not media:
                    errors.append(
                        {"id": media_id, "error": "Not found or access denied"}
                    )
                    continue

                # Delete stored file
                await StorageService.delete_media_file(media)

                # Delete variants
                for variant in media.variants or []:
                    if media.storage_provider == StorageProvider.LOCAL:
                        await storage._delete_local(variant.file_path)
                    else:
                        await storage._delete_remote(
                            variant.file_path, media.storage_provider.value
                        )

                await db.delete(media)
                success_count += 1
            except Exception as exc:
                errors.append({"id": media_id, "error": str(exc)})

        if success_count > 0:
            await db.commit()
        return success_count, errors

    @staticmethod
    async def bulk_tag(
        db: AsyncSession,
        media_ids: List[str],
        tag_ids: List[int],
        company_id: int,
    ) -> Tuple[int, List[Dict[str, str]]]:
        """
        Apply tags to multiple media assets.

        Returns:
            Tuple of (success_count, list of error dicts).
        """
        errors: List[Dict[str, str]] = []
        success_count = 0

        for media_id in media_ids:
            try:
                await MediaOrganizerService.add_tags_to_media(
                    db, media_id, company_id, tag_ids
                )
                success_count += 1
            except Exception as exc:
                errors.append({"id": media_id, "error": str(exc)})

        return success_count, errors

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @staticmethod
    async def get_media_stats(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive media usage statistics."""
        base_filter = [MediaAsset.company_id == company_id]
        if branch_id is not None:
            base_filter.append(
                or_(
                    MediaAsset.branch_id == branch_id,
                    MediaAsset.branch_id.is_(None),
                )
            )

        # Total assets and size
        total_result = await db.execute(
            select(func.count(), func.coalesce(func.sum(MediaAsset.file_size), 0)).where(
                *base_filter
            )
        )
        total_assets, total_size = total_result.one() or (0, 0)

        # By category
        cat_result = await db.execute(
            select(MediaAsset.category, func.count())
            .where(*base_filter)
            .group_by(MediaAsset.category)
        )
        category_counts = {row[0]: row[1] for row in cat_result.all()}

        # By status
        status_result = await db.execute(
            select(MediaAsset.status, func.count())
            .where(*base_filter)
            .group_by(MediaAsset.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}

        # Analytics totals
        views_result = await db.execute(
            select(
                func.coalesce(func.sum(MediaAnalytics.views), 0),
                func.coalesce(func.sum(MediaAnalytics.downloads), 0),
            ).where(MediaAnalytics.media_id.in_(
                select(MediaAsset.id).where(*base_filter)
            ))
        )
        views_row = views_result.one()
        total_views = views_row[0] if views_row else 0
        total_downloads = views_row[1] if views_row else 0

        # Collection count
        col_result = await db.execute(
            select(func.count()).where(MediaCollection.company_id == company_id)
        )
        collection_count = col_result.scalar() or 0

        # Tag count
        tag_result = await db.execute(
            select(func.count()).where(MediaTag.company_id == company_id)
        )
        tag_count = tag_result.scalar() or 0

        # Storage by provider
        storage_result = await db.execute(
            select(MediaAsset.storage_provider, func.count())
            .where(*base_filter)
            .group_by(MediaAsset.storage_provider)
        )
        storage_by_provider = {
            row[0].value if hasattr(row[0], "value") else str(row[0]): row[1]
            for row in storage_result.all()
        }

        # Virus scan status summary
        scan_result = await db.execute(
            select(MediaAsset.virus_scan_status, func.count())
            .where(*base_filter)
            .group_by(MediaAsset.virus_scan_status)
        )
        virus_scan_summary = {row[0]: row[1] for row in scan_result.all()}

        return {
            "total_assets": total_assets,
            "total_size": total_size,
            "image_count": category_counts.get("image", 0),
            "video_count": category_counts.get("video", 0),
            "document_count": category_counts.get("document", 0),
            "processing_count": status_counts.get("processing", 0),
            "error_count": status_counts.get("error", 0),
            "total_views": total_views,
            "total_downloads": total_downloads,
            "collection_count": collection_count,
            "tag_count": tag_count,
            "storage_by_provider": storage_by_provider,
            "virus_scan_summary": virus_scan_summary,
        }


# ===========================================================================
# AIImageAnalysisService - OpenAI Vision Integration
# ===========================================================================

import logging

logger = logging.getLogger(__name__)


class AIImageAnalysisService:
    """
    Integrates OpenAI Vision API for automated image analysis.

    Supports:
    - Caption generation (brand-aware, platform-specific)
    - Hashtag suggestions (brand-aligned, filtered)
    - Creative scoring (composition, lighting, color, sharpness, relevance)
    - Object/brand/text detection
    - Brand alignment analysis
    - Instagram/Facebook/TikTok optimization
    - Creative auditing and fatigue detection

    Results are cached per media asset to avoid redundant API calls.
    Brand identity is automatically applied when available.
    """

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    @staticmethod
    async def analyze_media(
        db: AsyncSession,
        media: MediaAsset,
        analysis_type: AnalysisType,
        force_refresh: bool = False,
        branch_id: Optional[int] = None,
        platform: Optional[str] = None,
        language: Optional[str] = None,
        max_chars: Optional[int] = None,
    ) -> AIImageAnalysis:
        """
        Run AI analysis on a media asset with optional brand identity awareness.

        Args:
            db: Async database session.
            media: Target MediaAsset (must be an image).
            analysis_type: Type of analysis to perform.
            force_refresh: Re-run even if cached results exist.
            branch_id: Optional branch ID for brand-aware analysis.
            platform: Target platform for platform-specific analysis.
            language: Output language override.
            max_chars: Maximum characters for caption generation.

        Returns:
            AIImageAnalysis record with results.

        Raises:
            ValidationError: If media is not an image.
            NotFoundError: If media file cannot be read.
        """
        if media.category != "image":
            raise ValidationError(
                detail="AI analysis is only supported for image files"
            )

        # Check for cached result
        if not force_refresh:
            existing = await db.execute(
                select(AIImageAnalysis).where(
                    AIImageAnalysis.media_id == media.id,
                    AIImageAnalysis.analysis_type == analysis_type,
                )
            )
            cached = existing.scalar_one_or_none()
            if cached:
                return cached

        # Read image data from the correct storage backend
        storage = StorageService()
        image_data = await storage.read_media_file(media)

        if not image_data:
            raise NotFoundError(detail="Media file not available for analysis")

        image_b64 = base64.b64encode(image_data).decode("utf-8")
        mime_prefix = media.mime_type if media.mime_type else "image/jpeg"
        data_url = f"data:{mime_prefix};base64,{image_b64}"

        # Load brand identity if branch_id is provided
        brand_identity = None
        brand_identity_applied = False
        if branch_id:
            brand_identity = await CreativeStudioService.get_brand_identity(
                db, branch_id, media.company_id
            )

        # Call OpenAI API
        result_json, confidence, model_used = await AIImageAnalysisService._call_openai_vision(
            data_url=data_url,
            analysis_type=analysis_type,
            brand_identity=brand_identity,
            platform=platform,
            language=language,
            max_chars=max_chars,
        )

        brand_identity_applied = brand_identity is not None and analysis_type in (
            AnalysisType.CAPTION, AnalysisType.HASHTAG, AnalysisType.BRAND_ALIGNMENT
        )

        # Upsert analysis record
        existing = await db.execute(
            select(AIImageAnalysis).where(
                AIImageAnalysis.media_id == media.id,
                AIImageAnalysis.analysis_type == analysis_type,
            )
        )
        record = existing.scalar_one_or_none()
        if record:
            record.result = result_json
            record.confidence = confidence
            record.model_used = model_used
            record.branch_id = branch_id
            record.brand_identity_applied = brand_identity_applied
        else:
            record = AIImageAnalysis(
                media_id=media.id,
                company_id=media.company_id,
                branch_id=branch_id,
                analysis_type=analysis_type,
                result=result_json,
                confidence=confidence,
                model_used=model_used,
                brand_identity_applied=brand_identity_applied,
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def _call_openai_vision(
        data_url: str,
        analysis_type: AnalysisType,
        brand_identity: Optional[BranchBrandIdentity] = None,
        platform: Optional[str] = None,
        language: Optional[str] = None,
        max_chars: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Optional[float], str]:
        """
        Call OpenAI Vision API for image analysis.

        Args:
            data_url: Base64 data URL of the image.
            analysis_type: Type of analysis requested.
            brand_identity: Optional brand identity for brand-aware analysis.
            platform: Target platform for platform-specific prompts.
            language: Output language.
            max_chars: Max characters for caption.

        Returns:
            Tuple of (result_dict, confidence_score, model_name).

        Raises:
            RuntimeError: If API call fails or response cannot be parsed.
        """
        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        model = AI_ANALYSIS_VISION_MODEL
        base_prompt = AI_ANALYSIS_PROMPTS.get(analysis_type, "Analyze this image.")

        # Build brand-aware or platform-aware prompt
        prompt = AIImageAnalysisService._build_prompt(
            base_prompt=base_prompt,
            analysis_type=analysis_type,
            brand_identity=brand_identity,
            platform=platform,
            language=language,
            max_chars=max_chars,
        )

        # Determine detail level
        detail = AI_ANALYSIS_DETAIL_LEVEL
        if analysis_type == AnalysisType.OBJECTS:
            detail = "high"
        elif analysis_type == AnalysisType.HASHTAG:
            detail = "low"

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                                "detail": detail,
                            },
                        },
                    ],
                }
            ],
            "max_tokens": AI_ANALYSIS_MAX_TOKENS,
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=AI_ANALYSIS_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("OpenAI Vision API HTTP error: %s", exc.response.text)
            raise RuntimeError(f"OpenAI API error: {exc.response.status_code}") from exc
        except Exception as exc:
            logger.error("OpenAI Vision API error: %s", str(exc))
            raise RuntimeError(f"OpenAI API call failed: {str(exc)}") from exc

        content = data["choices"][0]["message"]["content"]

        # Parse result based on analysis type
        result = AIImageAnalysisService._parse_analysis_result(
            content, analysis_type
        )
        confidence = AIImageAnalysisService._extract_confidence(data)

        return result, confidence, model

    @staticmethod
    def _build_prompt(
        base_prompt: str,
        analysis_type: AnalysisType,
        brand_identity: Optional[BranchBrandIdentity] = None,
        platform: Optional[str] = None,
        language: Optional[str] = None,
        max_chars: Optional[int] = None,
    ) -> str:
        """Build the final prompt with brand identity and platform context."""
        prompt = base_prompt

        # Add brand identity context
        if brand_identity and analysis_type in (
            AnalysisType.CAPTION, AnalysisType.HASHTAG, AnalysisType.BRAND_ALIGNMENT
        ):
            colors = [brand_identity.primary_color]
            if brand_identity.secondary_color:
                colors.append(brand_identity.secondary_color)
            if brand_identity.accent_color:
                colors.append(brand_identity.accent_color)

            if analysis_type == AnalysisType.CAPTION:
                prompt = BRAND_AWARE_CAPTION_PROMPT.format(
                    platform=platform or "Instagram",
                    brand_name=brand_identity.brand_name,
                    brand_tone=brand_identity.brand_tone.value,
                    brand_colors=", ".join(colors),
                    target_audience=brand_identity.target_audience or "Genel",
                    language=language or brand_identity.language,
                    max_chars=max_chars or 2200,
                )
            elif analysis_type == AnalysisType.HASHTAG:
                prompt = BRAND_AWARE_HASHTAG_PROMPT.format(
                    brand_name=brand_identity.brand_name,
                    industry=brand_identity.industry or "general",
                    brand_tone=brand_identity.brand_tone.value,
                    target_audience=brand_identity.target_audience or "Genel",
                    language=language or brand_identity.language,
                )
                # Add always-include and never-include rules
                if brand_identity.hashtags_always_include:
                    prompt += f"\n\nALWAYS include these hashtags: {', '.join(brand_identity.hashtags_always_include)}"
                if brand_identity.hashtags_never_include:
                    prompt += f"\n\nNEVER include these hashtags: {', '.join(brand_identity.hashtags_never_include)}"
            elif analysis_type == AnalysisType.BRAND_ALIGNMENT:
                prompt += (
                    f"\n\nBrand Identity Context:\n"
                    f"- Brand Name: {brand_identity.brand_name}\n"
                    f"- Primary Color: {brand_identity.primary_color}\n"
                    f"- Secondary Color: {brand_identity.secondary_color or 'N/A'}\n"
                    f"- Accent Color: {brand_identity.accent_color or 'N/A'}\n"
                    f"- Brand Tone: {brand_identity.brand_tone.value}\n"
                    f"- Visual Style: {brand_identity.visual_style or 'N/A'}\n"
                    f"- Target Audience: {brand_identity.target_audience or 'N/A'}\n"
                    f"- Industry: {brand_identity.industry or 'N/A'}"
                )

        # Add platform context for Instagram optimization
        if analysis_type == AnalysisType.INSTAGRAM_OPTIMIZE and platform:
            prompt += f"\n\nTarget platform: {platform}"

        # Add language instruction
        if language:
            prompt += f"\n\nRespond in {language} language."

        return prompt

    @staticmethod
    def _parse_analysis_result(
        content: str, analysis_type: AnalysisType
    ) -> Dict[str, Any]:
        """Parse the raw OpenAI response into structured JSON."""
        content = content.strip()

        # Helper to extract JSON from markdown code blocks
        def _extract_json(text: str) -> Optional[Dict[str, Any]]:
            try:
                if "```json" in text:
                    json_str = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    json_str = text.split("```")[1].split("```")[0].strip()
                else:
                    json_str = text
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                return None

        if analysis_type == AnalysisType.SCORE:
            parsed = _extract_json(content)
            if parsed and isinstance(parsed, dict):
                # Normalize to 1-10 scale if needed
                for key in ["composition", "lighting", "color", "sharpness", "relevance", "overall"]:
                    if key in parsed and isinstance(parsed[key], (int, float)):
                        if parsed[key] > 10:  # Convert from 1-100 to 1-10
                            parsed[key] = round(parsed[key] / 10, 1)
                return parsed
            return {
                "composition": 5.0,
                "lighting": 5.0,
                "color": 5.0,
                "sharpness": 5.0,
                "relevance": 5.0,
                "overall": 5.0,
                "explanation": content[:500],
            }

        elif analysis_type == AnalysisType.OBJECTS:
            parsed = _extract_json(content)
            if parsed:
                if isinstance(parsed, list):
                    return {"objects": parsed, "scene_description": ""}
                return parsed
            return {"objects": [{"label": content[:100], "confidence": 0.5}], "scene_description": content[:200]}

        elif analysis_type == AnalysisType.CAPTION:
            return {"caption": content, "platform": "general"}

        elif analysis_type == AnalysisType.HASHTAG:
            hashtags = [h.strip() for h in content.split(",") if h.strip()]
            return {"hashtags": hashtags, "count": len(hashtags)}

        elif analysis_type in (
            AnalysisType.BRAND_ALIGNMENT,
            AnalysisType.INSTAGRAM_OPTIMIZE,
            AnalysisType.CREATIVE_AUDIT,
        ):
            parsed = _extract_json(content)
            if parsed and isinstance(parsed, dict):
                return parsed
            # Fallback: wrap raw content
            return {"result": content[:1000], "raw": True}

        return {"result": content}

    @staticmethod
    def _extract_confidence(response_data: Dict[str, Any]) -> Optional[float]:
        """Extract confidence score from OpenAI response."""
        usage = response_data.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        if total_tokens > 0:
            # Higher token usage for complex analyses indicates more processing
            # Normalize to 0-1 range
            return round(min(1.0, max(0.5, 1.0 - (total_tokens / 4000))), 3)
        return None

    @staticmethod
    async def get_analysis_results(
        db: AsyncSession,
        media_id: str,
        company_id: int,
    ) -> List[AIImageAnalysis]:
        """Get all AI analysis results for a media asset."""
        result = await db.execute(
            select(AIImageAnalysis)
            .where(
                AIImageAnalysis.media_id == media_id,
                AIImageAnalysis.company_id == company_id,
            )
            .order_by(AIImageAnalysis.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def run_full_analysis(
        db: AsyncSession,
        media: MediaAsset,
        branch_id: Optional[int] = None,
        platform: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, AIImageAnalysis]:
        """
        Run all analysis types on a media asset.

        Args:
            db: Async database session.
            media: Target MediaAsset.
            branch_id: Optional branch for brand-aware analysis.
            platform: Target platform.
            language: Output language.

        Returns:
            Dict mapping analysis type names to AIImageAnalysis records.
        """
        results: Dict[str, AIImageAnalysis] = {}
        analysis_types = [
            AnalysisType.CAPTION,
            AnalysisType.HASHTAG,
            AnalysisType.SCORE,
            AnalysisType.OBJECTS,
        ]

        for atype in analysis_types:
            try:
                analysis = await AIImageAnalysisService.analyze_media(
                    db=db,
                    media=media,
                    analysis_type=atype,
                    branch_id=branch_id,
                    platform=platform,
                    language=language,
                )
                results[atype.value] = analysis
            except Exception as exc:
                logger.warning("Analysis %s failed for media %s: %s", atype.value, media.id, str(exc))
                results[atype.value] = None  # type: ignore[assignment]

        return results


# ===========================================================================
# CreativeStudioService - Brand Identity, Audit, Fatigue Detection
# ===========================================================================


class CreativeStudioService:
    """
    Advanced creative studio service for brand identity management,
    creative auditing, fatigue detection, and portfolio analysis.

    Provides:
    - Branch brand identity CRUD
    - Creative audit with fatigue detection
    - Portfolio-wide creative health analysis
    - Similarity detection across media assets
    """

    # ------------------------------------------------------------------
    # Brand Identity Management
    # ------------------------------------------------------------------

    @staticmethod
    async def create_brand_identity(
        db: AsyncSession,
        company_id: int,
        branch_id: int,
        data: BrandIdentityCreate,
    ) -> BranchBrandIdentity:
        """Create a new brand identity for a branch."""
        # Check if identity already exists for this branch
        existing = await db.execute(
            select(BranchBrandIdentity).where(
                BranchBrandIdentity.branch_id == branch_id,
                BranchBrandIdentity.company_id == company_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                f"Brand identity already exists for branch {branch_id}. Use update instead."
            )

        identity = BranchBrandIdentity(
            branch_id=branch_id,
            company_id=company_id,
            brand_name=data.brand_name,
            primary_color=data.primary_color,
            secondary_color=data.secondary_color,
            accent_color=data.accent_color,
            brand_tone=BrandTone(data.brand_tone),
            target_audience=data.target_audience,
            industry=data.industry,
            language=data.language,
            font_style=data.font_style,
            visual_style=data.visual_style,
            hashtags_always_include=data.hashtags_always_include,
            hashtags_never_include=data.hashtags_never_include,
            competitors_to_differentiate=data.competitors_to_differentiate,
            is_active=True,
        )
        db.add(identity)
        await db.commit()
        await db.refresh(identity)
        return identity

    @staticmethod
    async def get_brand_identity(
        db: AsyncSession,
        branch_id: int,
        company_id: int,
    ) -> Optional[BranchBrandIdentity]:
        """Get brand identity for a branch."""
        result = await db.execute(
            select(BranchBrandIdentity).where(
                BranchBrandIdentity.branch_id == branch_id,
                BranchBrandIdentity.company_id == company_id,
                BranchBrandIdentity.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_brand_identity(
        db: AsyncSession,
        company_id: int,
        branch_id: int,
        data: BrandIdentityUpdate,
    ) -> BranchBrandIdentity:
        """Update brand identity for a branch."""
        identity = await CreativeStudioService.get_brand_identity(
            db, branch_id, company_id
        )
        if not identity:
            raise NotFoundError(f"Brand identity for branch {branch_id} not found")

        updateable_fields = [
            "brand_name", "primary_color", "secondary_color", "accent_color",
            "target_audience", "industry", "language", "font_style", "visual_style",
            "hashtags_always_include", "hashtags_never_include",
            "competitors_to_differentiate", "is_active",
        ]
        for field in updateable_fields:
            value = getattr(data, field, None)
            if value is not None:
                setattr(identity, field, value)

        if data.brand_tone is not None:
            identity.brand_tone = BrandTone(data.brand_tone)

        identity.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(identity)
        return identity

    @staticmethod
    async def delete_brand_identity(
        db: AsyncSession,
        company_id: int,
        branch_id: int,
    ) -> None:
        """Delete (deactivate) brand identity for a branch."""
        identity = await CreativeStudioService.get_brand_identity(
            db, branch_id, company_id
        )
        if not identity:
            raise NotFoundError(f"Brand identity for branch {branch_id} not found")
        identity.is_active = False
        await db.commit()

    @staticmethod
    async def list_brand_identities(
        db: AsyncSession,
        company_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[BranchBrandIdentity], int]:
        """List all brand identities for a company."""
        query = select(BranchBrandIdentity).where(
            BranchBrandIdentity.company_id == company_id,
            BranchBrandIdentity.is_active.is_(True),
        )

        count_result = await db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.order_by(BranchBrandIdentity.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        return list(result.scalars().all()), total

    # ------------------------------------------------------------------
    # Creative Audit & Fatigue Detection
    # ------------------------------------------------------------------

    @staticmethod
    async def run_creative_audit(
        db: AsyncSession,
        media: MediaAsset,
        audit_request: Optional[CreativeAuditRequest] = None,
        branch_id: Optional[int] = None,
    ) -> CreativeAudit:
        """
        Run a comprehensive creative audit on a media asset.

        Uses OpenAI Vision for analysis and compares against company history
        for fatigue detection.

        Args:
            db: Async database session.
            media: Target MediaAsset.
            audit_request: Optional audit configuration.
            branch_id: Optional branch ID.

        Returns:
            CreativeAudit record with results.
        """
        audit_request = audit_request or CreativeAuditRequest()

        # Check for cached result
        if not audit_request.force_refresh:
            existing = await db.execute(
                select(CreativeAudit).where(CreativeAudit.media_id == media.id)
            )
            cached = existing.scalar_one_or_none()
            if cached:
                return cached

        # Run AI analysis for creative audit
        analysis = await AIImageAnalysisService.analyze_media(
            db=db,
            media=media,
            analysis_type=AnalysisType.CREATIVE_AUDIT,
            force_refresh=audit_request.force_refresh,
            branch_id=branch_id,
        )

        # Get company history for comparison
        company_history = []
        if audit_request.compare_with_company_history:
            company_history = await CreativeStudioService._get_company_creative_history(
                db, media.company_id, exclude_media_id=media.id
            )

        # Analyze fatigue signals
        fatigue_signals = CreativeStudioService._detect_fatigue_signals(
            analysis.result, company_history
        )

        # Determine fatigue level
        fatigue_level = CreativeStudioService._calculate_fatigue_level(
            fatigue_signals,
            analysis.result.get("originality_score", 5),
        )

        # Find similar creatives
        similar_ids = []
        if audit_request.detect_similarity:
            similar_ids = await CreativeStudioService._find_similar_creatives(
                db, media, company_history
            )

        # Build best practices checklist
        bp_raw = analysis.result.get("best_practices_checklist", {})
        from app.media.schemas import BestPracticesChecklist
        best_practices = BestPracticesChecklist(
            rule_of_thirds=bp_raw.get("rule_of_thirds", False),
            leading_lines=bp_raw.get("leading_lines", False),
            negative_space=bp_raw.get("negative_space", False),
            focal_point=bp_raw.get("focal_point", False),
            color_contrast=bp_raw.get("color_contrast", False),
        )

        # Upsert audit record
        existing = await db.execute(
            select(CreativeAudit).where(CreativeAudit.media_id == media.id)
        )
        record = existing.scalar_one_or_none()

        originality = analysis.result.get("originality_score")
        try:
            originality_int = int(originality) if originality else None
        except (ValueError, TypeError):
            originality_int = None

        if record:
            record.originality_score = originality_int
            record.fatigue_level = fatigue_level
            record.fatigue_signals = fatigue_signals
            record.trend_alignment = analysis.result.get("trend_alignment", {})
            record.competitor_similarity_risk = analysis.result.get(
                "competitor_similarity_risk", "low"
            )
            record.best_practices_checklist = best_practices.model_dump()
            record.refresh_recommendations = analysis.result.get(
                "refresh_recommendations", []
            )
            record.engagement_prediction = analysis.result.get(
                "engagement_prediction", {}
            )
            record.similar_media_ids = similar_ids
        else:
            record = CreativeAudit(
                media_id=media.id,
                company_id=media.company_id,
                branch_id=branch_id,
                originality_score=originality_int,
                fatigue_level=fatigue_level,
                fatigue_signals=fatigue_signals,
                trend_alignment=analysis.result.get("trend_alignment", {}),
                competitor_similarity_risk=analysis.result.get(
                    "competitor_similarity_risk", "low"
                ),
                best_practices_checklist=best_practices.model_dump(),
                refresh_recommendations=analysis.result.get(
                    "refresh_recommendations", []
                ),
                engagement_prediction=analysis.result.get(
                    "engagement_prediction", {}
                ),
                similar_media_ids=similar_ids,
            )
            db.add(record)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def get_portfolio_audit_summary(
        db: AsyncSession,
        company_id: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get a summary of creative health across the entire media portfolio.

        Args:
            db: Async database session.
            company_id: Company ID.
            branch_id: Optional branch filter.

        Returns:
            Dict with portfolio-wide audit summary.
        """
        query = select(CreativeAudit).where(
            CreativeAudit.company_id == company_id
        )
        if branch_id is not None:
            query = query.where(CreativeAudit.branch_id == branch_id)

        result = await db.execute(query)
        audits = list(result.scalars().all())

        if not audits:
            return {
                "total_audited": 0,
                "average_originality": 0.0,
                "fatigue_distribution": {},
                "high_fatigue_count": 0,
                "trend_alignment_pct": 0.0,
                "top_recommendations": [],
                "assets_needing_refresh": [],
            }

        # Calculate metrics
        total = len(audits)
        avg_originality = sum(
            a.originality_score for a in audits if a.originality_score
        ) / total

        fatigue_dist: Dict[str, int] = {}
        high_fatigue = 0
        trend_aligned = 0
        all_recommendations: List[str] = []
        needs_refresh: List[str] = []

        for audit in audits:
            level = audit.fatigue_level.value
            fatigue_dist[level] = fatigue_dist.get(level, 0) + 1

            if audit.fatigue_level in (FatigueLevel.HIGH, FatigueLevel.CRITICAL):
                high_fatigue += 1
                needs_refresh.append(audit.media_id)

            trend = audit.trend_alignment or {}
            if trend.get("is_trending", False):
                trend_aligned += 1

            recs = audit.refresh_recommendations or []
            all_recommendations.extend(recs)

        # Count recommendation frequency and get top 5
        rec_counts: Dict[str, int] = {}
        for rec in all_recommendations:
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        top_recs = sorted(rec_counts.keys(), key=lambda r: rec_counts[r], reverse=True)[:5]

        return {
            "total_audited": total,
            "average_originality": round(avg_originality, 1),
            "fatigue_distribution": fatigue_dist,
            "high_fatigue_count": high_fatigue,
            "trend_alignment_pct": round(trend_aligned / total * 100, 1),
            "top_recommendations": top_recs,
            "assets_needing_refresh": needs_refresh,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_company_creative_history(
        db: AsyncSession,
        company_id: int,
        exclude_media_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MediaAsset]:
        """Get recent media assets for company history comparison."""
        query = select(MediaAsset).where(
            MediaAsset.company_id == company_id,
            MediaAsset.category == "image",
            MediaAsset.status == MediaStatus.READY,
        )
        if exclude_media_id:
            query = query.where(MediaAsset.id != exclude_media_id)

        query = query.order_by(MediaAsset.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _detect_fatigue_signals(
        audit_result: Dict[str, Any],
        company_history: List[MediaAsset],
    ) -> List[str]:
        """Detect creative fatigue signals from audit results."""
        signals: List[str] = []

        # Check for explicit fatigue signals from AI
        ai_signals = audit_result.get("fatigue_signals", [])
        if isinstance(ai_signals, list):
            signals.extend(ai_signals)

        # Check originality score
        originality = audit_result.get("originality_score")
        if originality and isinstance(originality, (int, float)):
            if originality < 4:
                signals.append(f"Very low originality score ({originality}/10)")
            elif originality < 6:
                signals.append(f"Below-average originality ({originality}/10)")

        # Check competitor similarity
        risk = audit_result.get("competitor_similarity_risk", "low")
        if risk in ("medium", "high"):
            signals.append(f"High competitor similarity risk ({risk})")

        # Check for overused patterns
        bp = audit_result.get("best_practices_checklist", {})
        if isinstance(bp, dict):
            passed = sum(1 for v in bp.values() if v)
            total = len(bp)
            if total > 0 and passed / total < 0.4:
                signals.append("Fails most best-practice checks")

        # Check trend alignment
        trend = audit_result.get("trend_alignment", {})
        if isinstance(trend, dict) and not trend.get("is_trending", True):
            signals.append("Not aligned with current trends")

        return signals

    @staticmethod
    def _calculate_fatigue_level(
        fatigue_signals: List[str],
        originality_score: float,
    ) -> FatigueLevel:
        """Calculate fatigue level from signals and originality score."""
        signal_count = len(fatigue_signals)
        cfg = CREATIVE_FATIGUE_CONFIG

        if signal_count == 0 and originality_score >= 7:
            return FatigueLevel.NONE
        elif signal_count <= 1 and originality_score >= 5:
            return FatigueLevel.LOW
        elif signal_count <= 2 and originality_score >= 4:
            return FatigueLevel.MEDIUM
        elif signal_count <= 3 and originality_score >= 3:
            return FatigueLevel.HIGH
        else:
            return FatigueLevel.CRITICAL

    @staticmethod
    async def _find_similar_creatives(
        db: AsyncSession,
        media: MediaAsset,
        company_history: List[MediaAsset],
    ) -> List[str]:
        """
        Find visually similar creatives in company history.

        Uses a heuristic based on dimensions, tags, and analysis results.
        Full visual similarity would require embedding comparison.
        """
        similar: List[str] = []

        for other in company_history:
            if other.id == media.id:
                continue

            similarity_score = 0.0

            # Dimension similarity (20%)
            if media.width and media.height and other.width and other.height:
                if media.width == other.width and media.height == other.height:
                    similarity_score += 0.2
                elif abs(media.width - other.width) < 100 and abs(media.height - other.height) < 100:
                    similarity_score += 0.1

            # Tag overlap (30%)
            media_tags = {t.tag_id for t in (media.tag_mappings or [])}
            other_tags = {t.tag_id for t in (other.tag_mappings or [])}
            if media_tags and other_tags:
                overlap = len(media_tags & other_tags)
                union = len(media_tags | other_tags)
                if union > 0:
                    similarity_score += 0.3 * (overlap / union)

            # Color palette similarity via analysis (50%)
            # This would require stored color histograms or embeddings
            # Placeholder: use file size as rough proxy
            if media.file_size and other.file_size:
                size_diff = abs(media.file_size - other.file_size) / max(media.file_size, 1)
                if size_diff < 0.1:
                    similarity_score += 0.15
                elif size_diff < 0.3:
                    similarity_score += 0.05

            if similarity_score >= CREATIVE_FATIGUE_CONFIG["similarity_threshold"]:
                similar.append(other.id)

        return similar[:10]  # Cap at 10 similar items


# ===========================================================================
# MediaOptimizationQueueService
# ===========================================================================


class MediaOptimizationQueueService:
    """
    Redis-based async job queue for media processing tasks.

    Enqueues jobs (thumbnail generation, optimization, AI analysis) and
    tracks their status. Workers poll the queue and execute jobs asynchronously.
    """

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"{JOB_STATUS_PREFIX}{job_id}"

    @staticmethod
    def _queue_channel(job_type: JobType) -> str:
        return f"{JOB_QUEUE_PREFIX}{job_type.value}"

    async def enqueue_job(
        self,
        job_type: JobType,
        media_id: str,
        company_id: int,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Enqueue a processing job in Redis.

        Args:
            job_type: Type of processing job.
            media_id: Target media asset ID.
            company_id: Tenant company ID.
            extra_payload: Additional job-specific data.

        Returns:
            Generated job ID.
        """
        job_id = f"{job_type.value}_{uuid.uuid4().hex[:12]}"
        job_data = {
            "job_id": job_id,
            "job_type": job_type.value,
            "media_id": media_id,
            "company_id": company_id,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error": None,
            "result": None,
        }
        if extra_payload:
            job_data["payload"] = extra_payload

        redis = await get_redis_client()
        await redis.set(
            self._job_key(job_id),
            json.dumps(job_data),
            ex=JOB_TIMEOUT_SECONDS,
        )
        await redis.lpush(self._queue_channel(job_type), json.dumps(job_data))
        return job_id

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a job."""
        redis = await get_redis_client()
        data = await redis.get(self._job_key(job_id))
        if data:
            return json.loads(data)
        return None

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update the status of a job."""
        redis = await get_redis_client()
        key = self._job_key(job_id)
        data = await redis.get(key)
        if not data:
            return

        job = json.loads(data)
        job["status"] = status
        if progress is not None:
            job["progress"] = progress
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
        if status in ("completed", "failed"):
            job["completed_at"] = datetime.now(timezone.utc).isoformat()

        await redis.set(key, json.dumps(job), ex=JOB_TIMEOUT_SECONDS)

    async def get_pending_jobs(
        self,
        job_type: JobType,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get pending jobs of a specific type from the queue."""
        redis = await get_redis_client()
        jobs = []
        for _ in range(limit):
            data = await redis.rpop(self._queue_channel(job_type))
            if not data:
                break
            job = json.loads(data)
            jobs.append(job)
        return jobs

    async def process_thumbnail_job(
        self,
        db: AsyncSession,
        media_id: str,
    ) -> Dict[str, Any]:
        """
        Process a thumbnail generation job.

        Args:
            db: Async database session.
            media_id: Target media asset ID.

        Returns:
            Result dict with generated variant info.
        """
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.id == media_id)
        )
        media = result.scalar_one_or_none()
        if not media:
            return {"error": "Media not found", "variants": []}

        storage = StorageService()
        source_data = await storage.read_media_file(media)

        if not source_data:
            return {"error": "File not readable from storage backend", "variants": []}

        variants = []
        if media.category == "image" and media.mime_type in PROCESSABLE_IMAGE_TYPES:
            variants = await ThumbnailService.generate_image_variants(
                db, media, source_data
            )
        elif media.category == "video" and media.mime_type in PROCESSABLE_VIDEO_TYPES:
            variant = await ThumbnailService.generate_video_thumbnail(
                db, media, source_data
            )
            if variant:
                variants = [variant]

        # Update media status to ready
        media.status = MediaStatus.READY
        await db.commit()

        # Trigger virus scan if pending
        if media.virus_scan_status == VirusScanStatus.PENDING.value:
            scan_result = await VirusScanningService.scan_file(source_data)
            await VirusScanningService.update_media_scan_status(db, media.id, scan_result)
            if scan_result["status"] == VirusScanStatus.INFECTED.value:
                await VirusScanningService.handle_infected_file(db, media)
                return {"error": "File infected with virus", "variants": [], "threat": scan_result.get("threat")}

        return {
            "variants": [
                {
                    "id": v.id,
                    "type": v.variant_type.value,
                    "width": v.width,
                    "height": v.height,
                    "file_size": v.file_size,
                }
                for v in variants
            ]
        }

    async def process_ai_analysis_job(
        self,
        db: AsyncSession,
        media_id: str,
        analysis_type: str,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process an AI analysis job."""
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.id == media_id)
        )
        media = result.scalar_one_or_none()
        if not media:
            return {"error": "Media not found"}

        try:
            analysis_enum = AnalysisType(analysis_type)
            analysis = await AIImageAnalysisService.analyze_media(
                db, media, analysis_enum, branch_id=branch_id
            )
            return {
                "analysis_id": analysis.id,
                "analysis_type": analysis_type,
                "confidence": analysis.confidence,
                "brand_identity_applied": analysis.brand_identity_applied,
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def process_optimize_job(
        self,
        db: AsyncSession,
        media_id: str,
    ) -> Dict[str, Any]:
        """
        Process an optimization job using ImageOptimizationService.

        Creates both an optimized JPEG variant and a WebP variant,
        leveraging thread pool for CPU-bound operations.
        """
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.id == media_id)
        )
        media = result.scalar_one_or_none()
        if not media or media.category != "image":
            return {"error": "Media not found or not an image"}

        storage = StorageService()
        source_data = await storage.read_media_file(media)
        if not source_data:
            return {"error": "File not readable from storage backend"}

        created_variants = []
        total_saved = 0

        # 1. Create optimized JPEG variant (progressive, downscaled if needed)
        opt_variant = await ImageOptimizationService.create_optimized_variant(
            db=db,
            media=media,
            source_data=source_data,
            variant_type=VariantType.OPTIMIZED,
        )
        if opt_variant:
            created_variants.append({
                "id": opt_variant.id,
                "type": "optimized",
                "width": opt_variant.width,
                "height": opt_variant.height,
                "file_size": opt_variant.file_size,
            })
            total_saved += max(0, media.file_size - opt_variant.file_size)

        # 2. Create WebP variant (better compression)
        webp_variant = await ImageOptimizationService.create_optimized_variant(
            db=db,
            media=media,
            source_data=source_data,
            variant_type=VariantType.WEBP,
        )
        if webp_variant:
            created_variants.append({
                "id": webp_variant.id,
                "type": "webp",
                "width": webp_variant.width,
                "height": webp_variant.height,
                "file_size": webp_variant.file_size,
            })
            total_saved = max(total_saved, media.file_size - webp_variant.file_size)

        # 3. Also generate responsive thumbnails via thread pool if not exists
        existing_variants = {v.variant_type for v in (media.variants or [])}
        thumbnail_types = {
            VariantType.SMALL: THUMBNAIL_DIMENSIONS["small"],
            VariantType.MEDIUM: THUMBNAIL_DIMENSIONS["medium"],
            VariantType.LARGE: THUMBNAIL_DIMENSIONS["large"],
        }
        for vtype, (max_w, max_h) in thumbnail_types.items():
            if vtype not in existing_variants:
                try:
                    variant_data = await ImageOptimizationService.optimize_image(
                        source_data=source_data,
                        mime_type=media.mime_type,
                        target_max_width=max_w,
                        target_max_height=max_h,
                        target_quality=IMAGE_QUALITY_SETTINGS.get(vtype.value, 82),
                    )
                    variant_path = ThumbnailService._variant_path(
                        media, vtype.value, media.mime_type
                    )
                    if media.storage_provider == StorageProvider.LOCAL:
                        await storage._store_local(variant_data, variant_path)
                    else:
                        await storage._store_remote(
                            variant_data, variant_path, media.storage_provider.value
                        )
                    img = Image.open(BytesIO(variant_data))
                    variant = MediaVariant(
                        media_id=media.id,
                        variant_type=vtype,
                        file_path=variant_path,
                        width=img.width,
                        height=img.height,
                        file_size=len(variant_data),
                        quality=IMAGE_QUALITY_SETTINGS.get(vtype.value, 82),
                    )
                    db.add(variant)
                    await db.commit()
                    created_variants.append({
                        "id": variant.id,
                        "type": vtype.value,
                        "width": variant.width,
                        "height": variant.height,
                        "file_size": variant.file_size,
                    })
                except Exception:
                    pass  # Non-fatal: skip failed responsive variant

        if not created_variants:
            return {"error": "No optimizations could be applied"}

        return {
            "variants": created_variants,
            "total_saved_bytes": total_saved,
            "original_size": media.file_size,
        }


# ===========================================================================
# ImageOptimizationService - Advanced Image Processing
# ===========================================================================

import concurrent.futures

# Global thread pool for CPU-bound Pillow operations
_image_processing_pool: Optional[concurrent.futures.ThreadPoolExecutor] = None


def _get_image_processing_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the global thread pool for image processing."""
    global _image_processing_pool
    if _image_processing_pool is None or _image_processing_pool._shutdown:
        _image_processing_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=IMAGE_PROCESSING_MAX_WORKERS,
            thread_name_prefix="imgproc-",
        )
    return _image_processing_pool


class ImageOptimizationService:
    """
    Advanced image optimization service for size reduction, format conversion,
    and quality enhancement.

    Uses a thread pool to run CPU-bound Pillow operations without blocking
    the async event loop. Supports:
    - Smart downscaling (preserve aspect ratio, max dimension enforcement)
    - Progressive JPEG output
    - Color profile conversion (to sRGB)
    - Metadata handling (strip or preserve)
    - Multi-format output (optimized JPEG, WebP, AVIF-ready)
    - Quality-aware recompression

    CDN BENEFIT: Optimized images are typically 40-70% smaller,
    reducing CDN transfer costs and improving page load times.
    """

    @staticmethod
    async def _run_in_thread(
        func, *args, timeout: Optional[int] = None
    ) -> Any:
        """Run a synchronous function in the image processing thread pool."""
        loop = asyncio.get_event_loop()
        pool = _get_image_processing_pool()
        timeout = timeout or IMAGE_PROCESSING_TIMEOUT_SECONDS
        return await asyncio.wait_for(
            loop.run_in_executor(pool, func, *args),
            timeout=timeout,
        )

    @staticmethod
    def _optimize_image_sync(
        source_data: bytes,
        mime_type: str,
        target_max_width: int = OPTIMIZATION_MAX_WIDTH,
        target_max_height: int = OPTIMIZATION_MAX_HEIGHT,
        target_quality: int = OPTIMIZATION_QUALITY_JPEG,
        output_format: Optional[str] = None,
    ) -> bytes:
        """
        Synchronous image optimization (runs in thread pool).

        Args:
            source_data: Raw image bytes.
            mime_type: Source MIME type.
            target_max_width: Maximum output width.
            target_max_height: Maximum output height.
            target_quality: JPEG/WebP quality (1-100).
            output_format: Force output format ('JPEG', 'WEBP', 'PNG').
                           If None, uses source format.

        Returns:
            Optimized image bytes.
        """
        from PIL import ImageCms

        img = Image.open(BytesIO(source_data))
        img = ImageOps.exif_transpose(img)

        # Determine output format
        if output_format:
            fmt = output_format.upper()
        elif mime_type == "image/png":
            fmt = "PNG"
        elif mime_type == "image/webp":
            fmt = "WEBP"
        elif mime_type == "image/gif":
            fmt = "GIF"
        else:
            fmt = "JPEG"

        # Convert palette/RGBA to RGB for JPEG output
        if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            # Create white background for transparency
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
        elif img.mode in ("RGBA", "P", "LA") and fmt != "PNG":
            img = img.convert("RGB")

        # Smart downscaling: only if image exceeds target dimensions
        orig_w, orig_h = img.width, img.height
        needs_resize = False
        new_w, new_h = orig_w, orig_h

        if orig_w > target_max_width or orig_h > target_max_height:
            ratio = min(target_max_width / orig_w, target_max_height / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            needs_resize = True

        # Also enforce absolute max dimension
        if max(orig_w, orig_h) > OPTIMIZATION_MAX_DIMENSION:
            ratio = OPTIMIZATION_MAX_DIMENSION / max(orig_w, orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            needs_resize = True

        if needs_resize:
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Color profile handling
        if OPTIMIZATION_COLOR_PROFILE_ACTION == "convert_to_srgb":
            try:
                if "icc_profile" in img.info:
                    icc = ImageCms.ImageCmsProfile(BytesIO(img.info["icc_profile"]))
                    srgb_profile = ImageCms.createProfile("sRGB")
                    img = ImageCms.profileToProfile(img, icc, srgb_profile)
            except Exception:
                pass  # Silently skip profile conversion on error
        elif OPTIMIZATION_COLOR_PROFILE_ACTION == "strip":
            img.info.pop("icc_profile", None)

        # Save to output buffer
        output = BytesIO()
        save_kwargs: Dict[str, Any] = {}

        if fmt == "JPEG":
            save_kwargs["quality"] = target_quality
            save_kwargs["progressive"] = OPTIMIZATION_PROGRESSIVE_JPEG
            save_kwargs["optimize"] = True
            save_kwargs["strip"] = True
            # Subsampling for smaller files at quality <= 80
            if target_quality <= 80:
                save_kwargs["subsampling"] = "4:2:0"
        elif fmt == "WEBP":
            save_kwargs["quality"] = target_quality
            save_kwargs["method"] = 6
        elif fmt == "PNG":
            save_kwargs["optimize"] = True

        img.save(output, format=fmt, **save_kwargs)
        return output.getvalue()

    @staticmethod
    async def optimize_image(
        source_data: bytes,
        mime_type: str,
        target_max_width: int = OPTIMIZATION_MAX_WIDTH,
        target_max_height: int = OPTIMIZATION_MAX_HEIGHT,
        target_quality: int = OPTIMIZATION_QUALITY_JPEG,
        output_format: Optional[str] = None,
    ) -> bytes:
        """
        Async image optimization using thread pool.

        Args:
            source_data: Raw image bytes.
            mime_type: Source MIME type.
            target_max_width: Maximum output width.
            target_max_height: Maximum output height.
            target_quality: Output quality 1-100.
            output_format: Force output format ('JPEG', 'WEBP', 'PNG').

        Returns:
            Optimized image bytes.

        Raises:
            ValidationError: If image cannot be processed.
            asyncio.TimeoutError: If processing exceeds timeout.
        """
        try:
            return await ImageOptimizationService._run_in_thread(
                ImageOptimizationService._optimize_image_sync,
                source_data,
                mime_type,
                target_max_width,
                target_max_height,
                target_quality,
                output_format,
            )
        except asyncio.TimeoutError:
            raise ValidationError(
                detail=f"Image optimization timed out after {IMAGE_PROCESSING_TIMEOUT_SECONDS}s"
            )
        except Exception as exc:
            raise ValidationError(detail=f"Image optimization failed: {str(exc)}")

    @staticmethod
    async def create_optimized_variant(
        db: AsyncSession,
        media: MediaAsset,
        source_data: bytes,
        variant_type: VariantType = VariantType.OPTIMIZED,
    ) -> Optional[MediaVariant]:
        """
        Create an optimized variant of an image and store it.

        Args:
            db: Async database session.
            media: Parent MediaAsset.
            source_data: Raw image bytes.
            variant_type: Variant type (OPTIMIZED or WEBP).

        Returns:
            Created MediaVariant or None.
        """
        is_webp = variant_type == VariantType.WEBP
        output_format = "WEBP" if is_webp else None
        quality = OPTIMIZATION_QUALITY_WEBP if is_webp else OPTIMIZATION_QUALITY_JPEG

        try:
            optimized_data = await ImageOptimizationService.optimize_image(
                source_data=source_data,
                mime_type=media.mime_type,
                target_quality=quality,
                output_format=output_format,
            )
        except ValidationError:
            return None

        # Skip if optimization didn't reduce size significantly
        if len(optimized_data) >= media.file_size * 0.95:
            return None

        # Generate storage path
        output_mime = "image/webp" if is_webp else media.mime_type
        variant_path = ThumbnailService._variant_path(
            media, variant_type.value, output_mime
        )

        # Store
        storage = StorageService()
        if media.storage_provider == StorageProvider.LOCAL:
            await storage._store_local(optimized_data, variant_path)
        else:
            await storage._store_remote(
                optimized_data, variant_path, media.storage_provider.value
            )

        # Get dimensions
        img = Image.open(BytesIO(optimized_data))
        variant = MediaVariant(
            media_id=media.id,
            variant_type=variant_type,
            file_path=variant_path,
            width=img.width,
            height=img.height,
            file_size=len(optimized_data),
            quality=quality,
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)
        return variant

    @staticmethod
    async def get_image_info(source_data: bytes) -> Dict[str, Any]:
        """
        Extract detailed image information without full processing.

        Returns dict with: format, mode, width, height, has_alpha,
        has_icc_profile, estimated_color_depth, file_size_bytes.
        """
        try:
            return await ImageOptimizationService._run_in_thread(
                ImageOptimizationService._get_image_info_sync, source_data
            )
        except Exception:
            return {"error": "Could not read image info"}

    @staticmethod
    def _get_image_info_sync(source_data: bytes) -> Dict[str, Any]:
        """Synchronous image info extraction."""
        with Image.open(BytesIO(source_data)) as img:
            info = {
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "has_alpha": img.mode in ("RGBA", "LA", "PA", "P"),
                "has_icc_profile": "icc_profile" in img.info,
                "file_size_bytes": len(source_data),
                "dpi": img.info.get("dpi"),
            }
            # Estimate bit depth
            mode_depth = {
                "1": 1, "L": 8, "LA": 16, "P": 8,
                "RGB": 24, "RGBA": 32, "CMYK": 32, "YCbCr": 24,
                "LAB": 24, "HSV": 24, "I": 32, "F": 32,
            }
            info["estimated_bits_per_pixel"] = mode_depth.get(img.mode, 24)
            return info

    @staticmethod
    def shutdown_pool() -> None:
        """Shutdown the image processing thread pool. Call on application exit."""
        global _image_processing_pool
        if _image_processing_pool:
            _image_processing_pool.shutdown(wait=False)
            _image_processing_pool = None
