"""
AI Architecture module constants.

Defines OpenAI model configurations, default parameters, rate limits,
cost estimates per token, maximum context lengths, and cache TTL defaults.
"""

from typing import Any, Dict

# ---------------------------------------------------------------------------
# Model Configurations
# ---------------------------------------------------------------------------

OPENAI_MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "gpt-4o": {
        "name": "gpt-4o",
        "display_name": "GPT-4o",
        "description": "OpenAI's most capable multimodal model. Great for complex reasoning.",
        "max_context_tokens": 128000,
        "max_output_tokens": 4096,
        "supports_vision": True,
        "supports_json_mode": True,
        "supports_function_calling": True,
        "tier": "premium",
    },
    "gpt-4o-mini": {
        "name": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "description": "Fast, affordable small model for focused tasks.",
        "max_context_tokens": 128000,
        "max_output_tokens": 16384,
        "supports_vision": True,
        "supports_json_mode": True,
        "supports_function_calling": True,
        "tier": "standard",
    },
    "gpt-3.5-turbo": {
        "name": "gpt-3.5-turbo",
        "display_name": "GPT-3.5 Turbo",
        "description": "Legacy fast model for simple tasks.",
        "max_context_tokens": 16385,
        "max_output_tokens": 4096,
        "supports_vision": False,
        "supports_json_mode": True,
        "supports_function_calling": True,
        "tier": "standard",
    },
}

# ---------------------------------------------------------------------------
# Default Generation Parameters
# ---------------------------------------------------------------------------

DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_MAX_TOKENS: int = 2048
DEFAULT_TOP_P: float = 1.0
DEFAULT_FREQUENCY_PENALTY: float = 0.0
DEFAULT_PRESENCE_PENALTY: float = 0.0

# Default model for general completions
DEFAULT_MODEL: str = "gpt-4o-mini"

# ---------------------------------------------------------------------------
# Rate Limits (requests per minute) per Tier
# ---------------------------------------------------------------------------

RATE_LIMITS_PER_TIER: Dict[str, Dict[str, int]] = {
    "free": {
        "requests_per_minute": 10,
        "tokens_per_minute": 10000,
        "requests_per_day": 100,
    },
    "standard": {
        "requests_per_minute": 60,
        "tokens_per_minute": 60000,
        "requests_per_day": 1000,
    },
    "premium": {
        "requests_per_minute": 500,
        "tokens_per_minute": 500000,
        "requests_per_day": 10000,
    },
}

# Default rate limit tier for new companies
DEFAULT_RATE_LIMIT_TIER: str = "standard"

# ---------------------------------------------------------------------------
# Cost Per 1K Tokens (USD) - Input / Output
# ---------------------------------------------------------------------------

COST_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input": 0.005,
        "output": 0.015,
    },
    "gpt-4o-mini": {
        "input": 0.00015,
        "output": 0.0006,
    },
    "gpt-3.5-turbo": {
        "input": 0.0005,
        "output": 0.0015,
    },
}

# ---------------------------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------------------------

MAX_RETRIES: int = 3
RETRY_BASE_DELAY_SECONDS: float = 1.0
RETRY_MAX_DELAY_SECONDS: float = 60.0
RETRY_EXPONENTIAL_BASE: float = 2.0

# HTTP status codes that trigger a retry
RETRYABLE_STATUS_CODES: list = [429, 500, 502, 503, 504]

# ---------------------------------------------------------------------------
# Cache TTL Defaults (seconds)
# ---------------------------------------------------------------------------

CACHE_TTL_SHORT: int = 60       # 1 minute - for highly volatile data
CACHE_TTL_MEDIUM: int = 600     # 10 minutes - for suggestions
CACHE_TTL_LONG: int = 3600      # 1 hour - for stable completions
CACHE_TTL_EXTENDED: int = 86400 # 24 hours - for usage analytics cache

DEFAULT_CACHE_TTL: int = CACHE_TTL_MEDIUM

# Cache key prefixes
CACHE_KEY_PREFIX_COMPLETION: str = "ai:completion"
CACHE_KEY_PREFIX_SUGGESTION: str = "ai:suggestion"
CACHE_KEY_PREFIX_RECOMMENDATION: str = "ai:recommendation"
CACHE_KEY_PREFIX_USAGE: str = "ai:usage"

# ---------------------------------------------------------------------------
# Streaming Configuration
# ---------------------------------------------------------------------------

STREAM_CHUNK_SIZE: int = 1024
STREAM_TIMEOUT_SECONDS: int = 120

# ---------------------------------------------------------------------------
# Suggestion Generation
# ---------------------------------------------------------------------------

SUGGESTION_TRIGGER_TYPES: list = [
    "content_idea",
    "timing_optimization",
    "audience_targeting",
    "channel_selection",
    "budget_allocation",
    "campaign_optimization",
]

MAX_SUGGESTIONS_PER_REQUEST: int = 5
SUGGESTION_CONFIDENCE_THRESHOLD: float = 0.6

# ---------------------------------------------------------------------------
# Recommendation Categories
# ---------------------------------------------------------------------------

RECOMMENDATION_CATEGORIES: list = [
    "content",
    "timing",
    "audience",
    "channel",
    "budget",
    "creative",
]

RECOMMENDATION_STATUSES: list = [
    "pending",
    "applied",
    "dismissed",
]

MAX_RECOMMENDATIONS_PER_BATCH: int = 10

# ---------------------------------------------------------------------------
# Conversation & Message Settings
# ---------------------------------------------------------------------------

MAX_MESSAGES_PER_CONVERSATION: int = 100
CONVERSATION_TITLE_MAX_LENGTH: int = 200
MAX_CONVERSATIONS_PER_USER: int = 50

# ---------------------------------------------------------------------------
# Usage Limits (per company per month)
# ---------------------------------------------------------------------------

DEFAULT_MONTHLY_TOKEN_LIMIT: int = 1_000_000  # 1M tokens
DEFAULT_MONTHLY_COST_LIMIT_USD: float = 100.0

USAGE_LIMIT_ALERT_THRESHOLD: float = 0.8  # Alert at 80% usage

# ---------------------------------------------------------------------------
# Per-User Rate Limits
# ---------------------------------------------------------------------------

DEFAULT_USER_DAILY_REQUEST_LIMIT: int = 50
DEFAULT_USER_DAILY_TOKEN_LIMIT: int = 100_000

# ---------------------------------------------------------------------------
# Per-Company Rate Limits (requests per minute)
# ---------------------------------------------------------------------------

DEFAULT_COMPANY_RPM_LIMIT: int = 60  # requests per minute
DEFAULT_COMPANY_TPM_LIMIT: int = 60_000  # tokens per minute

# ---------------------------------------------------------------------------
# Circuit Breaker Configuration
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS: int = 60
CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 2

# ---------------------------------------------------------------------------
# OpenAI API Endpoints
# ---------------------------------------------------------------------------

OPENAI_API_BASE_URL: str = "https://api.openai.com/v1"
OPENAI_CHAT_COMPLETIONS_ENDPOINT: str = f"{OPENAI_API_BASE_URL}/chat/completions"
OPENAI_MODERATION_ENDPOINT: str = f"{OPENAI_API_BASE_URL}/moderations"

# ---------------------------------------------------------------------------
# OpenAI Moderation
# ---------------------------------------------------------------------------

MODERATION_ENABLED: bool = True
MODERATION_REJECT_CATEGORIES: list = [
    "hate",
    "hate/threatening",
    "self-harm",
    "sexual",
    "sexual/minors",
    "violence",
    "violence/graphic",
]

# ---------------------------------------------------------------------------
# Graceful Fallback Messages
# ---------------------------------------------------------------------------

FALLBACK_MESSAGE_NO_API_KEY: str = (
    "AI servisi yapilandirilmamis. Lutfen yoneticinize basvurun."
)
FALLBACK_MESSAGE_RATE_LIMITED: str = (
    "AI kullanim limitine ulasildi. Lutfen daha sonra tekrar deneyin."
)
FALLBACK_MESSAGE_MODERATION_BLOCKED: str = (
    "Iceriginiz potansiyel olarak zararli olarak isaretlendi. "
    "Lutfen yeniden ifade edip tekrar deneyin."
)
FALLBACK_MESSAGE_CIRCUIT_OPEN: str = (
    "AI servisi gecici olarak kullanilamiyor. Lutfen biraz sonra tekrar deneyin."
)

# ---------------------------------------------------------------------------
# Cache TTL Defaults (overrides)
# ---------------------------------------------------------------------------

CACHE_TTL_COMPLETION: int = 3600  # 1 hour for completions
CACHE_TTL_SUGGESTION: int = 600   # 10 minutes for suggestions

# ---------------------------------------------------------------------------
# System Prompt Defaults
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT: str = (
    "You are an AI marketing assistant. You help users create, optimize, "
    "and analyze marketing campaigns. Provide actionable, data-driven advice "
    "that is concise and relevant to the user's business context."
)

SUGGESTION_SYSTEM_PROMPT: str = (
    "You are an expert marketing strategist. Analyze the provided context "
    "and generate actionable marketing suggestions. Each suggestion should "
    "include a clear title, detailed description, and estimated confidence "
    "score (0.0-1.0). Focus on practical, implementable recommendations."
)

RECOMMENDATION_SYSTEM_PROMPT: str = (
    "You are a data-driven marketing analyst. Based on the analytics data "
    "provided, generate specific recommendations to improve marketing performance. "
    "Categorize each recommendation (content/timing/audience/channel), provide "
    "confidence scores, and list specific action items."
)
