"""
Constants for the Creative Studio & Media Pipeline module.

Defines allowed file types, size limits, image processing settings,
thumbnail dimensions, CDN configuration, AI analysis prompts,
brand identity settings, social platform optimization rules,
and creative audit configuration.
"""

from enum import Enum


class VariantType(str, Enum):
    """Image variant types for responsive serving."""
    THUMBNAIL = "thumbnail"
    VIDEO_THUMBNAIL = "video_thumbnail"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    OPTIMIZED = "optimized"
    WEBP = "webp"
    ORIGINAL = "original"


import os
from enum import Enum

# ---------------------------------------------------------------------------
# Allowed MIME types
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
    "image/heic",
    "image/heif",
    "image/avif",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
    "video/ogg",
    "video/mpeg",
}

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
}

ALLOWED_MIME_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES | ALLOWED_DOCUMENT_TYPES

# Quick type categorization helper
MIME_TYPE_CATEGORIES = {
    "image": ALLOWED_IMAGE_TYPES,
    "video": ALLOWED_VIDEO_TYPES,
    "document": ALLOWED_DOCUMENT_TYPES,
}

# ---------------------------------------------------------------------------
# Max file sizes per type (in bytes)
# ---------------------------------------------------------------------------

MAX_IMAGE_SIZE = 50 * 1024 * 1024      # 50 MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024     # 500 MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024   # 20 MB

MAX_FILE_SIZE_BY_CATEGORY = {
    "image": MAX_IMAGE_SIZE,
    "video": MAX_VIDEO_SIZE,
    "document": MAX_DOCUMENT_SIZE,
}

DEFAULT_MAX_FILE_SIZE = MAX_IMAGE_SIZE  # fallback

# ---------------------------------------------------------------------------
# File extension to MIME type mapping (common extensions)
# ---------------------------------------------------------------------------

EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".avif": "image/avif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".ogv": "video/ogg",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".pdf": "application/pdf",
}

# ---------------------------------------------------------------------------
# Image processing settings
# ---------------------------------------------------------------------------

IMAGE_QUALITY_SETTINGS = {
    "thumbnail": 75,
    "small": 80,
    "medium": 82,
    "large": 85,
    "optimized": 82,
    "webp": 80,
}

# Pillow resampling filter for resizing
PILLOW_RESAMPLING = "LANCZOS"  # Use Image.Resampling.LANCZOS in code

# Color profile handling
COLOR_PROFILE_STRATEGY = "keep"  # keep / convert_to_srgb / strip

# ---------------------------------------------------------------------------
# Thumbnail / responsive size dimensions (width in pixels)
# ---------------------------------------------------------------------------

THUMBNAIL_DIMENSIONS = {
    "thumbnail": (256, 256),   # Square thumbnail
    "small": (480, 480),       # Small preview
    "medium": (1024, 1024),    # Medium preview
    "large": (1920, 1920),     # Large preview
}

THUMBNAIL_SIZE_MAP = {
    "s": "small",
    "m": "medium",
    "l": "large",
    "t": "thumbnail",
}

# ---------------------------------------------------------------------------
# Storage configuration
# ---------------------------------------------------------------------------

class StorageProvider(str, Enum):
    """Supported storage backends."""

    LOCAL = "local"
    S3 = "s3"
    R2 = "r2"


# Default upload directories (when using local storage)
LOCAL_UPLOAD_DIR = "uploads"
LOCAL_THUMBNAIL_DIR = "uploads/thumbnails"
LOCAL_VARIANTS_DIR = "uploads/variants"

# Path templates
MEDIA_PATH_TEMPLATE = "{company_id}/{year}/{month}/{filename}"
THUMBNAIL_PATH_TEMPLATE = "{company_id}/{year}/{month}/thumbnails/{variant}_{filename}"
VARIANT_PATH_TEMPLATE = "{company_id}/{year}/{month}/variants/{variant_type}_{filename}"

# ---------------------------------------------------------------------------
# CDN configuration
# ---------------------------------------------------------------------------

CDN_URL = ""  # Set via environment (e.g., https://cdn.example.com)
CDN_ENABLED = False

# Signed URL configuration
SIGNED_URL_EXPIRY_SECONDS = 3600        # 1 hour default
SIGNED_URL_ALGORITHM = "HS256"
SIGNED_URL_SECRET_HEADER = "X-Signed-URL-Secret"

# Presigned upload URL expiry for direct browser uploads
PRESIGNED_UPLOAD_EXPIRY_SECONDS = 600   # 10 minutes

# ---------------------------------------------------------------------------
# Media asset status
# ---------------------------------------------------------------------------

class MediaStatus(str, Enum):
    """Lifecycle status of a media asset."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    DELETED = "deleted"

# ---------------------------------------------------------------------------
# AI analysis configuration
# ---------------------------------------------------------------------------

class AnalysisType(str, Enum):
    """Types of AI image analysis available."""

    CAPTION = "caption"
    HASHTAG = "hashtag"
    SCORE = "score"
    OBJECTS = "objects"
    BRAND_ALIGNMENT = "brand_alignment"
    INSTAGRAM_OPTIMIZE = "instagram_optimize"
    CREATIVE_AUDIT = "creative_audit"


# Base analysis prompts for OpenAI Vision
AI_ANALYSIS_PROMPTS = {
    AnalysisType.CAPTION: (
        "Generate a detailed, engaging caption for this image. "
        "Describe the scene, mood, colors, and any notable elements. "
        "Keep it concise but evocative (2-3 sentences). "
        "Return ONLY the caption text, no additional commentary."
    ),
    AnalysisType.HASHTAG: (
        "Suggest 15-20 relevant hashtags for this image. "
        "Include a mix of popular, niche, and branded hashtags. "
        "Consider the visual content, style, and context. "
        "Return ONLY a comma-separated list of hashtags (with # prefix), no explanations."
    ),
    AnalysisType.SCORE: (
        "Analyze this image and rate it on these criteria (score 1-100 each):\n"
        "1. Composition - visual balance, rule of thirds, framing\n"
        "2. Lighting - exposure, contrast, shadows/highlights\n"
        "3. Color - harmony, saturation, color grading\n"
        "4. Sharpness - focus quality, detail clarity\n"
        "5. Relevance - how engaging it is for social media\n"
        "Return as JSON with keys: composition, lighting, color, sharpness, relevance, overall. "
        "Also include a brief 'explanation' field (max 200 chars)."
    ),
    AnalysisType.OBJECTS: (
        "Identify all prominent objects, brands, text, and people in this image. "
        "Return a JSON list of objects with fields: label, confidence (0-1), "
        "bounding_box (if visible as {x, y, width, height} normalized 0-1). "
        "Also include a 'scene_description' field summarizing the overall scene."
    ),
    AnalysisType.BRAND_ALIGNMENT: (
        "Analyze how well this image aligns with the given brand identity. "
        "Consider: color palette match, visual tone consistency, style alignment, "
        "and whether the image communicates the brand's core values. "
        "Return JSON with keys: color_alignment_score (1-10), tone_alignment_score (1-10), "
        "overall_alignment_score (1-10), strengths (array), improvements (array), "
        "recommendations (array of specific actionable suggestions)."
    ),
    AnalysisType.INSTAGRAM_OPTIMIZE: (
        "Analyze this image for Instagram optimization. "
        "Return JSON with keys:\n"
        "- recommended_format: 'feed' | 'story' | 'reel' | 'carousel'\n"
        "- recommended_aspect_ratio: string (e.g. '1:1', '4:5', '9:16')\n"
        "- crop_suggestions: array of {region, reason} objects\n"
        "- text_overlay_suggestions: array of {text, position, font_style} objects\n"
        "- color_adjustments: {brightness, contrast, saturation, warmth} each -20 to +20\n"
        "- best_posting_time: string (e.g. 'Weekday 6-9 PM')\n"
        "- engagement_prediction: {estimated_likes_range, estimated_comments_range, estimated_shares_range}\n"
        "- content_tips: array of strings\n"
        "- accessibility_notes: array of strings (alt text suggestions)"
    ),
    AnalysisType.CREATIVE_AUDIT: (
        "Perform a creative audit on this image. "
        "Compare it against common creative patterns and identify:\n"
        "- fatigue_signals: array of strings (signs of overused concepts)\n"
        "- originality_score: 1-10\n"
        "- trend_alignment: {is_trending, trending_themes: array}\n"
        "- competitor_similarity_risk: 'low' | 'medium' | 'high'\n"
        "- audience_fatigue_indicators: array of strings\n"
        "- refresh_recommendations: array of strings\n"
        "- best_practices_checklist: {rule_of_thirds, leading_lines, negative_space, focal_point, color_contrast, each boolean}\n"
        "Return as structured JSON."
    ),
}

# Brand-aware caption generation prompt template
BRAND_AWARE_CAPTION_PROMPT = (
    "Generate an engaging {platform} caption for this image that aligns with the following brand identity:\n"
    "Brand Name: {brand_name}\n"
    "Brand Tone: {brand_tone}\n"
    "Brand Colors: {brand_colors}\n"
    "Target Audience: {target_audience}\n"
    "Language: {language}\n\n"
    "The caption should:\n"
    "- Reflect the brand's tone of voice\n"
    "- Naturally incorporate brand personality\n"
    "- Be optimized for {platform} engagement\n"
    "- Include a subtle call-to-action if appropriate\n"
    "- Use relevant emojis sparingly\n"
    "- Stay under {max_chars} characters\n\n"
    "Return ONLY the caption text, no additional commentary."
)

# Brand-aware hashtag generation prompt template
BRAND_AWARE_HASHTAG_PROMPT = (
    "Suggest hashtags for this image that align with the following brand identity:\n"
    "Brand Name: {brand_name}\n"
    "Industry: {industry}\n"
    "Brand Tone: {brand_tone}\n"
    "Target Audience: {target_audience}\n"
    "Language: {language}\n\n"
    "Include:\n"
    "- 3-5 branded hashtags (incorporate brand name or tagline)\n"
    "- 5-8 industry/niche hashtags\n"
    "- 3-5 trending/popular hashtags relevant to the image\n"
    "- 2-3 location-based hashtags if applicable\n\n"
    "Return ONLY a comma-separated list of hashtags (with # prefix), no explanations."
)

# Creative scoring rubric (1-10 scale with descriptions)
CREATIVE_SCORING_RUBRIC = {
    10: "Exceptional - Magazine-quality, perfectly composed, stunning visuals",
    9: "Excellent - Professional quality with strong visual impact",
    8: "Very Good - Well above average, minor improvements possible",
    7: "Good - Solid quality, meets professional standards",
    6: "Above Average - Decent with some notable strengths",
    5: "Average - Acceptable but not memorable",
    4: "Below Average - Noticeable issues that hurt engagement",
    3: "Poor - Multiple significant problems",
    2: "Very Poor - Major composition/technical flaws",
    1: "Unusable - Does not meet minimum quality standards",
}

# Instagram platform specifications
INSTAGRAM_FORMAT_SPECS = {
    "feed": {
        "aspect_ratios": ["1:1", "4:5", "1.91:1"],
        "min_resolution": (1080, 1080),
        "max_file_size_mb": 30,
        "recommended_dimensions": {
            "square": (1080, 1080),
            "portrait": (1080, 1350),
            "landscape": (1080, 566),
        },
        "caption_max_chars": 2200,
        "hashtag_limit": 30,
        "optimal_hashtags": 15,
    },
    "story": {
        "aspect_ratio": "9:16",
        "min_resolution": (1080, 1920),
        "max_file_size_mb": 30,
        "duration_seconds": 15,
        "text_safe_zone": "Top 20% and bottom 20% avoid text (UI overlay area)",
    },
    "reel": {
        "aspect_ratio": "9:16",
        "min_resolution": (1080, 1920),
        "max_duration_seconds": 90,
        "recommended_duration": 15,
        "max_file_size_mb": 4 * 1024,  # 4GB
    },
    "carousel": {
        "min_items": 2,
        "max_items": 10,
        "aspect_ratios": ["1:1", "4:5"],
    },
}

# Facebook platform specifications
FACEBOOK_FORMAT_SPECS = {
    "feed": {
        "aspect_ratios": ["1.91:1", "1:1", "4:5"],
        "min_resolution": (1200, 630),
        "max_file_size_mb": 8,
        "caption_max_chars": 63206,
    },
    "story": {
        "aspect_ratio": "9:16",
        "min_resolution": (1080, 1920),
    },
}

# TikTok platform specifications
TIKTOK_FORMAT_SPECS = {
    "video": {
        "aspect_ratio": "9:16",
        "min_resolution": (1080, 1920),
        "max_duration_seconds": 600,
        "recommended_duration": 15,
        "max_file_size_mb": 2876,  # ~2.8GB
    },
}

# Best posting times by platform (general recommendations)
BEST_POSTING_TIMES = {
    "instagram": {
        "weekday": "11 AM - 1 PM, 6 PM - 9 PM",
        "weekend": "10 AM - 1 PM",
        "worst": "Late night (12 AM - 5 AM)",
    },
    "facebook": {
        "weekday": "9 AM - 11 AM, 1 PM - 3 PM",
        "weekend": "12 PM - 1 PM",
        "worst": "Late night (11 PM - 5 AM)",
    },
    "tiktok": {
        "weekday": "7 AM - 9 AM, 7 PM - 11 PM",
        "weekend": "9 AM - 11 AM",
        "worst": "Midday work hours (10 AM - 4 PM)",
    },
}

# Creative fatigue detection thresholds
CREATIVE_FATIGUE_CONFIG = {
    "min_usage_count_for_fatigue": 3,
    "fatigue_score_threshold": 0.6,
    "similarity_threshold": 0.75,
    "days_before_considered_old": 90,
    "max_recommended_reuse": 5,
    "engagement_drop_threshold_pct": 30,
    "color_palette_variety_min": 3,
}

# AI analysis API configuration
AI_ANALYSIS_TIMEOUT_SECONDS = 45
AI_ANALYSIS_MAX_TOKENS = 800
AI_ANALYSIS_VISION_MODEL = "gpt-4o-mini"
AI_ANALYSIS_DETAIL_LEVEL = "auto"  # "low", "high", or "auto"

# ---------------------------------------------------------------------------
# Async job queue configuration
# ---------------------------------------------------------------------------

JOB_QUEUE_PREFIX = "media:job:"
JOB_STATUS_PREFIX = "media:job_status:"
JOB_QUEUE_CHANNEL = "media:job_queue"
JOB_TIMEOUT_SECONDS = 300  # 5 minutes

# Job types
class JobType(str, Enum):
    """Types of async media processing jobs."""

    THUMBNAIL = "thumbnail"
    OPTIMIZE = "optimize"
    AI_ANALYSIS = "ai_analysis"
    WEBP_CONVERT = "webp_convert"
    VIDEO_THUMBNAIL = "video_thumbnail"
    VIRUS_SCAN = "virus_scan"
    BRAND_ANALYSIS = "brand_analysis"
    CREATIVE_AUDIT = "creative_audit"

# ---------------------------------------------------------------------------
# Pagination defaults
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 100

# ---------------------------------------------------------------------------
# Virus scanning configuration (ClamAV - placeholder for future)
# ---------------------------------------------------------------------------

VIRUS_SCAN_ENABLED: bool = os.environ.get("VIRUS_SCAN_ENABLED", "false").lower() == "true"
CLAMAV_HOST: str = os.environ.get("CLAMAV_HOST", "localhost")
CLAMAV_PORT: int = int(os.environ.get("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT_SECONDS: int = 30
VIRUS_SCAN_MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB - larger files skip scan
VIRUS_SCAN_BATCH_SIZE: int = 10  # Files per batch scan job

# ---------------------------------------------------------------------------
# MIME magic byte signatures (first bytes for validation)
# ---------------------------------------------------------------------------

MIME_MAGIC_BYTES = {
    # Images
    b"\xff\xd8\xff": "image/jpeg",          # JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",       # PNG
    b"GIF87a": "image/gif",                  # GIF
    b"GIF89a": "image/gif",                  # GIF
    b"RIFF": "image/webp",                   # WebP (starts with RIFF....WEBP)
    b"BM": "image/bmp",                      # BMP
    b"II*\x00": "image/tiff",                # TIFF little-endian
    b"MM\x00*": "image/tiff",                # TIFF big-endian
    # Videos
    b"\x00\x00\x00\x1cftyp": None,           # MP4/MOV (check ftyp)
    b"\x00\x00\x00 ftyp": None,              # MP4 variant
    b"\x00\x00\x00\x18ftyp": None,           # MP4 variant
    b"\x00\x00\x00 ftypqt": None,            # MOV
    b"RIFF": "video/avi",                    # AVI (RIFF....AVI )
    # PDF
    b"%PDF": "application/pdf",              # PDF
}

# WebP specific check: after "RIFF....WEBP"
WEBP_MAGIC_OFFSET = 8
WEBP_MAGIC_EXPECTED = b"WEBP"

# PDF version detection
PDF_VERSION_MAP = {
    b"%PDF-1.0": "application/pdf",
    b"%PDF-1.1": "application/pdf",
    b"%PDF-1.2": "application/pdf",
    b"%PDF-1.3": "application/pdf",
    b"%PDF-1.4": "application/pdf",
    b"%PDF-1.5": "application/pdf",
    b"%PDF-1.6": "application/pdf",
    b"%PDF-1.7": "application/pdf",
    b"%PDF-2.0": "application/pdf",
}

# ---------------------------------------------------------------------------
# Checksum algorithm
# ---------------------------------------------------------------------------

CHECKSUM_ALGORITHM = "sha256"

# ---------------------------------------------------------------------------
# Allowed image formats for processing
# ---------------------------------------------------------------------------

PROCESSABLE_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

PROCESSABLE_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
}

# ---------------------------------------------------------------------------
# Image optimization settings
# ---------------------------------------------------------------------------

# Maximum dimensions before optimization triggers
OPTIMIZATION_MAX_DIMENSION = 4096  # px - images larger than this get downscaled
OPTIMIZATION_TARGET_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB target for optimized images
OPTIMIZATION_QUALITY_JPEG = 82
OPTIMIZATION_QUALITY_WEBP = 80
OPTIMIZATION_MAX_WIDTH = 2048  # Max width for optimized variant
OPTIMIZATION_MAX_HEIGHT = 2048  # Max height for optimized variant

# Progressive JPEG settings
OPTIMIZATION_PROGRESSIVE_JPEG = True

# ICC color profile handling during optimization
OPTIMIZATION_COLOR_PROFILE_ACTION = "convert_to_srgb"  # keep / convert_to_srgb / strip

# Metadata stripping during optimization (security + size reduction)
OPTIMIZATION_STRIP_EXIF = False  # Keep EXIF in original, strip from optimized
OPTIMIZATION_STRIP_ICC = False

# ---------------------------------------------------------------------------
# Async processing settings
# ---------------------------------------------------------------------------

# Thread pool size for CPU-bound image operations
IMAGE_PROCESSING_MAX_WORKERS = 4
# Timeout for individual image processing operations
IMAGE_PROCESSING_TIMEOUT_SECONDS = 60


# --- Virus Scanning (CLAMAV) ---
VIRUS_SCAN_ENABLED: bool = os.environ.get("VIRUS_SCAN_ENABLED", "false").lower() == "true"
CLAMAV_HOST: str = os.environ.get("CLAMAV_HOST", "clamav")
CLAMAV_PORT: int = int(os.environ.get("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT_SECONDS: int = int(os.environ.get("CLAMAV_TIMEOUT_SECONDS", "30"))
VIRUS_SCAN_MAX_FILE_SIZE: int = int(os.environ.get("VIRUS_SCAN_MAX_FILE_SIZE", "100")) * 1024 * 1024  # 100MB default


class VirusScanStatus(str, Enum):
    """Virus scan result statuses."""
    SKIPPED = "skipped"
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
