"""
AI Architecture Pydantic v2 schemas.

Defines request/response models for all AI module endpoints:
- Prompt templates CRUD
- Conversations and messages
- AI suggestions and recommendations
- Usage analytics
- Cache management
- AI generation requests
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Shared Mixins
# ---------------------------------------------------------------------------

class TenantMixin(BaseModel):
    """Mixin adding tenant fields for request schemas."""

    company_id: int
    branch_id: Optional[int] = None


class TimestampMixin(BaseModel):
    """Mixin adding timestamp fields for response schemas."""

    created_at: datetime
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# AI Prompt Schemas
# ---------------------------------------------------------------------------

class AIPromptCreate(BaseModel):
    """Request schema for creating a new AI prompt template."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "company_id": 1,
            "branch_id": None,
            "name": "Campaign Idea Generator",
            "description": "Generates creative marketing campaign ideas",
            "system_prompt": "You are a creative marketing strategist...",
            "user_prompt_template": "Generate campaign ideas for {{industry}} targeting {{audience}}.",
            "model_name": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2048,
            "variables": ["industry", "audience"],
            "branch_aware": False,
            "is_default": False,
            "category": "marketing",
        }
    })

    company_id: int
    branch_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: str = Field(..., min_length=1)
    user_prompt_template: str = Field(..., min_length=1)
    model_name: str = Field(default="gpt-4o-mini")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=16384)
    variables: Optional[List[str]] = Field(default_factory=list)
    branch_aware: bool = False
    is_default: bool = False
    category: str = Field(default="general")


class AIPromptUpdate(BaseModel):
    """Request schema for updating an AI prompt template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=16384)
    variables: Optional[List[str]] = None
    branch_aware: Optional[bool] = None
    is_default: Optional[bool] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None


class AIPromptResponse(BaseModel):
    """Response schema for an AI prompt template."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int]
    name: str
    description: Optional[str]
    system_prompt: str
    user_prompt_template: str
    model_name: str
    temperature: float
    max_tokens: int
    variables: Optional[List[str]]
    branch_aware: bool = False
    is_default: bool = False
    category: str = "general"
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class AIPromptListResponse(BaseModel):
    """Response schema for listing AI prompt templates."""

    model_config = ConfigDict(from_attributes=True)

    items: List[AIPromptResponse]
    total: int
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# AI Message Schemas
# ---------------------------------------------------------------------------

class AIMessageCreate(BaseModel):
    """Request schema for creating a message in a conversation."""

    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str = Field(..., min_length=1)
    tokens: Optional[int] = Field(default=0, ge=0)


class AIMessageResponse(BaseModel):
    """Response schema for an AI message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    tokens: int
    model: Optional[str]
    finish_reason: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# AI Conversation Schemas
# ---------------------------------------------------------------------------

class AIConversationCreate(BaseModel):
    """Request schema for starting a new AI conversation."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Campaign Strategy Discussion",
            "model": "gpt-4o-mini",
            "prompt_id": 1,
        }
    })

    title: str = Field(..., min_length=1, max_length=200)
    model: Optional[str] = Field(default="gpt-4o-mini")
    prompt_id: Optional[int] = None


class AIConversationResponse(BaseModel):
    """Response schema for an AI conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int]
    user_id: int
    session_id: str
    title: str
    model: str
    total_tokens: int
    status: str
    prompt_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    messages: List[AIMessageResponse] = []


class AIConversationListResponse(BaseModel):
    """Response schema for listing AI conversations."""

    model_config = ConfigDict(from_attributes=True)

    items: List[AIConversationResponse]
    total: int
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# AI Generation Schemas
# ---------------------------------------------------------------------------

class AIGenerateRequest(BaseModel):
    """Request schema for generating an AI completion.

    Supports prompt templates via prompt_id with variable substitution.
    Branch-aware prompt selection is automatic when prompt_id is set.
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "prompt": "Write a marketing email for a summer sale",
            "model": "gpt-4o-mini",
            "system_prompt": None,
            "temperature": 0.7,
            "max_tokens": 2048,
            "variables": {"industry": "retail", "audience": "young adults"},
            "use_cache": True,
            "prompt_id": None,
        }
    })

    prompt: str = Field(..., min_length=1)
    model: Optional[str] = Field(default="gpt-4o-mini")
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=16384)
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict)
    use_cache: bool = True
    prompt_id: Optional[int] = Field(default=None, ge=1)


class AIGenerateResponse(BaseModel):
    """Response schema for an AI completion.

    Includes supervised mode flags and cost estimation metadata.
    """

    content: str
    model: str
    tokens_used: int
    tokens_input: int
    tokens_output: int
    cost_estimate: float
    cost_estimate_pre: Optional[float] = None
    latency_ms: int
    cached: bool = False
    finish_reason: Optional[str] = None
    supervised: bool = True
    requires_approval: bool = True


# ---------------------------------------------------------------------------
# AI Suggestion Schemas
# ---------------------------------------------------------------------------

class AISuggestionCreate(BaseModel):
    """Request schema for generating AI suggestions."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "trigger_type": "content_idea",
            "context": {
                "industry": "retail",
                "target_audience": "young adults",
                "budget_range": "medium",
            },
            "count": 3,
        }
    })

    trigger_type: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    count: int = Field(default=3, ge=1, le=10)


class AISuggestionFeedback(BaseModel):
    """Request schema for submitting feedback on a suggestion."""

    feedback: str = Field(..., pattern="^(helpful|not_helpful|applied|dismissed)$")
    notes: Optional[str] = None


class AISuggestionResponse(BaseModel):
    """Response schema for an AI suggestion."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int]
    trigger_type: str
    context: Optional[Dict[str, Any]]
    prompt_used: str
    response: str
    tokens_used: int
    model: str
    was_applied: bool
    user_feedback: Optional[str]
    created_at: datetime


class AISuggestionListResponse(BaseModel):
    """Response schema for listing AI suggestions."""

    model_config = ConfigDict(from_attributes=True)

    items: List[AISuggestionResponse]
    total: int
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# AI Recommendation Schemas
# ---------------------------------------------------------------------------

class AIRecommendationCreate(BaseModel):
    """Request schema for generating AI recommendations."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "categories": ["content", "timing"],
            "context": {
                "recent_campaigns": ["summer_sale", "back_to_school"],
                "performance_data": {"ctr": 2.5, "conversion": 1.8},
            },
            "count": 5,
        }
    })

    categories: Optional[List[str]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    count: int = Field(default=5, ge=1, le=10)


class AIRecommendationResponse(BaseModel):
    """Response schema for an AI recommendation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    branch_id: Optional[int]
    category: str
    title: str
    description: str
    confidence_score: float
    data_source: Optional[str]
    action_items: Optional[List[Dict[str, Any]]]
    status: str
    created_at: datetime


class AIRecommendationListResponse(BaseModel):
    """Response schema for listing AI recommendations."""

    model_config = ConfigDict(from_attributes=True)

    items: List[AIRecommendationResponse]
    total: int
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# AI Usage Schemas
# ---------------------------------------------------------------------------

class AIUsageFilter(BaseModel):
    """Filter parameters for AI usage analytics."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "company_id": 1,
            "user_id": None,
            "model": None,
            "start_date": "2024-01-01T00:00:00",
            "end_date": "2024-12-31T23:59:59",
        }
    })

    company_id: Optional[int] = None
    user_id: Optional[int] = None
    model: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AIUsageResponse(BaseModel):
    """Response schema for a single AI usage log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    user_id: Optional[int]
    model: str
    endpoint: str
    tokens_input: int
    tokens_output: int
    cost_estimate: float
    latency_ms: int
    status: str
    created_at: datetime


class AIUsageSummary(BaseModel):
    """Aggregated AI usage summary for analytics."""

    total_requests: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens: int
    total_cost_estimate: float
    avg_latency_ms: float
    avg_tokens_per_request: float
    requests_by_model: Dict[str, int]
    requests_by_status: Dict[str, int]
    tokens_by_day: Dict[str, int]
    cost_by_day: Dict[str, float]


class AIUsageListResponse(BaseModel):
    """Response schema for listing AI usage logs."""

    model_config = ConfigDict(from_attributes=True)

    items: List[AIUsageResponse]
    total: int
    page: int = 1
    page_size: int = 20


# ---------------------------------------------------------------------------
# AI Cache Schemas
# ---------------------------------------------------------------------------

class AICacheResponse(BaseModel):
    """Response schema for an AI cache entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cache_key: str
    model: str
    prompt_hash: str
    tokens: int
    expires_at: datetime
    hit_count: int
    created_at: datetime


class AICacheStats(BaseModel):
    """Cache statistics response."""

    total_entries: int
    active_entries: int
    expired_entries: int
    total_hits: int
    hit_rate: float
    avg_hit_count: float
    total_tokens_saved: int
    estimated_cost_savings: float


# ---------------------------------------------------------------------------
# Send Message Schemas
# ---------------------------------------------------------------------------

class AISendMessageRequest(BaseModel):
    """Request schema for sending a message in a conversation."""

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "content": "Help me write a social media post about our new product",
            "stream": False,
        }
    })

    content: str = Field(..., min_length=1)
    stream: bool = False


class AISendMessageResponse(BaseModel):
    """Response schema for a sent message with AI reply."""

    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
    tokens_used: int
    cost_estimate: float
    latency_ms: int


# ---------------------------------------------------------------------------
# Error Response Schema
# ---------------------------------------------------------------------------

class AIErrorResponse(BaseModel):
    """Error response schema for AI operations."""

    detail: str
    error_code: Optional[str] = None
    retry_after: Optional[int] = None
