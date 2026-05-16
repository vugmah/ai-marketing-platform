"""Pydantic v2 schemas for the AI Customer Support module."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===========================================================================
# Base Mixins
# ===========================================================================

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TenantMixin(BaseModel):
    """Mixin for tenant isolation fields."""
    company_id: int
    branch_id: Optional[int] = None


# ===========================================================================
# Support Ticket Schemas
# ===========================================================================

class TicketBase(BaseModel):
    """Base fields for support tickets."""
    customer_id: Optional[str] = Field(None, max_length=255)
    customer_name: Optional[str] = Field(None, max_length=255)
    customer_email: Optional[str] = Field(None, max_length=255)
    source: str = Field(..., pattern="^(whatsapp|telegram|instagram|facebook|email|web)$")
    source_conversation_id: Optional[str] = Field(None, max_length=255)
    subject: str = Field(..., max_length=500)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    category: Optional[str] = Field(None, pattern="^(billing|technical|sales|general)$")
    tags: Optional[List[str]] = Field(default=None)


class TicketCreate(TicketBase):
    """Schema for creating a new support ticket."""
    company_id: int
    branch_id: Optional[int] = None
    assigned_to: Optional[int] = None
    initial_message: Optional[str] = Field(
        None, description="Optional initial message content from the customer"
    )


class TicketUpdate(BaseModel):
    """Schema for updating a support ticket."""
    subject: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, pattern="^(open|pending|resolved|closed)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    category: Optional[str] = Field(None, pattern="^(billing|technical|sales|general)$")
    tags: Optional[List[str]] = None
    assigned_to: Optional[int] = None
    ai_handled: Optional[bool] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class TicketAssign(BaseModel):
    """Schema for assigning a ticket to an agent."""
    assigned_to: int
    note: Optional[str] = None


class TicketEscalate(BaseModel):
    """Schema for escalating a ticket."""
    reason: str = Field(..., min_length=1, max_length=1000)
    new_priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    assign_to: Optional[int] = None


class TicketClose(BaseModel):
    """Schema for closing a ticket."""
    resolution_note: Optional[str] = None


class TicketResponse(TicketBase, TenantMixin, TimestampMixin):
    """Schema for ticket response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    assigned_to: Optional[int] = None
    ai_handled: bool = False
    ai_confidence: Optional[float] = None
    resolved_at: Optional[datetime] = None
    message_count: Optional[int] = Field(None, description="Number of messages in the ticket")
    last_activity_at: Optional[datetime] = None


class TicketListResponse(BaseModel):
    """Schema for paginated ticket list response."""
    items: List[TicketResponse]
    total: int
    page: int
    page_size: int


class TicketFilterParams(BaseModel):
    """Query parameters for filtering tickets."""
    status: Optional[str] = Field(None, pattern="^(open|pending|resolved|closed)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    source: Optional[str] = Field(None, pattern="^(whatsapp|telegram|instagram|facebook|email|web)$")
    category: Optional[str] = Field(None, pattern="^(billing|technical|sales|general)$")
    assignee: Optional[int] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ===========================================================================
# Support Message Schemas
# ===========================================================================

class MessageBase(BaseModel):
    """Base fields for support messages."""
    content: str = Field(..., min_length=1)
    attachments: Optional[List[Dict[str, Any]]] = Field(default=None)
    internal_note: bool = False


class MessageCreate(MessageBase):
    """Schema for creating a new message."""
    sender_type: str = Field(default="agent", pattern="^(customer|agent|ai|system)$")
    sender_id: Optional[int] = None


class MessageResponse(MessageBase, TimestampMixin):
    """Schema for message response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    sender_type: str
    sender_id: Optional[int] = None
    ai_generated: bool = False
    ai_confidence: Optional[float] = None
    sentiment: Optional[str] = None


class MessageListResponse(BaseModel):
    """Schema for paginated message list response."""
    items: List[MessageResponse]
    total: int
    page: int
    page_size: int


class AIReplyRequest(BaseModel):
    """Schema for requesting an AI-generated reply."""
    context_override: Optional[str] = Field(
        None, description="Optional context to override RAG retrieval"
    )
    tone: Optional[str] = Field(default="professional", pattern="^(professional|friendly|formal|empathetic)$")
    max_length: int = Field(default=500, ge=50, le=2000)


class AIReplyResponse(BaseModel):
    """Schema for AI-generated reply response (approval mode default ON)."""
    content: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    kb_articles_used: List[int] = Field(default_factory=list)
    relevance_scores: Dict[str, float] = Field(default_factory=dict)
    suggested_human_takeover: bool = False
    tokens_used: int = 0
    cost_estimate: float = 0.0

    # Approval mode fields - DEFAULT: AI cevabi otomatik GONDERILMEZ
    auto_sent: bool = False
    requires_approval: bool = True
    approval_status: str = Field(default="pending", pattern="^(pending|approved|rejected|auto_sent|filtered)$")

    # Filtering results
    forbidden_triggered: bool = False
    forbidden_keywords_found: List[str] = Field(default_factory=list)
    forbidden_patterns_found: List[str] = Field(default_factory=list)

    # Audit log reference
    audit_log_id: Optional[int] = None

    # Escalation info
    escalation_triggered: bool = False
    escalation_reason: Optional[str] = None


class HumanTakeoverRequest(BaseModel):
    """Schema for human takeover request."""
    reason: Optional[str] = "Human agent requested"


class HumanTakeoverResponse(BaseModel):
    """Schema for human takeover response."""
    success: bool
    message: str
    ticket_id: int


# ===========================================================================
# Knowledge Base Article Schemas
# ===========================================================================

class KnowledgeBaseArticleBase(BaseModel):
    """Base fields for KB articles."""
    title: str = Field(..., max_length=500)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = Field(default=None)
    keywords: Optional[List[str]] = Field(default=None)
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")


class KnowledgeBaseArticleCreate(KnowledgeBaseArticleBase):
    """Schema for creating a KB article."""
    company_id: int
    source: str = Field(default="manual", pattern="^(manual|ai_generated)$")


class KnowledgeBaseArticleUpdate(BaseModel):
    """Schema for updating a KB article."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|archived)$")
    vector_embedding: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class KnowledgeBaseArticleResponse(KnowledgeBaseArticleBase, TimestampMixin):
    """Schema for KB article response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    source: str
    view_count: int = 0
    helpful_count: int = 0
    created_by: Optional[int] = None


class KnowledgeBaseArticleListResponse(BaseModel):
    """Schema for paginated KB article list response."""
    items: List[KnowledgeBaseArticleResponse]
    total: int
    page: int
    page_size: int


class KnowledgeBaseSearchRequest(BaseModel):
    """Schema for KB search request."""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeBaseSearchResult(BaseModel):
    """Schema for a single KB search result with relevance score."""
    article: KnowledgeBaseArticleResponse
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class KnowledgeBaseSearchResponse(BaseModel):
    """Schema for KB search response."""
    results: List[KnowledgeBaseSearchResult]
    query: str
    total_found: int


class KnowledgeBaseCategoryBase(BaseModel):
    """Base fields for KB categories."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0


class KnowledgeBaseCategoryCreate(KnowledgeBaseCategoryBase):
    """Schema for creating a KB category."""
    company_id: int


class KnowledgeBaseCategoryUpdate(BaseModel):
    """Schema for updating a KB category."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class KnowledgeBaseCategoryResponse(KnowledgeBaseCategoryBase, TimestampMixin):
    """Schema for KB category response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    children: List[KnowledgeBaseCategoryResponse] = Field(default_factory=list)


# ===========================================================================
# Support Macro Schemas
# ===========================================================================

class SupportMacroBase(BaseModel):
    """Base fields for support macros."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    shortcut: str = Field(..., max_length=50, pattern="^/[a-zA-Z0-9_-]+$")
    content: str = Field(..., min_length=1)
    variables: Optional[Dict[str, str]] = Field(default=None)
    category: Optional[str] = Field(None, max_length=100)


class SupportMacroCreate(SupportMacroBase):
    """Schema for creating a support macro."""
    company_id: int


class SupportMacroUpdate(BaseModel):
    """Schema for updating a support macro."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    shortcut: Optional[str] = Field(None, max_length=50, pattern="^/[a-zA-Z0-9_-]+$")
    content: Optional[str] = Field(None, min_length=1)
    variables: Optional[Dict[str, str]] = None
    category: Optional[str] = Field(None, max_length=100)

    model_config = ConfigDict(str_strip_whitespace=True)


class SupportMacroResponse(SupportMacroBase, TimestampMixin):
    """Schema for support macro response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_by: Optional[int] = None


class SupportMacroListResponse(BaseModel):
    """Schema for paginated macro list response."""
    items: List[SupportMacroResponse]
    total: int
    page: int
    page_size: int


class MacroExpandRequest(BaseModel):
    """Schema for expanding a macro with variables."""
    variables: Dict[str, Any] = Field(default_factory=dict)


class MacroExpandResponse(BaseModel):
    """Schema for macro expansion response."""
    expanded_content: str
    macro_name: str
    shortcut: str


# ===========================================================================
# Escalation Rule Schemas
# ===========================================================================

class EscalationRuleBase(BaseModel):
    """Base fields for escalation rules."""
    name: str = Field(..., max_length=200)
    conditions: Dict[str, Any] = Field(..., description="Conditions that trigger the rule")
    actions: Dict[str, Any] = Field(..., description="Actions to take when triggered")
    is_active: bool = True


class EscalationRuleCreate(EscalationRuleBase):
    """Schema for creating an escalation rule."""
    company_id: int


class EscalationRuleUpdate(BaseModel):
    """Schema for updating an escalation rule."""
    name: Optional[str] = Field(None, max_length=200)
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(str_strip_whitespace=True)


class EscalationRuleResponse(EscalationRuleBase, TimestampMixin):
    """Schema for escalation rule response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int


class EscalationRuleListResponse(BaseModel):
    """Schema for paginated escalation rule list response."""
    items: List[EscalationRuleResponse]
    total: int
    page: int
    page_size: int


class EscalationTriggerResult(BaseModel):
    """Schema for escalation trigger result."""
    triggered: bool
    rules_matched: List[int] = Field(default_factory=list)
    actions_taken: List[str] = Field(default_factory=list)
    ticket_id: int


# ===========================================================================
# Support Analytics Schemas
# ===========================================================================

class SupportAnalyticsBase(BaseModel):
    """Base fields for support analytics."""
    date: datetime
    total_tickets: int = 0
    resolved_tickets: int = 0
    avg_response_time: Optional[float] = None
    avg_resolution_time: Optional[float] = None
    ai_resolution_rate: Optional[float] = None
    customer_satisfaction: Optional[float] = None
    tickets_by_source: Optional[Dict[str, int]] = None
    tickets_by_category: Optional[Dict[str, int]] = None


class SupportAnalyticsResponse(SupportAnalyticsBase):
    """Schema for support analytics response (read)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_at: Optional[datetime] = None


class SupportAnalyticsSummary(BaseModel):
    """Schema for aggregated analytics summary."""
    total_tickets: int = 0
    resolved_tickets: int = 0
    open_tickets: int = 0
    avg_response_time_minutes: Optional[float] = None
    avg_resolution_time_minutes: Optional[float] = None
    ai_resolution_rate: Optional[float] = None
    customer_satisfaction: Optional[float] = None
    tickets_by_source: Dict[str, int] = Field(default_factory=dict)
    tickets_by_priority: Dict[str, int] = Field(default_factory=dict)
    tickets_by_status: Dict[str, int] = Field(default_factory=dict)


class SupportAnalyticsDateRange(BaseModel):
    """Schema for analytics date range request."""
    start_date: datetime
    end_date: datetime


# ===========================================================================
# Conversation (Unified Multi-Channel) Schemas
# ===========================================================================

class ConversationMessage(BaseModel):
    """Schema for a message in a unified conversation view."""
    id: int
    sender_type: str
    sender_name: Optional[str] = None
    content: str
    ai_generated: bool = False
    sentiment: Optional[str] = None
    created_at: datetime


class ConversationSummary(BaseModel):
    """Schema for conversation summary in unified view."""
    ticket_id: int
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    source: str
    subject: str
    status: str
    priority: str
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    ai_handled: bool = False


class ConversationReplyRequest(BaseModel):
    """Schema for replying to a conversation."""
    content: str = Field(..., min_length=1)
    use_ai: bool = False


class ConversationReplyResponse(BaseModel):
    """Schema for conversation reply response."""
    success: bool
    message_id: Optional[int] = None
    ticket_id: int
    ai_generated: bool = False
    content: str
    requires_approval: bool = False
    audit_log_id: Optional[int] = None
    confidence: Optional[float] = None
    suggested_human_takeover: bool = False
    forbidden_triggered: bool = False


class ConversationListResponse(BaseModel):
    """Schema for paginated conversation list response."""
    items: List[ConversationSummary]
    total: int
    page: int
    page_size: int


# ===========================================================================
# Sentiment Analysis Schemas
# ===========================================================================

class SentimentAnalysisRequest(BaseModel):
    """Schema for sentiment analysis request."""
    text: str = Field(..., min_length=1, max_length=10000)


class SentimentAnalysisResponse(BaseModel):
    """Schema for sentiment analysis response."""
    sentiment: str = Field(..., pattern="^(positive|negative|neutral)$")
    score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)


# ===========================================================================
# Ticket Categorization Schemas
# ===========================================================================

class CategorizationRequest(BaseModel):
    """Schema for ticket categorization request."""
    subject: str = Field(..., max_length=500)
    content: Optional[str] = None


class CategorizationResponse(BaseModel):
    """Schema for ticket categorization response."""
    category: str = Field(..., pattern="^(billing|technical|sales|general)$")
    confidence: float = Field(..., ge=0.0, le=1.0)


# ===========================================================================
# AI Reply Audit Log Schemas
# ===========================================================================

class AIReplyAuditLogResponse(BaseModel):
    """Schema for AI reply audit log entry."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    company_id: int
    original_content: str
    filtered_content: Optional[str] = None
    confidence: Optional[float] = None
    kb_articles_used: List[int] = Field(default_factory=list)
    status: str = Field(..., pattern="^(pending|approved|rejected|auto_sent|filtered)$")
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    forbidden_triggered: bool = False
    forbidden_keywords_found: List[str] = Field(default_factory=list)
    forbidden_patterns_found: List[str] = Field(default_factory=list)
    detected_sentiment: Optional[str] = None
    suggested_human_takeover: bool = False
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None
    created_at: Optional[datetime] = None


class AIReplyApprovalRequest(BaseModel):
    """Schema for approving or rejecting an AI reply."""
    action: str = Field(..., pattern="^(approve|reject|approve_and_send)$")
    note: Optional[str] = None


class AIReplyApprovalResponse(BaseModel):
    """Schema for AI reply approval response."""
    success: bool
    message: str
    audit_log_id: int
    ticket_id: int
    action: str


# ===========================================================================
# RAG Context Schemas
# ===========================================================================

class RAGContextRequest(BaseModel):
    """Schema for RAG context retrieval request."""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    company_id: int


class RAGContextResponse(BaseModel):
    """Schema for RAG context retrieval response."""
    context: str
    articles_used: List[int] = Field(default_factory=list)
    relevance_scores: Dict[int, float] = Field(default_factory=dict)
