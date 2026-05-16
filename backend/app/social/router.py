"""FastAPI router for the social media integration module.

All endpoints are prefixed with /api/v2/social by main.py registration.
Provides CRUD for accounts, posts, comments, messages, analytics,
competitors, and webhook handling.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import ValidationError

from .schemas import (
    AIReplySuggestion,
    AnalyticsDashboard,
    CommentMarkReadResponse,
    CommentReplyRequest,
    CommentReplyResponse,
    ConversationListResponse,
    ConversationSyncResponse,
    HashtagIntelligenceCreate,
    HashtagIntelligenceListResponse,
    HashtagIntelligenceResponse,
    HashtagIntelligenceUpdate,
    HashtagSuggestionRequest,
    HashtagSuggestionResponse,
    ListeningCheckResult,
    MarkReadResponse,
    MessageReplyRequest,
    MessageReplyResponse,
    PublishNowRequest,
    PublishNowResponse,
    PublishingQueueCreate,
    PublishingQueueListResponse,
    PublishingQueueResponse,
    PublishingQueueUpdate,
    QueueProcessResult,
    SentimentAnalysisResult,
    SocialAccountCreate,
    SocialAccountListResponse,
    SocialAccountResponse,
    SocialAccountUpdate,
    SocialAnalyticsCreate,
    SocialAnalyticsListResponse,
    SocialCommentListResponse,
    SocialCommentResponse,
    SocialCommentUpdate,
    SocialCompetitorCreate,
    SocialCompetitorListResponse,
    SocialCompetitorResponse,
    SocialCompetitorUpdate,
    SocialListeningCreate,
    SocialListeningListResponse,
    SocialListeningResponse,
    SocialListeningUpdate,
    SocialMessageResponse,
    SocialMessageResponse,
    SocialPostCreate,
    SocialPostListResponse,
    SocialPostResponse,
    SocialPostUpdate,
    TokenRefreshRequest,
    TokenRefreshResponse,
    WebhookEventListResponse,
    WebhookProcessingStatus,
    WebhookSignatureVerifyRequest,
    WebhookSignatureVerifyResponse,
    WebhookVerifyResponse,
)
from .service import (
    AnalyticsService,
    CommentService,
    CompetitorService,
    CredentialManager,
    HashtagIntelligenceService,
    InboundMessageService,
    MessageService,
    OutboundMessageService,
    PostService,
    PublishingQueueService,
    SocialAccountService,
    SocialListeningService,
    TelegramClient,
    WebhookService,
    WhatsAppClient,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["social"])


# =============================================================================
# Account Endpoints
# =============================================================================


@router.post(
    "/accounts",
    response_model=SocialAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a new social media account",
    description="Connect a new social media account with OAuth tokens. Tokens are encrypted at rest.",
)
async def create_account(
    data: SocialAccountCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Connect a new social media account.

    Encrypts and stores OAuth credentials. Validates tokens with the platform API.
    """
    service = SocialAccountService(db)
    account = await service.create_account(
        company_id=user.company_id,
        data=data,
        branch_id=user.branch_id,
    )
    return account


@router.get(
    "/accounts",
    response_model=SocialAccountListResponse,
    summary="List connected social accounts",
    description="List all connected social media accounts for the current tenant.",
)
async def list_accounts(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List connected social media accounts."""
    service = SocialAccountService(db)
    result = await service.list_accounts(
        company_id=user.company_id,
        platform=platform,
        status=status,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/accounts/{account_id}",
    response_model=SocialAccountResponse,
    summary="Get a social account by ID",
    description="Get detailed information about a connected social account.",
)
async def get_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a social account by ID."""
    service = SocialAccountService(db)
    account = await service.get_account(account_id, user.company_id)
    return account


@router.patch(
    "/accounts/{account_id}",
    response_model=SocialAccountResponse,
    summary="Update a social account",
    description="Update account name, profile URL, or settings.",
)
async def update_account(
    account_id: int,
    data: SocialAccountUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a social account."""
    service = SocialAccountService(db)
    account = await service.update_account(account_id, user.company_id, data)
    return account


@router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect a social account",
    description="Disconnect and remove a social account and all associated data.",
)
async def delete_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect and delete a social account."""
    service = SocialAccountService(db)
    await service.delete_account(account_id, user.company_id)


@router.post(
    "/accounts/{account_id}/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh account access token",
    description="Manually refresh an account's OAuth access token.",
)
async def refresh_account_token(
    account_id: int,
    request_data: TokenRefreshRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh an account's access token."""
    service = SocialAccountService(db)
    result = await service.refresh_account_token(
        account_id=account_id,
        company_id=user.company_id,
        force=request_data.force,
    )
    return TokenRefreshResponse(
        success=result.get("success", False),
        expires_at=result.get("expires_at"),
        message=result.get("message", ""),
    )


@router.get(
    "/accounts/{account_id}/analytics",
    response_model=dict[str, object],
    summary="Get account-specific analytics",
    description="Fetch and sync analytics for a specific connected account.",
)
async def get_account_analytics(
    account_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get analytics for a specific account."""
    service = AnalyticsService(db)
    result = await service.sync_account_analytics(user.company_id, account_id)
    return result


# =============================================================================
# Post Endpoints
# =============================================================================


@router.post(
    "/posts",
    response_model=SocialPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new social post",
    description="Create a new social post (draft or scheduled).",
)
async def create_post(
    data: SocialPostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new social post."""
    service = PostService(db)
    post = await service.create_post(
        company_id=user.company_id,
        data=data,
        branch_id=user.branch_id,
    )
    return post


@router.get(
    "/posts",
    response_model=SocialPostListResponse,
    summary="List social posts",
    description="List all social posts for the current tenant.",
)
async def list_posts(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    status: Optional[str] = Query(None, description="Filter by status"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List social posts."""
    service = PostService(db)
    result = await service.list_posts(
        company_id=user.company_id,
        account_id=account_id,
        status=status,
        platform=platform,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/posts/{post_id}",
    response_model=SocialPostResponse,
    summary="Get a post by ID",
    description="Get detailed information about a social post.",
)
async def get_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a social post by ID."""
    service = PostService(db)
    post = await service.get_post(post_id, user.company_id)
    return post


@router.put(
    "/posts/{post_id}",
    response_model=SocialPostResponse,
    summary="Update a post",
    description="Update a draft or scheduled post. Published posts cannot be edited.",
)
async def update_post(
    post_id: int,
    data: SocialPostUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a social post."""
    service = PostService(db)
    post = await service.update_post(post_id, user.company_id, data)
    return post


@router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a post",
    description="Delete a social post.",
)
async def delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a social post."""
    service = PostService(db)
    await service.delete_post(post_id, user.company_id)


@router.post(
    "/posts/{post_id}/publish",
    response_model=PublishNowResponse,
    summary="Publish a post immediately",
    description="Publish a draft or scheduled post immediately via the platform API.",
)
async def publish_now(
    post_id: int,
    request_data: PublishNowRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Publish a post immediately."""
    service = PostService(db)
    result = await service.publish_now(post_id, user.company_id)
    return PublishNowResponse(
        success=result.get("success", False),
        external_post_id=result.get("external_post_id"),
        message=result.get("message", ""),
    )


# =============================================================================
# Comment Endpoints
# =============================================================================


@router.get(
    "/comments",
    response_model=SocialCommentListResponse,
    summary="List comments",
    description="List all social media comments for the current tenant.",
)
async def list_comments(
    post_id: Optional[int] = Query(None, description="Filter by post"),
    status: Optional[str] = Query(None, description="Filter by status"),
    account_id: Optional[int] = Query(None, description="Filter by account"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List social media comments."""
    service = CommentService(db)
    result = await service.list_comments(
        company_id=user.company_id,
        post_id=post_id,
        status=status,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/comments/{comment_id}",
    response_model=SocialCommentResponse,
    summary="Get a comment by ID",
    description="Get a specific comment.",
)
async def get_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a comment by ID."""
    service = CommentService(db)
    comment = await service.get_comment(comment_id, user.company_id)
    return comment


@router.patch(
    "/comments/{comment_id}",
    response_model=SocialCommentResponse,
    summary="Update a comment",
    description="Update comment status or sentiment.",
)
async def update_comment(
    comment_id: int,
    data: SocialCommentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a comment."""
    service = CommentService(db)
    comment = await service.update_comment(comment_id, user.company_id, data)
    return comment


@router.post(
    "/comments/{comment_id}/reply",
    response_model=CommentReplyResponse,
    summary="Reply to a comment",
    description="Reply to a comment via the platform API.",
)
async def reply_to_comment(
    comment_id: int,
    data: CommentReplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reply to a comment via the platform API."""
    service = CommentService(db)
    result = await service.reply_to_comment(
        comment_id=comment_id,
        company_id=user.company_id,
        reply_content=data.reply_content,
    )
    return CommentReplyResponse(
        success=result.get("success", False),
        reply_id=result.get("reply_id"),
        message=result.get("message", ""),
    )


@router.put(
    "/comments/{comment_id}/read",
    response_model=CommentMarkReadResponse,
    summary="Mark a comment as read",
    description="Mark a comment as read.",
)
async def mark_comment_read(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a comment as read."""
    service = CommentService(db)
    result = await service.mark_as_read(comment_id, user.company_id)
    return CommentMarkReadResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
    )


@router.post(
    "/comments/{comment_id}/sentiment",
    response_model=Dict[str, str],
    summary="Analyze comment sentiment",
    description="Analyze the sentiment of a comment using AI.",
)
async def analyze_comment_sentiment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze comment sentiment."""
    service = CommentService(db)
    result = await service.analyze_sentiment(comment_id, user.company_id)
    return result


@router.post(
    "/comments/sync/{account_id}",
    response_model=Dict[str, int],
    summary="Sync comments from platform",
    description="Sync comments from a platform account.",
)
async def sync_comments(
    account_id: int,
    post_id: Optional[int] = Query(None, description="Specific post to sync"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sync comments from a platform."""
    service = CommentService(db)
    result = await service.sync_comments(
        company_id=user.company_id,
        account_id=account_id,
        post_id=post_id,
    )
    return result


# =============================================================================
# Message Endpoints
# =============================================================================


@router.get(
    "/messages",
    response_model=SocialMessageResponse,
    summary="List messages",
    description="List all direct messages for the current tenant.",
)
async def list_messages(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List messages."""
    service = MessageService(db)
    result = await service.list_messages(
        company_id=user.company_id,
        account_id=account_id,
        platform=platform,
        status=status,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/messages/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="List conversation summaries for the current tenant.",
)
async def list_conversations(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List conversation summaries."""
    service = MessageService(db)
    result = await service.list_conversations(
        company_id=user.company_id,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/messages/{message_id}",
    response_model=SocialMessageResponse,
    summary="Get a message by ID",
    description="Get a specific message.",
)
async def get_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a message by ID."""
    service = MessageService(db)
    message = await service.get_message(message_id, user.company_id)
    return message


@router.post(
    "/messages/{message_id}/reply",
    response_model=MessageReplyResponse,
    summary="Reply to a conversation",
    description="Reply to a conversation via the platform API.",
)
async def reply_to_conversation(
    message_id: int,
    data: MessageReplyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reply to a conversation."""
    service = MessageService(db)
    result = await service.reply_to_conversation(
        message_id=message_id,
        company_id=user.company_id,
        reply_content=data.reply_content,
    )
    return MessageReplyResponse(
        success=result.get("success", False),
        message_id=result.get("message_id"),
        message=result.get("message", ""),
    )


@router.post(
    "/messages/{message_id}/read",
    response_model=MarkReadResponse,
    summary="Mark conversation as read",
    description="Mark all messages in a conversation as read and send read receipt.",
)
async def mark_conversation_read(
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a conversation as read."""
    service = MessageService(db)
    message = await service.get_message(message_id, user.company_id)
    result = await service.mark_conversation_as_read(
        conversation_id=message.external_conversation_id,
        company_id=user.company_id,
        account_id=message.account_id,
    )
    return MarkReadResponse(**result)


@router.post(
    "/messages/{message_id}/sentiment",
    response_model=SentimentAnalysisResult,
    summary="Analyze message sentiment",
    description="Analyze the sentiment of a message. Negative sentiment triggers escalation.",
)
async def analyze_message_sentiment_endpoint(
    message_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze sentiment of a message."""
    service = MessageService(db)
    result = await service.analyze_message_sentiment(message_id, user.company_id)
    return SentimentAnalysisResult(**result)


@router.post(
    "/messages/{message_id}/ai-reply",
    response_model=AIReplySuggestion,
    summary="Generate AI reply suggestion",
    description=(
        "Generate an AI-powered reply suggestion for a conversation. "
        "Auto-send is DISABLED by default - suggestions must be reviewed by a human agent."
    ),
)
async def generate_ai_reply_suggestion_endpoint(
    message_id: int,
    tone: str = Query("professional", description="Reply tone: professional, friendly, formal"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate AI reply suggestion (auto-send OFF by default)."""
    service = MessageService(db)
    result = await service.generate_ai_reply_suggestion(
        message_id=message_id,
        company_id=user.company_id,
        tone=tone,
    )
    return AIReplySuggestion(**result)


@router.post(
    "/messages/sync/{account_id}",
    response_model=ConversationSyncResponse,
    summary="Sync conversations from platform",
    description="Sync DM conversations from Instagram or Facebook Messenger.",
)
async def sync_conversations(
    account_id: int,
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sync conversations from a platform account."""
    service = MessageService(db)
    result = await service.sync_conversations(
        company_id=user.company_id,
        account_id=account_id,
        limit=limit,
    )
    return ConversationSyncResponse(**result)


@router.get(
    "/messages/unread/counts",
    response_model=dict[str, object],
    summary="Unread message counts",
    description="Get unread message counts per platform and total.",
)
async def get_unread_counts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get unread message counts."""
    service = MessageService(db)
    result = await service.get_unread_counts(user.company_id)
    return result


@router.post(
    "/webhooks/queue/process",
    response_model=dict[str, object],
    summary="Process queued messages",
    description="Process pending messages from the conversation queue.",
)
async def process_queued_messages_endpoint(
    batch_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Process queued incoming messages."""
    service = MessageService(db)
    result = await service.process_queued_messages(user.company_id, batch_size=batch_size)
    return result


# =============================================================================
# Analytics Endpoints
# =============================================================================


@router.get(
    "/analytics",
    response_model=AnalyticsDashboard,
    summary="Social analytics dashboard",
    description="Get aggregated social media analytics dashboard for the tenant.",
)
async def get_analytics_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the social analytics dashboard."""
    service = AnalyticsService(db)
    dashboard = await service.get_dashboard(user.company_id)
    return dashboard


@router.get(
    "/analytics/snapshots",
    response_model=SocialAnalyticsListResponse,
    summary="List analytics snapshots",
    description="List detailed analytics snapshots.",
)
async def list_analytics_snapshots(
    account_id: Optional[int] = Query(None, description="Filter by account"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List analytics snapshots."""
    service = AnalyticsService(db)
    result = await service.list_analytics(
        company_id=user.company_id,
        account_id=account_id,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return result


@router.post(
    "/analytics/snapshots",
    response_model=dict[str, object],
    status_code=status.HTTP_201_CREATED,
    summary="Create analytics snapshot",
    description="Manually create an analytics snapshot.",
)
async def create_analytics_snapshot(
    data: SocialAnalyticsCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create an analytics snapshot."""
    service = AnalyticsService(db)
    snapshot = await service.create_snapshot(
        company_id=user.company_id,
        data=data,
        branch_id=user.branch_id,
    )
    return {"success": True, "snapshot_id": snapshot.id}


# =============================================================================
# Competitor Endpoints
# =============================================================================


@router.get(
    "/competitors",
    response_model=SocialCompetitorListResponse,
    summary="List tracked competitors",
    description="List all tracked competitor accounts.",
)
async def list_competitors(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List tracked competitors."""
    service = CompetitorService(db)
    result = await service.list_competitors(
        company_id=user.company_id,
        platform=platform,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/competitors/{competitor_id}",
    response_model=SocialCompetitorResponse,
    summary="Get a competitor by ID",
    description="Get detailed information about a tracked competitor.",
)
async def get_competitor(
    competitor_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a competitor by ID."""
    service = CompetitorService(db)
    competitor = await service.get_competitor(competitor_id, user.company_id)
    return competitor


@router.post(
    "/competitors",
    response_model=SocialCompetitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a competitor",
    description="Add a competitor account to track.",
)
async def create_competitor(
    data: SocialCompetitorCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a competitor to track."""
    service = CompetitorService(db)
    competitor = await service.create_competitor(
        company_id=user.company_id,
        data=data,
        branch_id=user.branch_id,
    )
    return competitor


@router.patch(
    "/competitors/{competitor_id}",
    response_model=SocialCompetitorResponse,
    summary="Update a competitor",
    description="Update competitor tracking data.",
)
async def update_competitor(
    competitor_id: int,
    data: SocialCompetitorUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a competitor."""
    service = CompetitorService(db)
    competitor = await service.update_competitor(
        competitor_id, user.company_id, data
    )
    return competitor


@router.delete(
    "/competitors/{competitor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a competitor",
    description="Stop tracking a competitor.",
)
async def delete_competitor(
    competitor_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a competitor."""
    service = CompetitorService(db)
    await service.delete_competitor(competitor_id, user.company_id)


@router.post(
    "/competitors/{competitor_id}/analyze",
    response_model=dict[str, object],
    summary="Analyze a competitor",
    description="Fetch and update metrics for a competitor.",
)
async def analyze_competitor(
    competitor_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze a competitor."""
    service = CompetitorService(db)
    result = await service.analyze_competitor(competitor_id, user.company_id)
    return result


# =============================================================================
# Webhook Endpoints
# =============================================================================


@router.get(
    "/webhooks/{platform}",
    response_model=WebhookVerifyResponse,
    summary="Webhook verification (GET)",
    description="Handle platform webhook verification challenges.",
    include_in_schema=False,
)
async def verify_webhook(
    platform: str,
    request: Request,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
) -> dict:
    """Handle webhook verification from Facebook/Instagram."""
    service = WebhookService(None)  # No DB needed for verification
    result = await service.handle_subscription_verification(
        platform=platform,
        hub_mode=hub_mode,
        hub_verify_token=hub_verify_token,
        hub_challenge=hub_challenge,
        expected_verify_token=getattr(settings, "WEBHOOK_VERIFY_TOKEN", ""),
    )
    if result:
        return WebhookVerifyResponse(challenge=result, message="Webhook verified")
    raise ValidationError("Webhook verification failed")


@router.post(
    "/webhooks/{platform}",
    response_model=dict[str, object],
    summary="Receive webhook events",
    description="Receive and process webhook events from WhatsApp and Telegram. "
                "Validates signatures, parses inbound messages, creates tickets.",
    include_in_schema=False,
)
async def receive_webhook(
    platform: str,
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive webhook events from social platforms.

    Handles webhooks from Facebook, Instagram, WhatsApp, TikTok, Telegram.
    Validates signatures where applicable, parses inbound messages,
    creates/updates support tickets, and triggers AI auto-reply.
    """
    body = await request.body()
    payload = json.loads(body) if body else {}

    # -- 1. Webhook validation --
    if platform in ("facebook", "instagram", "whatsapp"):
        app_secret = getattr(settings, "WHATSAPP_APP_SECRET", "")
        if app_secret and x_hub_signature_256:
            is_valid = WhatsAppClient.validate_webhook_signature(
                body, x_hub_signature_256, app_secret
            )
            if not is_valid:
                raise ValidationError("Invalid webhook signature")

    elif platform == "telegram":
        expected_secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if expected_secret:
            is_valid = TelegramClient.validate_webhook_secret(
                body, x_telegram_bot_api_secret_token or "", expected_secret
            )
            if not is_valid:
                raise ValidationError("Invalid Telegram webhook secret")

    # -- 2. Resolve company/account (branch-based routing) --
    company_id: Optional[int] = None
    account_id: Optional[int] = None
    branch_id: Optional[int] = None

    if platform in ("facebook", "instagram", "whatsapp"):
        entry = payload.get("entry", [{}])[0]
        # Try phone_number_id from metadata first
        changes = entry.get("changes", [{}])[0] if entry.get("changes") else {}
        value = changes.get("value", {}) if isinstance(changes, dict) else {}
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id") or entry.get("id")

        if phone_number_id:
            from sqlalchemy import select
            from .models import SocialAccount

            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.account_id == str(phone_number_id),
                    SocialAccount.platform == platform,
                )
            )
            account = result.scalar_one_or_none()
            if account:
                company_id = account.company_id
                account_id = account.id
                branch_id = account.branch_id

    elif platform == "telegram":
        # Parse update to get chat info
        parsed_update = TelegramClient.parse_inbound_update(payload)
        if parsed_update and parsed_update.get("chat_id"):
            chat_id = str(parsed_update["chat_id"])
            from sqlalchemy import select
            from .models import SocialAccount

            # Match by account_id (the bot's chat/account mapping)
            # or by settings.chat_id for group/channel targets
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.platform == "telegram",
                    SocialAccount.company_id.isnot(None),
                )
            )
            accounts = result.scalars().all()
            for acct in accounts:
                acct_chat_id = (acct.settings or {}).get("chat_id") if acct.settings else None
                if acct_chat_id == chat_id or acct.account_id == chat_id:
                    company_id = acct.company_id
                    account_id = acct.id
                    branch_id = acct.branch_id
                    break

            # Fallback: if no branch-specific match, use company-wide bot
            if not company_id:
                result = await db.execute(
                    select(SocialAccount).where(
                        SocialAccount.platform == "telegram",
                        SocialAccount.branch_id.is_(None),
                    ).order_by(SocialAccount.created_at)
                )
                account = result.scalar_one_or_none()
                if account:
                    company_id = account.company_id
                    account_id = account.id
                    branch_id = account.branch_id

    if not company_id:
        # No matching account - return 200 to stop platform retries
        logger.warning("Webhook received for unknown %s account", platform)
        return {"success": False, "error": "No matching account"}

    # -- 3. Process inbound messages --
    inbound_service = InboundMessageService(db)
    webhook_service = WebhookService(db)

    processed = False

    if platform == "whatsapp":
        # Parse inbound message
        parsed = WhatsAppClient.parse_inbound_message(payload)
        if parsed:
            result = await inbound_service.process_whatsapp_message(
                company_id=company_id,
                account_id=account_id,
                parsed=parsed,
            )
            processed = True

            # Mark message as read on WhatsApp
            try:
                cred_mgr = CredentialManager()
                token = cred_mgr.decrypt_access_token(
                    (await db.execute(
                        select(SocialAccount).where(SocialAccount.id == account_id)
                    )).scalar_one_or_none().access_token
                )
                wa_client = WhatsAppClient(access_token=token, phone_number_id=parsed.get("phone_number_id"))
                await wa_client.mark_message_as_read(parsed["message_id"])
                await wa_client.close()
            except Exception:
                pass  # Non-critical

        # Also check for status updates
        status_update = WhatsAppClient.parse_message_status(payload)
        if status_update:
            logger.info(
                "WhatsApp message %s status: %s",
                status_update["message_id"],
                status_update["status"],
            )

    elif platform == "telegram":
        # Parse inbound update
        if parsed_update:
            result = await inbound_service.process_telegram_message(
                company_id=company_id,
                account_id=account_id,
                parsed=parsed_update,
            )
            processed = True

            # Answer callback queries inline
            if parsed_update.get("update_type") == "callback_query":
                try:
                    cred_mgr = CredentialManager()
                    acct = (await db.execute(
                        select(SocialAccount).where(SocialAccount.id == account_id)
                    )).scalar_one_or_none()
                    if acct:
                        token = cred_mgr.decrypt_access_token(acct.access_token)
                        tg_client = TelegramClient(bot_token=token)
                        await tg_client.post(
                            "/answerCallbackQuery",
                            json_data={
                                "callback_query_id": parsed_update["callback_id"],
                                "text": "Processing your request...",
                            },
                        )
                        await tg_client.close()
                except Exception:
                    pass

    # -- 4. Store webhook event for audit trail --
    event_type = "unknown"
    if platform in ("facebook", "instagram"):
        changes = payload.get("entry", [{}])[0].get("changes", [])
        if changes:
            event_type = changes[0].get("field", "unknown")
    elif platform == "whatsapp" and parsed:
        event_type = f"message_{parsed.get('message_type', 'unknown')}"
    elif platform == "telegram" and parsed_update:
        event_type = parsed_update.get("update_type", "message")

    event = await webhook_service.create_event(
        company_id=company_id,
        platform=platform,
        event_type=event_type,
        payload=payload,
        account_id=account_id,
    )
    await webhook_service.process_event(event.id, company_id)

    return {
        "success": True,
        "event_id": event.id,
        "processed": processed,
        "company_id": company_id,
        "branch_id": branch_id,
    }


@router.get(
    "/webhooks/events",
    response_model=WebhookEventListResponse,
    summary="Webhook event log",
    description="View webhook event processing log.",
)
async def list_webhook_events(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    processed: Optional[bool] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List webhook events."""
    service = WebhookService(db)
    result = await service.list_events(
        company_id=user.company_id,
        platform=platform,
        processed=processed,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/webhooks/status",
    response_model=WebhookProcessingStatus,
    summary="Webhook processing status",
    description="Get webhook processing statistics.",
)
async def webhook_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get webhook processing status."""
    from sqlalchemy import func, select

    from .models import SocialWebhook

    total_result = await db.execute(
        select(func.count())
        .select_from(SocialWebhook)
        .where(SocialWebhook.company_id == user.company_id)
    )
    total = total_result.scalar() or 0

    processed_result = await db.execute(
        select(func.count())
        .select_from(SocialWebhook)
        .where(
            SocialWebhook.company_id == user.company_id,
            SocialWebhook.processed == True,
        )
    )
    processed_count = processed_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count())
        .select_from(SocialWebhook)
        .where(
            SocialWebhook.company_id == user.company_id,
            SocialWebhook.processed == True,
            SocialWebhook.error_message.isnot(None),
        )
    )
    failed_count = failed_result.scalar() or 0

    return WebhookProcessingStatus(
        total_events=total,
        processed_count=processed_count,
        failed_count=failed_count,
        pending_count=total - processed_count,
    )


@router.post(
    "/webhooks/events/{event_id}/process",
    response_model=dict[str, object],
    summary="Process a webhook event",
    description="Manually re-process a webhook event.",
)
async def process_webhook_event(
    event_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually process a webhook event."""
    service = WebhookService(db)
    result = await service.process_event(event_id, user.company_id)
    return result


# =============================================================================
# Publishing Queue Endpoints
# =============================================================================


@router.post(
    "/queue",
    response_model=PublishingQueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a post to the publishing queue",
    description="Add a post to the sequential publishing queue with rate limit control.",
)
async def create_queue_item(
    data: PublishingQueueCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a post to the publishing queue."""
    service = PublishingQueueService(db)
    item = await service.add_to_queue(
        company_id=user.company_id,
        account_id=data.account_id,
        post_id=data.post_id,
        platform=data.platform,
        sequence_order=data.sequence_order,
        scheduled_at=data.scheduled_at,
        rate_limit_delay=data.rate_limit_delay,
        branch_id=user.branch_id,
    )
    return item


@router.get(
    "/queue",
    response_model=PublishingQueueListResponse,
    summary="List publishing queue items",
    description="List all publishing queue items for the current tenant.",
)
async def list_queue_items(
    status: Optional[str] = Query(None, description="Filter by status"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List publishing queue items."""
    service = PublishingQueueService(db)
    result = await service.list_queue(
        company_id=user.company_id,
        status=status,
        platform=platform,
        page=page,
        page_size=page_size,
    )
    return result


@router.post(
    "/queue/process",
    response_model=QueueProcessResult,
    summary="Process the publishing queue",
    description="Process all pending queue items sequentially with rate limiting.",
)
async def process_publishing_queue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Process the publishing queue sequentially."""
    service = PublishingQueueService(db)
    result = await service.process_queue(user.company_id)
    return QueueProcessResult(**result)


@router.delete(
    "/queue/{queue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a queue item",
    description="Remove a post from the publishing queue.",
)
async def delete_queue_item(
    queue_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a queue item."""
    service = PublishingQueueService(db)
    await service.remove_from_queue(queue_id, user.company_id)


# =============================================================================
# Social Listening Endpoints
# =============================================================================


@router.post(
    "/listening",
    response_model=SocialListeningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a social listening entry",
    description="Add a hashtag, mention, or keyword to monitor.",
)
async def create_listening(
    data: SocialListeningCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a social listening entry."""
    service = SocialListeningService(db)
    entry = await service.create_listening(
        company_id=user.company_id,
        data=data.model_dump(),
        branch_id=user.branch_id,
    )
    return entry


@router.get(
    "/listening",
    response_model=SocialListeningListResponse,
    summary="List social listening entries",
    description="List all social listening entries for the current tenant.",
)
async def list_listening(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List social listening entries."""
    service = SocialListeningService(db)
    result = await service.list_listening(
        company_id=user.company_id,
        platform=platform,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/listening/{listening_id}",
    response_model=SocialListeningResponse,
    summary="Get a listening entry",
    description="Get a social listening entry by ID.",
)
async def get_listening(
    listening_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a listening entry."""
    service = SocialListeningService(db)
    entry = await service.get_listening(listening_id, user.company_id)
    return entry


@router.patch(
    "/listening/{listening_id}",
    response_model=SocialListeningResponse,
    summary="Update a listening entry",
    description="Update a social listening entry.",
)
async def update_listening(
    listening_id: int,
    data: SocialListeningUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a listening entry."""
    service = SocialListeningService(db)
    entry = await service.update_listening(
        listening_id, user.company_id, data.model_dump(exclude_unset=True)
    )
    return entry


@router.delete(
    "/listening/{listening_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a listening entry",
    description="Remove a social listening entry.",
)
async def delete_listening(
    listening_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a listening entry."""
    service = SocialListeningService(db)
    await service.delete_listening(listening_id, user.company_id)


@router.post(
    "/listening/{listening_id}/check",
    response_model=ListeningCheckResult,
    summary="Check a listening target",
    description="Manually check a listening target and collect results.",
)
async def check_listening(
    listening_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check a listening entry."""
    service = SocialListeningService(db)
    result = await service.check_listening(listening_id, user.company_id)
    return ListeningCheckResult(**result)


# =============================================================================
# Hashtag Intelligence Endpoints
# =============================================================================


@router.post(
    "/hashtags",
    response_model=HashtagIntelligenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create hashtag intelligence",
    description="Manually add a hashtag intelligence entry.",
)
async def create_hashtag_intelligence(
    data: HashtagIntelligenceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a hashtag intelligence entry."""
    service = HashtagIntelligenceService(db)
    entry = await service.create_entry(
        company_id=user.company_id,
        data=data.model_dump(),
        branch_id=user.branch_id,
    )
    return entry


@router.get(
    "/hashtags",
    response_model=HashtagIntelligenceListResponse,
    summary="List hashtag intelligence",
    description="List all hashtag intelligence entries.",
)
async def list_hashtag_intelligence(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    trend_direction: Optional[str] = Query(None, description="Filter by trend"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List hashtag intelligence entries."""
    service = HashtagIntelligenceService(db)
    result = await service.list_entries(
        company_id=user.company_id,
        platform=platform,
        trend_direction=trend_direction,
        page=page,
        page_size=page_size,
    )
    return result


@router.get(
    "/hashtags/{entry_id}",
    response_model=HashtagIntelligenceResponse,
    summary="Get hashtag intelligence entry",
    description="Get a hashtag intelligence entry by ID.",
)
async def get_hashtag_intelligence(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a hashtag intelligence entry."""
    service = HashtagIntelligenceService(db)
    entry = await service.get_entry(entry_id, user.company_id)
    return entry


@router.patch(
    "/hashtags/{entry_id}",
    response_model=HashtagIntelligenceResponse,
    summary="Update hashtag intelligence",
    description="Update a hashtag intelligence entry.",
)
async def update_hashtag_intelligence(
    entry_id: int,
    data: HashtagIntelligenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a hashtag intelligence entry."""
    service = HashtagIntelligenceService(db)
    entry = await service.update_entry(entry_id, user.company_id, data.model_dump(exclude_unset=True))
    return entry


@router.delete(
    "/hashtags/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete hashtag intelligence",
    description="Remove a hashtag intelligence entry.",
)
async def delete_hashtag_intelligence(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a hashtag intelligence entry."""
    service = HashtagIntelligenceService(db)
    await service.delete_entry(entry_id, user.company_id)


@router.post(
    "/hashtags/analyze",
    response_model=dict[str, object],
    summary="Analyze hashtags for a platform",
    description="Fetch and analyze hashtags from connected account's recent posts.",
)
async def analyze_hashtags(
    platform: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Analyze hashtags for a platform."""
    service = HashtagIntelligenceService(db)
    result = await service.analyze_hashtags(user.company_id, platform)
    return result


@router.post(
    "/hashtags/suggest",
    response_model=HashtagSuggestionResponse,
    summary="Get hashtag suggestions",
    description="Get hashtag suggestions based on a topic/content description.",
)
async def suggest_hashtags(
    data: HashtagSuggestionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get hashtag suggestions for a topic."""
    service = HashtagIntelligenceService(db)
    result = await service.suggest_hashtags(
        user.company_id, data.topic, data.platform, data.count
    )
    return HashtagSuggestionResponse(**result)


# =============================================================================
# Webhook Signature Verification Endpoint
# =============================================================================


@router.post(
    "/webhooks/verify-signature",
    response_model=WebhookSignatureVerifyResponse,
    summary="Verify a webhook signature",
    description="Manually verify a webhook payload signature for any platform.",
)
async def verify_webhook_signature(
    data: WebhookSignatureVerifyRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Verify a webhook signature manually.

    Supports Facebook/Instagram (x-hub-signature-256 sha256=...),
    TikTok, and Telegram webhook secrets.
    """
    service = WebhookService(None)  # No DB needed for signature verification
    secret = data.secret or getattr(settings, "WEBHOOK_VERIFY_TOKEN", "")
    if not secret and data.platform in ("facebook", "instagram", "whatsapp"):
        secret = getattr(settings, "WHATSAPP_APP_SECRET", "")
    if not secret and data.platform == "tiktok":
        secret = getattr(settings, "TIKTOK_CLIENT_SECRET", "")
    if not secret and data.platform == "telegram":
        secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")

    payload_bytes = data.payload.encode("utf-8") if isinstance(data.payload, str) else data.payload
    is_valid = service.verify_webhook_signature(
        platform=data.platform,
        payload=payload_bytes,
        signature=data.signature,
        secret=secret,
    )
    return WebhookSignatureVerifyResponse(
        valid=is_valid,
        platform=data.platform,
        message="Signature valid" if is_valid else "Signature invalid",
    )


# =============================================================================
# Outbound Messaging Endpoints
# =============================================================================


@router.post(
    "/messages/{ticket_id}/send",
    response_model=dict[str, object],
    summary="Send outbound reply via WhatsApp/Telegram",
    description="Send a reply to the customer's original channel.",
)
async def send_outbound_reply(
    ticket_id: int,
    content: str,
    ai_generated: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send an outbound reply to the original messaging channel."""
    service = OutboundMessageService(db)
    result = await service.send_reply(
        ticket_id=ticket_id,
        company_id=user.company_id,
        content=content,
        sender_id=user.id,
        ai_generated=ai_generated,
    )
    return result


@router.post(
    "/whatsapp/send",
    response_model=dict[str, object],
    summary="Send WhatsApp message directly",
    description="Send a message via a connected WhatsApp Business account.",
)
async def send_whatsapp_message(
    account_id: int,
    to: str,
    content: str,
    message_type: str = "text",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a WhatsApp message directly via API."""
    service = OutboundMessageService(db)
    result = await service.send_whatsapp_reply(
        account_id=account_id,
        company_id=user.company_id,
        to=to,
        content=content,
        message_type=message_type,
    )
    return result


@router.post(
    "/telegram/send",
    response_model=dict[str, object],
    summary="Send Telegram message directly",
    description="Send a message via a connected Telegram Bot account.",
)
async def send_telegram_message(
    account_id: int,
    chat_id: str,
    content: str,
    use_inline_keyboard: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a Telegram message directly via Bot API."""
    service = OutboundMessageService(db)
    result = await service.send_telegram_reply(
        account_id=account_id,
        company_id=user.company_id,
        chat_id=chat_id,
        content=content,
        use_inline_keyboard=use_inline_keyboard,
    )
    return result