"""
AI Architecture router.

Provides 18 endpoints for the AI module:
- Prompt template CRUD (5 endpoints)
- AI completion generation (1 endpoint)
- Suggestions (3 endpoints)
- Recommendations (4 endpoints)
- Usage analytics (1 endpoint)
- Conversations and messages (4 endpoints)

All endpoints require authentication and enforce tenant isolation
via company_id and branch_id from the current user.

Router prefix: /api/v2/ai (registered in main.py)
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import (
    CACHE_TTL_COMPLETION,
    MAX_SUGGESTIONS_PER_REQUEST,
    RECOMMENDATION_CATEGORIES,
    SUGGESTION_TRIGGER_TYPES,
)
from app.ai.models import (
    AIConversation,
    AIMessage,
    AIModelName,
    AIPrompt,
    AIRecommendation,
    AISuggestion,
    AIUsageLog,
    ConversationStatus,
    MessageRole,
)
from app.ai.schemas import (
    AIConversationCreate,
    AIConversationListResponse,
    AIConversationResponse,
    AIErrorResponse,
    AIGenerateRequest,
    AIGenerateResponse,
    AIMessageResponse,
    AIPromptCreate,
    AIPromptListResponse,
    AIPromptResponse,
    AIPromptUpdate,
    AIRecommendationCreate,
    AIRecommendationListResponse,
    AIRecommendationResponse,
    AISendMessageRequest,
    AISendMessageResponse,
    AISuggestionCreate,
    AISuggestionFeedback,
    AISuggestionListResponse,
    AISuggestionResponse,
    AIUsageFilter,
    AIUsageListResponse,
    AIUsageResponse,
    AIUsageSummary,
)
from app.ai.service import (
    AICacheService,
    AIUsageTracker,
    CircuitBreaker,
    ConversationService,
    OpenAIService,
    PromptTemplateService,
    RecommendationEngine,
    AISuggestionService,
)
from app.auth.models import User
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_company_branch(user: User) -> tuple:
    """Extract company_id and branch_id from the current user.

    Args:
        user: The authenticated user.

    Returns:
        Tuple of (company_id, branch_id).

    Raises:
        ValidationError: If company_id is not set.
    """
    if user.company_id is None:
        raise ValidationError("User must belong to a company")
    return user.company_id, user.branch_id


def _model_to_dict(instance: Any) -> Dict[str, Any]:
    """Convert a SQLAlchemy model instance to a dict.

    Args:
        instance: SQLAlchemy model instance.

    Returns:
        Dictionary of column names to values.
    """
    from sqlalchemy import inspect

    mapper = inspect(instance.__class__)
    return {
        col.key: getattr(instance, col.key)
        for col in mapper.mapper.column_attrs
    }


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------


@router.post(
    "/prompts",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AI prompt template",
)
async def create_prompt(
    data: AIPromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new reusable AI prompt template.

    Args:
        data: Prompt template data.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Created prompt template.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = PromptTemplateService(db)
    data_dict = data.model_dump()
    data_dict["company_id"] = company_id
    data_dict["branch_id"] = branch_id

    prompt = await service.create_prompt(data_dict)
    return {"success": True, "data": AIPromptResponse.model_validate(prompt).model_dump()}


@router.get(
    "/prompts",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List AI prompt templates",
)
async def list_prompts(
    active_only: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List AI prompt templates for the current company.

    Args:
        active_only: Filter to active prompts only.
        page: Page number.
        page_size: Items per page.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Paginated list of prompt templates.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = PromptTemplateService(db)
    prompts, total = await service.list_prompts(
        company_id=company_id,
        branch_id=branch_id,
        active_only=active_only,
        page=page,
        page_size=page_size,
    )

    items = [AIPromptResponse.model_validate(p).model_dump() for p in prompts]
    return {
        "success": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get(
    "/prompts/{prompt_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get a prompt template by ID",
)
async def get_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a single AI prompt template by ID.

    Args:
        prompt_id: The prompt template ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The prompt template.
    """
    company_id, _ = _get_company_branch(current_user)

    service = PromptTemplateService(db)
    prompt = await service.get_prompt(prompt_id, company_id)
    return {"success": True, "data": AIPromptResponse.model_validate(prompt).model_dump()}


@router.put(
    "/prompts/{prompt_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update a prompt template",
)
async def update_prompt(
    prompt_id: int,
    data: AIPromptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update an AI prompt template.

    Args:
        prompt_id: The prompt template ID.
        data: Updated fields.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The updated prompt template.
    """
    company_id, _ = _get_company_branch(current_user)

    service = PromptTemplateService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    prompt = await service.update_prompt(prompt_id, company_id, update_data)
    return {"success": True, "data": AIPromptResponse.model_validate(prompt).model_dump()}


@router.delete(
    "/prompts/{prompt_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Soft delete a prompt template",
)
async def delete_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Soft delete (deactivate) an AI prompt template.

    Args:
        prompt_id: The prompt template ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Success response.
    """
    company_id, _ = _get_company_branch(current_user)

    service = PromptTemplateService(db)
    await service.delete_prompt(prompt_id, company_id)
    return {"success": True, "detail": f"Prompt {prompt_id} deleted"}


# ---------------------------------------------------------------------------
# AI Generation
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Generate an AI completion",
)
async def generate_completion(
    request_data: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate an AI completion with caching, usage tracking, and cost estimation.

    Checks the cache first if use_cache is True. Supports prompt templates
    with variable substitution. Logs usage after generation with supervised mode flag.

    Args:
        request_data: Generation request parameters.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The AI completion response with metadata.
    """
    company_id, branch_id = _get_company_branch(current_user)

    model = request_data.model or "gpt-4o-mini"
    prompt = request_data.prompt
    use_cache = request_data.use_cache
    prompt_id = request_data.prompt_id
    variables = request_data.variables or {}

    # ------------------------------------------------------------------
    # 1. Graceful fallback: API key missing
    # ------------------------------------------------------------------
    from app.config import settings
    if not getattr(settings, "OPENAI_API_KEY", None):
        return {
            "success": False,
            "data": {
                "content": "AI servisi yapilandirilmamis. Lutfen yoneticinize basvurun.",
                "model": model,
                "fallback": True,
                "error": "AI_API_KEY_MISSING",
                "supervised": True,
            },
            "error": "AI_API_KEY_MISSING",
        }

    # ------------------------------------------------------------------
    # 2. Branch-aware prompt template resolution
    # ------------------------------------------------------------------
    system_prompt = request_data.system_prompt
    if prompt_id or not system_prompt:
        prompt_service = PromptTemplateService(db)
        branch_prompt = await prompt_service.get_branch_aware_prompt(
            company_id=company_id,
            branch_id=branch_id,
            prompt_id=prompt_id,
        )
        if branch_prompt:
            if branch_prompt.system_prompt:
                system_prompt = branch_prompt.system_prompt
            # Render user prompt template with variables
            if branch_prompt.user_prompt_template:
                rendered = prompt_service.render_template(
                    branch_prompt.user_prompt_template, variables
                )
                # Merge rendered template with user prompt
                if rendered.strip():
                    prompt = f"{rendered}\n\nKullanici mesaji:\n{prompt}"
            model = branch_prompt.model_name.value

    # ------------------------------------------------------------------
    # 3. Check cache
    # ------------------------------------------------------------------
    cache_service = AICacheService()
    if use_cache:
        cached = await cache_service.get_cached_response(model, prompt)
        if cached:
            return {"success": True, "data": cached}

    # ------------------------------------------------------------------
    # 4. Build messages
    # ------------------------------------------------------------------
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        from app.ai.constants import DEFAULT_SYSTEM_PROMPT
        messages.append({"role": "system", "content": DEFAULT_SYSTEM_PROMPT})
    messages.append({"role": "user", "content": prompt})

    # ------------------------------------------------------------------
    # 5. Cost estimation (pre-request)
    # ------------------------------------------------------------------
    openai_service = OpenAIService()
    cost_estimate = openai_service.estimate_request_cost(
        messages=messages, model=model, max_tokens=request_data.max_tokens
    )

    # ------------------------------------------------------------------
    # 6. Call OpenAI with full orchestration
    # ------------------------------------------------------------------
    result = await openai_service.create_chat_completion(
        messages=messages,
        model=model,
        temperature=request_data.temperature,
        max_tokens=request_data.max_tokens,
        company_id=company_id,
        user_id=current_user.id,
        branch_id=branch_id,
        prompt_id=prompt_id,
        db=db,
    )

    # Handle graceful fallback responses
    is_fallback = result.get("fallback", False)
    req_status = "success" if not is_fallback else "fallback"

    # ------------------------------------------------------------------
    # 7. Log usage (every API call: tokens, cost, latency, supervised)
    # ------------------------------------------------------------------
    usage_tracker = AIUsageTracker(db)
    await usage_tracker.log_usage(
        company_id=company_id,
        user_id=current_user.id,
        model=result["model"],
        endpoint="/v1/chat/completions",
        tokens_input=result["tokens_input"],
        tokens_output=result["tokens_output"],
        cost_estimate=result["cost_estimate"],
        latency_ms=result["latency_ms"],
        status=req_status,
        branch_id=branch_id,
        supervised_mode=result.get("supervised", True),
        request_metadata={
            "prompt_id": prompt_id,
            "cost_estimate_pre": result.get("cost_estimate_pre"),
            "moderation": result.get("moderation") is not None,
            "cache_used": False,
            "fallback": is_fallback,
            "error": result.get("error"),
        },
    )

    # Return fallback response directly
    if is_fallback:
        return {
            "success": False,
            "data": {
                "content": result["content"],
                "model": result["model"],
                "fallback": True,
                "error": result.get("error"),
                "supervised": result.get("supervised", True),
            },
            "error": result.get("error"),
        }

    # ------------------------------------------------------------------
    # 8. Cache the response (TTL: 1 hour)
    # ------------------------------------------------------------------
    if use_cache:
        cache_service = AICacheService()
        await cache_service.cache_response(
            model=model,
            prompt=prompt,
            response=result["content"],
            tokens=result["total_tokens"],
            ttl=CACHE_TTL_COMPLETION,
        )

    response_data = {
        "content": result["content"],
        "model": result["model"],
        "tokens_used": result["total_tokens"],
        "tokens_input": result["tokens_input"],
        "tokens_output": result["tokens_output"],
        "cost_estimate": result["cost_estimate"],
        "cost_estimate_pre": result.get("cost_estimate_pre"),
        "latency_ms": result["latency_ms"],
        "cached": False,
        "finish_reason": result.get("finish_reason"),
        "supervised": result.get("supervised", True),
        "requires_approval": result.get("requires_approval", True),
    }

    return {"success": True, "data": response_data}


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


@router.post(
    "/suggestions",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI suggestions for context",
)
async def generate_suggestions(
    request_data: AISuggestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate AI marketing suggestions for a given context.

    Args:
        request_data: Suggestion generation parameters.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of generated suggestions.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = AISuggestionService(db)
    suggestions = await service.generate_suggestions(
        company_id=company_id,
        branch_id=branch_id,
        trigger_type=request_data.trigger_type,
        context=request_data.context or {},
        count=min(request_data.count, MAX_SUGGESTIONS_PER_REQUEST),
    )

    items = [AISuggestionResponse.model_validate(s).model_dump() for s in suggestions]
    return {"success": True, "data": {"items": items, "total": len(items)}}


@router.get(
    "/suggestions",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List AI suggestions",
)
async def list_suggestions(
    trigger_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List AI suggestions for the current company.

    Args:
        trigger_type: Optional trigger type filter.
        page: Page number.
        page_size: Items per page.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Paginated list of suggestions.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = AISuggestionService(db)
    suggestions, total = await service.list_suggestions(
        company_id=company_id,
        branch_id=branch_id,
        trigger_type=trigger_type,
        page=page,
        page_size=page_size,
    )

    items = [AISuggestionResponse.model_validate(s).model_dump() for s in suggestions]
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post(
    "/suggestions/{suggestion_id}/feedback",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit feedback for a suggestion",
)
async def submit_suggestion_feedback(
    suggestion_id: int,
    data: AISuggestionFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Submit user feedback for an AI suggestion.

    Args:
        suggestion_id: The suggestion ID.
        data: Feedback data.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The updated suggestion.
    """
    company_id, _ = _get_company_branch(current_user)

    service = AISuggestionService(db)
    suggestion = await service.submit_feedback(
        suggestion_id=suggestion_id,
        company_id=company_id,
        feedback=data.feedback,
        notes=data.notes,
    )
    return {"success": True, "data": AISuggestionResponse.model_validate(suggestion).model_dump()}


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List AI recommendations",
)
async def list_recommendations(
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List AI recommendations for the current company.

    Args:
        category: Optional category filter.
        status: Optional status filter.
        page: Page number.
        page_size: Items per page.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Paginated list of recommendations.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = RecommendationEngine(db)
    recommendations, total = await service.list_recommendations(
        company_id=company_id,
        branch_id=branch_id,
        category=category,
        status=status,
        page=page,
        page_size=page_size,
    )

    items = [AIRecommendationResponse.model_validate(r).model_dump() for r in recommendations]
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post(
    "/recommendations/generate",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Generate new AI recommendations",
)
async def generate_recommendations(
    request_data: AIRecommendationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generate new AI marketing recommendations based on analytics data.

    Args:
        request_data: Recommendation generation parameters.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of generated recommendations.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = RecommendationEngine(db)
    recommendations = await service.generate_recommendations(
        company_id=company_id,
        branch_id=branch_id,
        categories=request_data.categories,
        context=request_data.context or {},
        count=request_data.count,
    )

    items = [AIRecommendationResponse.model_validate(r).model_dump() for r in recommendations]
    return {"success": True, "data": {"items": items, "total": len(items)}}


@router.post(
    "/recommendations/{recommendation_id}/apply",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Mark a recommendation as applied",
)
async def apply_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark an AI recommendation as applied.

    Args:
        recommendation_id: The recommendation ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The updated recommendation.
    """
    company_id, _ = _get_company_branch(current_user)

    service = RecommendationEngine(db)
    rec = await service.apply_recommendation(recommendation_id, company_id)
    return {"success": True, "data": AIRecommendationResponse.model_validate(rec).model_dump()}


@router.post(
    "/recommendations/{recommendation_id}/dismiss",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Mark a recommendation as dismissed",
)
async def dismiss_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark an AI recommendation as dismissed.

    Args:
        recommendation_id: The recommendation ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The updated recommendation.
    """
    company_id, _ = _get_company_branch(current_user)

    service = RecommendationEngine(db)
    rec = await service.dismiss_recommendation(recommendation_id, company_id)
    return {"success": True, "data": AIRecommendationResponse.model_validate(rec).model_dump()}


# ---------------------------------------------------------------------------
# Usage Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/usage",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get AI usage analytics",
)
async def get_usage_analytics(
    user_id: Optional[int] = Query(default=None),
    model: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    summary_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role([
            "super_admin", "company_admin", "branch_manager", "analyst"
        ])
    ),
) -> Dict[str, Any]:
    """Get AI usage analytics and logs.

    Requires admin, manager, or analyst role.

    Args:
        user_id: Optional user ID filter.
        model: Optional model name filter.
        start_date: Optional start date (ISO format).
        end_date: Optional end date (ISO format).
        page: Page number.
        page_size: Items per page.
        summary_only: Return only summary without individual logs.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Usage analytics data with optional log entries.
    """
    company_id, _ = _get_company_branch(current_user)

    usage_tracker = AIUsageTracker(db)

    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Get summary
    summary = await usage_tracker.get_usage_summary(
        company_id=company_id,
        user_id=user_id,
        model=model,
        start_date=start_dt,
        end_date=end_dt,
    )

    response_data: Dict[str, Any] = {"summary": summary}

    if not summary_only:
        logs, total = await usage_tracker.list_usage_logs(
            company_id=company_id,
            user_id=user_id,
            model=model,
            page=page,
            page_size=page_size,
        )
        log_items = [AIUsageResponse.model_validate(l).model_dump() for l in logs]
        response_data["logs"] = {
            "items": log_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return {"success": True, "data": response_data}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@router.get(
    "/conversations",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List AI conversations",
)
async def list_conversations(
    status: Optional[str] = Query(default="active"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """List AI conversations for the current user.

    Args:
        status: Conversation status filter.
        page: Page number.
        page_size: Items per page.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Paginated list of conversations.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = ConversationService(db)
    conversations, total = await service.list_conversations(
        company_id=company_id,
        branch_id=branch_id,
        user_id=current_user.id,
        status=status or "active",
        page=page,
        page_size=page_size,
    )

    items = [AIConversationResponse.model_validate(c).model_dump() for c in conversations]
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post(
    "/conversations",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Start a new AI conversation",
)
async def create_conversation(
    data: AIConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start a new AI conversation.

    Args:
        data: Conversation creation data.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The created conversation.
    """
    company_id, branch_id = _get_company_branch(current_user)

    service = ConversationService(db)
    conversation = await service.create_conversation(
        company_id=company_id,
        branch_id=branch_id,
        user_id=current_user.id,
        title=data.title,
        model=data.model,
        prompt_id=data.prompt_id,
    )
    return {
        "success": True,
        "data": AIConversationResponse.model_validate(conversation).model_dump(),
    }


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Send a message in a conversation",
)
async def send_message(
    conversation_id: int,
    data: AISendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Send a message in a conversation and get an AI response.

    Streaming support is available via the `stream` flag.

    Args:
        conversation_id: The conversation ID.
        data: Message data.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        The user message and AI response.
    """
    company_id, _ = _get_company_branch(current_user)

    # Check if streaming is requested
    if data.stream:
        # [NOT IMPLEMENTED v1.0] Streaming responses require SSE endpoint
        # Planned for future release: /conversations/{id}/messages/stream
        return {
            "success": False,
            "data": {
                "streaming": False,
                "message": "Streaming is not implemented in this version. Use non-streaming requests.",
            },
            "error": "STREAMING_NOT_IMPLEMENTED",
        }

    service = ConversationService(db)
    user_msg, assistant_msg = await service.send_message(
        conversation_id=conversation_id,
        company_id=company_id,
        user_id=current_user.id,
        content=data.content,
    )

    return {
        "success": True,
        "data": {
            "user_message": AIMessageResponse.model_validate(user_msg).model_dump(),
            "assistant_message": AIMessageResponse.model_validate(assistant_msg).model_dump(),
        },
    }


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get messages in a conversation",
)
async def get_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get all messages in a conversation.

    Args:
        conversation_id: The conversation ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of messages.
    """
    company_id, _ = _get_company_branch(current_user)

    # Verify the conversation belongs to the user
    service = ConversationService(db)
    conversation = await service.get_conversation(
        conversation_id, company_id, current_user.id
    )

    # Get messages
    from sqlalchemy import select
    from app.ai.models import AIMessage

    result = await db.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at)
    )
    messages = result.scalars().all()

    items = [AIMessageResponse.model_validate(m).model_dump() for m in messages]
    return {"success": True, "data": {"items": items, "total": len(items)}}


@router.delete(
    "/conversations/{conversation_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Soft delete a conversation.

    Args:
        conversation_id: The conversation ID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Success response.
    """
    company_id, _ = _get_company_branch(current_user)

    service = ConversationService(db)
    await service.delete_conversation(
        conversation_id=conversation_id,
        company_id=company_id,
        user_id=current_user.id,
    )
    return {"success": True, "detail": f"Conversation {conversation_id} deleted"}


# ---------------------------------------------------------------------------
# AI Health & Diagnostics
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="AI service health check",
)
async def ai_health_check(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check AI service health status.

    Returns API key status, circuit breaker state, cache connectivity,
    and quota summary for the current company.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Health status with component diagnostics.
    """
    company_id, _ = _get_company_branch(current_user)

    from app.config import settings

    # Check API key
    api_key_configured = bool(getattr(settings, "OPENAI_API_KEY", ""))

    # Check circuit breaker
    cb = CircuitBreaker()

    # Check company quota
    usage_tracker = AIUsageTracker(db)
    within_quota, quota_info = await usage_tracker.check_company_quota(
        company_id=company_id,
    )

    # Check cache connectivity
    cache_status = "unknown"
    try:
        cache_service = AICacheService()
        cache_stats = await cache_service.get_cache_stats()
        cache_status = "connected"
    except Exception:
        cache_status = "disconnected"

    return {
        "success": True,
        "data": {
            "api_key_configured": api_key_configured,
            "circuit_breaker": {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "can_execute": cb.can_execute(),
            },
            "quota": quota_info,
            "cache": {
                "status": cache_status,
                "stats": cache_stats if cache_status == "connected" else None,
            },
            "supervised_mode": getattr(settings, "AI_SUPERVISED_MODE", True),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


@router.get(
    "/cache-stats",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get AI cache statistics",
)
async def get_cache_statistics(
    current_user: User = Depends(
        require_role([
            "super_admin", "company_admin", "branch_manager", "analyst"
        ])
    ),
) -> Dict[str, Any]:
    """Get AI cache statistics for monitoring.

    Requires admin, manager, or analyst role.

    Args:
        current_user: Authenticated user.

    Returns:
        Cache statistics including entries, hit rates, and cost savings.
    """
    cache_service = AICacheService()
    stats = await cache_service.get_cache_stats()
    return {"success": True, "data": stats}
