"""
AI Architecture database models.

Defines 7 tables for the AI module:
- ai_prompts: Reusable prompt templates with variables
- ai_conversations: Chat conversation sessions
- ai_messages: Individual messages within conversations
- ai_suggestions: AI-generated marketing suggestions
- ai_recommendations: Data-driven marketing recommendations
- ai_usage_logs: API usage tracking and cost monitoring
- ai_cache: Response cache for AI completions
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Shared Enums
# ---------------------------------------------------------------------------

class AIModelName(str, enum.Enum):
    """Supported OpenAI model names."""

    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_3_5_TURBO = "gpt-3.5-turbo"


class MessageRole(str, enum.Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ConversationStatus(str, enum.Enum):
    """Lifecycle status of a conversation."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SuggestionTriggerType(str, enum.Enum):
    """Type of event that triggered an AI suggestion."""

    CONTENT_IDEA = "content_idea"
    TIMING_OPTIMIZATION = "timing_optimization"
    AUDIENCE_TARGETING = "audience_targeting"
    CHANNEL_SELECTION = "channel_selection"
    BUDGET_ALLOCATION = "budget_allocation"
    CAMPAIGN_OPTIMIZATION = "campaign_optimization"


class RecommendationCategory(str, enum.Enum):
    """Category of an AI marketing recommendation."""

    CONTENT = "content"
    TIMING = "timing"
    AUDIENCE = "audience"
    CHANNEL = "channel"
    BUDGET = "budget"
    CREATIVE = "creative"


class RecommendationStatus(str, enum.Enum):
    """Lifecycle status of a recommendation."""

    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class UserFeedback(str, enum.Enum):
    """User feedback on AI suggestions."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    APPLIED = "applied"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# 1. AI Prompts
# ---------------------------------------------------------------------------

class AIPrompt(Base):
    """
    Reusable AI prompt template for a company/branch.

    Stores system prompt, user prompt template with variable placeholders,
    model configuration, and template metadata for versioned prompt management.
    """

    __tablename__ = "ai_prompts"
    __table_args__ = {
        "schema": None,
        "comment": "Reusable AI prompt templates with variable support",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    name = Column(String(255), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=True)

    model_name = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        default=AIModelName.GPT_4O_MINI,
        nullable=False,
    )
    temperature = Column(
        Float,
        default=0.7,
        nullable=False,
    )
    max_tokens = Column(
        Integer,
        default=2048,
        nullable=False,
    )

    variables = Column(JSON, nullable=True, default=list)

    # Branch-aware prompt: if True, this prompt is scoped to a specific branch
    branch_aware = Column(Boolean, default=False, nullable=False)

    # Default prompt: auto-selected when no specific prompt is requested
    is_default = Column(Boolean, default=False, nullable=False)

    # Template category for grouping (e.g., "marketing", "analytics", "general")
    category = Column(String(50), nullable=True, default="general")

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    conversations = relationship(
        "AIConversation",
        back_populates="prompt",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AIPrompt(id={self.id}, name='{self.name}', "
            f"model='{self.model_name}', company_id={self.company_id}, "
            f"branch_aware={self.branch_aware}, is_default={self.is_default})>"
        )


# ---------------------------------------------------------------------------
# 2. AI Conversations
# ---------------------------------------------------------------------------

class AIConversation(Base):
    """
    A chat conversation session between a user and the AI.

    Tracks metadata including model used, total token consumption,
    and conversation lifecycle status.
    """

    __tablename__ = "ai_conversations"
    __table_args__ = {
        "schema": None,
        "comment": "AI chat conversation sessions",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        nullable=True,
        index=True,
    )
    user_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    prompt_id = Column(
        Integer,
        ForeignKey(
            "ai_prompts.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_ai_conversations_prompt_id",
        ),
        nullable=True,
        index=True,
    )

    session_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)

    model = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        nullable=False,
    )
    total_tokens = Column(Integer, default=0, nullable=False)

    status = Column(
        Enum(ConversationStatus, name="conversationstatus", create_type=True),
        default=ConversationStatus.ACTIVE,
        nullable=False,
    )

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    prompt = relationship("AIPrompt", back_populates="conversations")
    messages = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AIMessage.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<AIConversation(id={self.id}, "
            f"session_id='{self.session_id}', "
            f"user_id={self.user_id}, "
            f"status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# 3. AI Messages
# ---------------------------------------------------------------------------

class AIMessage(Base):
    """
    A single message within an AI conversation.

    Stores the message content, role, token count, model used,
    and finish reason for tracking and analytics.
    """

    __tablename__ = "ai_messages"
    __table_args__ = {
        "schema": None,
        "comment": "Individual messages within AI conversations",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    conversation_id = Column(
        Integer,
        ForeignKey(
            "ai_conversations.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ai_messages_conversation_id",
        ),
        nullable=False,
        index=True,
    )

    role = Column(
        Enum(MessageRole, name="messagerole", create_type=True),
        nullable=False,
    )
    content = Column(Text, nullable=False)

    tokens = Column(Integer, default=0, nullable=False)
    model = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        nullable=True,
    )
    finish_reason = Column(String(50), nullable=True)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    conversation = relationship("AIConversation", back_populates="messages")

    def __repr__(self) -> str:
        return (
            f"<AIMessage(id={self.id}, "
            f"role='{self.role}', "
            f"conversation_id={self.conversation_id}, "
            f"tokens={self.tokens})>"
        )


# ---------------------------------------------------------------------------
# 4. AI Suggestions
# ---------------------------------------------------------------------------

    # Relationships

class AISuggestion(Base):
    """
    AI-generated marketing suggestion for a company/branch.

    Captures the trigger context, prompt used, AI response,
    token usage, and user feedback for continuous improvement.
    """

    __tablename__ = "ai_suggestions"
    __table_args__ = {
        "schema": None,
        "comment": "AI-generated marketing suggestions with feedback tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    trigger_type = Column(
        Enum(SuggestionTriggerType, name="suggestiontriggertype", create_type=True),
        nullable=False,
        index=True,
    )
    context = Column(JSON, nullable=True)
    prompt_used = Column(Text, nullable=False)
    response = Column(Text, nullable=False)

    tokens_used = Column(Integer, default=0, nullable=False)
    model = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        nullable=False,
    )

    was_applied = Column(Boolean, default=False, nullable=False)
    # Supervised mode: human approval tracking
    supervised_mode = Column(Boolean, default=True, nullable=False)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approval_status = Column(
        String(20),
        default="pending",
        nullable=False,
        doc="pending | approved | rejected - AI output approval status"
    )

    user_feedback = Column(
        Enum(UserFeedback, name="userfeedback", create_type=True),
        nullable=True,
    )

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AISuggestion(id={self.id}, "
            f"trigger_type='{self.trigger_type}', "
            f"company_id={self.company_id}, "
            f"was_applied={self.was_applied}, "
            f"approval='{self.approval_status}')>"
        )


# ---------------------------------------------------------------------------
# 5. AI Recommendations
# ---------------------------------------------------------------------------

class AIRecommendation(Base):
    """
    Data-driven marketing recommendation for a company/branch.

    Generated based on analytics data, categorized by type,
    with confidence scoring and action item tracking.
    """

    __tablename__ = "ai_recommendations"
    __table_args__ = {
        "schema": None,
        "comment": "Data-driven marketing recommendations",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    branch_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    category = Column(
        Enum(RecommendationCategory, name="recommendationcategory", create_type=True),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    confidence_score = Column(
        Float,
        nullable=False,
    )
    data_source = Column(String(255), nullable=True)
    action_items = Column(JSON, nullable=True)

    status = Column(
        Enum(RecommendationStatus, name="recommendationstatus", create_type=True),
        default=RecommendationStatus.PENDING,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AIRecommendation(id={self.id}, "
            f"category='{self.category}', "
            f"title='{self.title}', "
            f"confidence={self.confidence_score}, "
            f"status='{self.status}')>"
        )


# ---------------------------------------------------------------------------
# 6. AI Usage Logs
# ---------------------------------------------------------------------------

class AIUsageLog(Base):
    """
    Log entry for every AI API call made by the system.

    Tracks tokens, estimated cost, latency, and status for
    usage analytics, cost monitoring, and rate limiting.
    """

    __tablename__ = "ai_usage_logs"
    __table_args__ = {
        "schema": None,
        "comment": "AI API usage logs for cost and token tracking",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    company_id = Column(
        Integer,
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    model = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        nullable=False,
    )
    endpoint = Column(String(255), nullable=False)

    tokens_input = Column(Integer, default=0, nullable=False)
    tokens_output = Column(Integer, default=0, nullable=False)
    cost_estimate = Column(
        Float,
        default=0.0,
        nullable=False,
    )
    latency_ms = Column(Integer, default=0, nullable=False)

    status = Column(String(50), nullable=False, index=True)

    # Supervised mode flag for this request
    supervised_mode = Column(Boolean, default=True, nullable=False)

    # Branch ID for branch-aware analytics
    branch_id = Column(Integer, nullable=True)

    # Request metadata: prompt_id, cache_hit, retry_count, moderation_result
    request_metadata = Column(JSON, nullable=True, default=dict)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AIUsageLog(id={self.id}, "
            f"model='{self.model}', "
            f"company_id={self.company_id}, "
            f"tokens_in={self.tokens_input}, "
            f"tokens_out={self.tokens_output}, "
            f"cost=${self.cost_estimate:.4f}, "
            f"supervised={self.supervised_mode})>"
        )


# ---------------------------------------------------------------------------
# 7. AI Cache
# ---------------------------------------------------------------------------

class AICache(Base):
    """
    Cache of AI completion responses for deduplication and performance.

    Stores hashed prompts with their responses, expiration timestamps,
    and hit counts for cache analytics and eviction.
    """

    __tablename__ = "ai_cache"
    __table_args__ = {
        "schema": None,
        "comment": "Cache of AI completion responses",
    }

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    model = Column(
        Enum(AIModelName, name="aimodelname", create_type=True),
        nullable=False,
    )
    prompt_hash = Column(String(64), nullable=False, index=True)
    response = Column(Text, nullable=False)

    tokens = Column(Integer, default=0, nullable=False)

    expires_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, default=0, nullable=False)

    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AICache(id={self.id}, "
            f"cache_key='{self.cache_key}', "
            f"model='{self.model}', "
            f"hits={self.hit_count}, "
            f"expires_at={self.expires_at})>"
        )
