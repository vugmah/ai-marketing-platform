"""
FastAPI router for the AI Customer Support module.

Base path: /api/v2/support (mounted in main.py)

Provides endpoints for:
- Ticket management (CRUD, assign, escalate, close)
- Message management (list, add, AI reply, human takeover)
- Knowledge base (CRUD, search with RAG)
- Macros (CRUD, expand by shortcut)
- Escalation rules (CRUD)
- Analytics (aggregated metrics)
- Conversations (unified multi-channel view)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.social.service import OutboundMessageService

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.service import OpenAIService
from app.dependencies import get_current_user, get_db, require_role
from app.exceptions import NotFoundError, ValidationError
from app.support.constants import (
    RAG_TOP_K_RESULTS,
)
from app.support.models import (
    EscalationRule,
    KnowledgeBaseArticle,
    KnowledgeBaseCategory,
    SupportMacro,
    SupportMessage,
    SupportTicket,
)
from app.support.schemas import (
    AIReplyApprovalRequest,
    AIReplyApprovalResponse,
    AIReplyAuditLogResponse,
    AIReplyRequest,
    AIReplyResponse,
    CategorizationRequest,
    CategorizationResponse,
    ConversationListResponse,
    ConversationReplyRequest,
    ConversationReplyResponse,
    EscalationRuleCreate,
    EscalationRuleListResponse,
    EscalationRuleResponse,
    EscalationRuleUpdate,
    EscalationTriggerResult,
    HumanTakeoverRequest,
    HumanTakeoverResponse,
    KnowledgeBaseArticleCreate,
    KnowledgeBaseArticleListResponse,
    KnowledgeBaseArticleResponse,
    KnowledgeBaseArticleUpdate,
    KnowledgeBaseCategoryCreate,
    KnowledgeBaseCategoryResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
    MacroExpandRequest,
    MacroExpandResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
    SupportAnalyticsSummary,
    SupportMacroCreate,
    SupportMacroListResponse,
    SupportMacroResponse,
    SupportMacroUpdate,
    TicketAssign,
    TicketClose,
    TicketCreate,
    TicketEscalate,
    TicketFilterParams,
    TicketListResponse,
    TicketResponse,
    TicketUpdate,
)
from app.support.service import (
    AdminAlertService,
    AIAutoReplyService,
    AuditLogService,
    ConversationService,
    EscalationService,
    KnowledgeBaseService,
    MacroService,
    MessageService,
    RAGService,
    SentimentService,
    SupportAnalyticsService,
    TicketService,
)

router = APIRouter(prefix="/support", tags=["AI Customer Support"])


# ===========================================================================
# Helper: Build OpenAI service from app state
# ===========================================================================

def _get_openai_service(request: Request) -> OpenAIService:
    """Get or create OpenAI service from app state."""
    openai_svc = getattr(request.app.state, "openai_service", None)
    if openai_svc is None:
        openai_svc = OpenAIService()
        request.app.state.openai_service = openai_svc
    return openai_svc


# ===========================================================================
# Tickets
# ===========================================================================

@router.get(
    "/tickets",
    response_model=TicketListResponse,
    summary="List support tickets",
    description="List support tickets with optional filtering by status, priority, source, category, and assignee.",
)
async def list_tickets(
    request: Request,
    status: Optional[str] = Query(None, pattern="^(open|pending|resolved|closed)$"),
    priority: Optional[str] = Query(None, pattern="^(low|medium|high|urgent)$"),
    source: Optional[str] = Query(None, pattern="^(whatsapp|telegram|instagram|facebook|email|web)$"),
    category: Optional[str] = Query(None, pattern="^(billing|technical|sales|general)$"),
    assignee: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List support tickets with filtering and pagination."""
    filters = {
        "status": status,
        "priority": priority,
        "source": source,
        "category": category,
        "assignee": assignee,
        "search": search,
    }
    filters = {k: v for k, v in filters.items() if v is not None}

    service = TicketService(db)
    tickets, total = await service.list_tickets(
        company_id=user.company_id,
        branch_id=user.branch_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )

    # Build response items with message counts
    items = []
    for ticket in tickets:
        msg_count = await MessageService(db).get_message_count(ticket.id)
        ticket_dict = {
            "id": ticket.id,
            "company_id": ticket.company_id,
            "branch_id": ticket.branch_id,
            "customer_id": ticket.customer_id,
            "customer_name": ticket.customer_name,
            "customer_email": ticket.customer_email,
            "source": ticket.source,
            "source_conversation_id": ticket.source_conversation_id,
            "subject": ticket.subject,
            "status": ticket.status,
            "priority": ticket.priority,
            "assigned_to": ticket.assigned_to,
            "ai_handled": ticket.ai_handled,
            "ai_confidence": ticket.ai_confidence,
            "category": ticket.category,
            "tags": ticket.tags,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "resolved_at": ticket.resolved_at,
            "message_count": msg_count,
            "last_activity_at": ticket.updated_at,
        }
        items.append(ticket_dict)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a support ticket",
)
async def create_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SupportTicket:
    """Create a new support ticket."""
    # Ensure user can only create tickets for their company
    if data.company_id != user.company_id:
        raise ValidationError("Cannot create ticket for another company")

    service = TicketService(db)
    return await service.create_ticket(
        company_id=data.company_id,
        branch_id=data.branch_id or user.branch_id,
        data=data.model_dump(),
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket detail",
)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a ticket by ID with all details."""
    service = TicketService(db)
    ticket = await service.get_ticket(ticket_id, user.company_id)
    msg_count = await MessageService(db).get_message_count(ticket.id)

    return {
        "id": ticket.id,
        "company_id": ticket.company_id,
        "branch_id": ticket.branch_id,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "source": ticket.source,
        "source_conversation_id": ticket.source_conversation_id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "ai_handled": ticket.ai_handled,
        "ai_confidence": ticket.ai_confidence,
        "category": ticket.category,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "message_count": msg_count,
        "last_activity_at": ticket.updated_at,
    }


@router.put(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Update a ticket",
)
async def update_ticket(
    ticket_id: int,
    data: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Update a support ticket."""
    service = TicketService(db)
    ticket = await service.update_ticket(
        ticket_id, user.company_id, data.model_dump(exclude_unset=True)
    )
    msg_count = await MessageService(db).get_message_count(ticket.id)

    return {
        "id": ticket.id,
        "company_id": ticket.company_id,
        "branch_id": ticket.branch_id,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "source": ticket.source,
        "source_conversation_id": ticket.source_conversation_id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "ai_handled": ticket.ai_handled,
        "ai_confidence": ticket.ai_confidence,
        "category": ticket.category,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "message_count": msg_count,
        "last_activity_at": ticket.updated_at,
    }


@router.post(
    "/tickets/{ticket_id}/assign",
    response_model=TicketResponse,
    summary="Assign ticket to agent",
)
async def assign_ticket(
    ticket_id: int,
    data: TicketAssign,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Assign a ticket to a specific agent."""
    service = TicketService(db)
    ticket = await service.assign_ticket(
        ticket_id, user.company_id, data.assigned_to, data.note
    )
    msg_count = await MessageService(db).get_message_count(ticket.id)

    return {
        "id": ticket.id,
        "company_id": ticket.company_id,
        "branch_id": ticket.branch_id,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "source": ticket.source,
        "source_conversation_id": ticket.source_conversation_id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "ai_handled": ticket.ai_handled,
        "ai_confidence": ticket.ai_confidence,
        "category": ticket.category,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "message_count": msg_count,
        "last_activity_at": ticket.updated_at,
    }


@router.post(
    "/tickets/{ticket_id}/escalate",
    response_model=TicketResponse,
    summary="Escalate a ticket",
)
async def escalate_ticket(
    ticket_id: int,
    data: TicketEscalate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Escalate a ticket with optional priority change."""
    service = TicketService(db)
    ticket = await service.escalate_ticket(
        ticket_id=ticket_id,
        company_id=user.company_id,
        reason=data.reason,
        new_priority=data.new_priority,
        assign_to=data.assign_to,
    )
    msg_count = await MessageService(db).get_message_count(ticket.id)

    return {
        "id": ticket.id,
        "company_id": ticket.company_id,
        "branch_id": ticket.branch_id,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "source": ticket.source,
        "source_conversation_id": ticket.source_conversation_id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "ai_handled": ticket.ai_handled,
        "ai_confidence": ticket.ai_confidence,
        "category": ticket.category,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "message_count": msg_count,
        "last_activity_at": ticket.updated_at,
    }


@router.post(
    "/tickets/{ticket_id}/close",
    response_model=TicketResponse,
    summary="Close a ticket",
)
async def close_ticket(
    ticket_id: int,
    data: TicketClose,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Close a resolved ticket."""
    service = TicketService(db)
    ticket = await service.close_ticket(
        ticket_id, user.company_id, data.resolution_note
    )
    msg_count = await MessageService(db).get_message_count(ticket.id)

    return {
        "id": ticket.id,
        "company_id": ticket.company_id,
        "branch_id": ticket.branch_id,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer_name,
        "customer_email": ticket.customer_email,
        "source": ticket.source,
        "source_conversation_id": ticket.source_conversation_id,
        "subject": ticket.subject,
        "status": ticket.status,
        "priority": ticket.priority,
        "assigned_to": ticket.assigned_to,
        "ai_handled": ticket.ai_handled,
        "ai_confidence": ticket.ai_confidence,
        "category": ticket.category,
        "tags": ticket.tags,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "message_count": msg_count,
        "last_activity_at": ticket.updated_at,
    }


# ===========================================================================
# Ticket Messages
# ===========================================================================

@router.get(
    "/tickets/{ticket_id}/messages",
    response_model=MessageListResponse,
    summary="List ticket messages",
)
async def list_messages(
    ticket_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_internal: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List messages for a specific ticket."""
    service = MessageService(db)
    messages, total = await service.list_messages(
        ticket_id=ticket_id,
        company_id=user.company_id,
        page=page,
        page_size=page_size,
        include_internal=include_internal,
    )
    return {
        "items": messages,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a message to a ticket",
)
async def add_message(
    ticket_id: int,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SupportMessage:
    """Add a message to a ticket.

    GUVENLIK: AI sender_type ile dogrudan mesaj eklemek engellenir.
    AI mesajlari sadece approve endpoint'i ile gonderilir.
    """
    msg_data = data.model_dump()
    msg_data["sender_id"] = user.id

    # AI sender_type ile dogrudan mesaj eklemeyi engelle
    # AI mesajlari sadece approve endpoint'i ile gonderilir
    if msg_data.get("sender_type") == "ai":
        raise ValidationError(
            "AI messages cannot be added directly. "
            "Use POST /tickets/{ticket_id}/ai-reply to generate, "
            "then POST /tickets/{ticket_id}/ai-reply/{audit_log_id}/approve to send."
        )

    service = MessageService(db)
    return await service.add_message(ticket_id, user.company_id, msg_data)


# ===========================================================================
# AI Reply
# ===========================================================================

@router.post(
    "/tickets/{ticket_id}/ai-reply",
    response_model=AIReplyResponse,
    summary="Generate AI reply for a ticket (APPROVAL MODE DEFAULT ON)",
)
async def generate_ai_reply(
    request: Request,
    ticket_id: int,
    body: AIReplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generate an AI-powered reply for a ticket using RAG.

    CRITICAL: AI cevabi HICBIR ZAMAN otomatik gonderilmez.
    Her zaman onay bekler (requires_approval=True).
    Agent onay vermeden mesaj musteriye gitmez.
    """
    # Get ticket with messages
    ticket_service = TicketService(db)
    ticket = await ticket_service.get_ticket(ticket_id, user.company_id)

    message_service = MessageService(db)
    messages, _ = await message_service.list_messages(
        ticket_id, user.company_id, page=1, page_size=50
    )

    openai_svc = _get_openai_service(request)
    ai_service = AIAutoReplyService(db, openai_svc)

    result = await ai_service.generate_reply(
        company_id=user.company_id,
        ticket=ticket,
        messages=messages,
        tone=body.tone,
        max_length=body.max_length,
        context_override=body.context_override,
    )

    # ==========================================
    # APPROVAL MODE DEFAULT ON
    # ==========================================
    # AI cevabi OTOMATIK gonderilmez.
    # Sadece onay bekleme durumunda kalir.
    # Human agent /approve endpoint'ini cagirmadan mesaj gitmez.

    # Eger escalation tetiklendiyse, system notu ekle
    if result.get("escalation_triggered"):
        escalation_service = EscalationService(db)
        await escalation_service.evaluate_rules_for_ticket(ticket, messages)
        await message_service.add_message(
            ticket_id=ticket_id,
            company_id=user.company_id,
            data={
                "sender_type": "system",
                "content": f"AI otomatik yukseltme tetiklendi: {result.get('escalation_reason', 'unknown')}. "
                           f"Confidence: {result['confidence']}. Onay gerekiyor.",
                "internal_note": True,
            },
        )

    return result


@router.post(
    "/tickets/{ticket_id}/human-takeover",
    response_model=HumanTakeoverResponse,
    summary="Transfer AI-handled ticket to human agent",
)
async def human_takeover(
    ticket_id: int,
    data: HumanTakeoverRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Transfer an AI-handled ticket to a human agent.
    AI devredisi birakilir, ticket human agent'e atanir.
    Bekleyen AI reply'ler varsa red edilir.
    """
    ticket_service = TicketService(db)
    ticket = await ticket_service.get_ticket(ticket_id, user.company_id)

    # 1. Assign to the requesting user
    await ticket_service.assign_ticket(
        ticket_id=ticket_id,
        company_id=user.company_id,
        assigned_to=user.id,
        note=f"Human takeover: {data.reason}",
    )

    # 2. Disable AI handling on the ticket
    ticket.ai_handled = False
    ticket.ai_confidence = None

    # 3. Reject any pending AI reply audit logs for this ticket
    audit_service = AuditLogService(db)
    pending_logs, _ = await audit_service.list_logs(
        company_id=user.company_id,
        ticket_id=ticket_id,
        status="pending",
        page=1,
        page_size=100,
    )
    for log in pending_logs:
        await audit_service.update_status(
            log_id=log.id,
            company_id=user.company_id,
            status="rejected",
            reviewed_by=user.id,
            review_note=f"Auto-rejected due to human takeover: {data.reason}",
        )

    # 4. Add a system message
    message_service = MessageService(db)
    await message_service.add_message(
        ticket_id=ticket_id,
        company_id=user.company_id,
        data={
            "sender_type": "system",
            "content": f"Human agent ({user.id}) has taken over this ticket. Reason: {data.reason}. "
                       f"AI handling disabled. {len(pending_logs)} pending AI replies auto-rejected.",
            "internal_note": True,
        },
    )

    # 5. Send admin alert for human takeover
    try:
        alert_service = AdminAlertService(db)
        await alert_service.alert_human_takeover(
            company_id=user.company_id,
            ticket_id=ticket_id,
            agent_id=user.id,
            reason=data.reason,
            branch_id=ticket.branch_id,
        )
    except Exception:
        pass  # Alert failure should not block the takeover

    await db.commit()

    return {
        "success": True,
        "message": f"Ticket {ticket_id} transferred to human agent {user.id}. "
                   f"{len(pending_logs)} pending AI replies auto-rejected.",
        "ticket_id": ticket_id,
        "pending_replies_rejected": len(pending_logs),
    }


# ===========================================================================
# AI Reply Approval (APPROVAL MODE DEFAULT ON)
# ===========================================================================

@router.post(
    "/tickets/{ticket_id}/ai-reply/{audit_log_id}/approve",
    response_model=AIReplyApprovalResponse,
    summary="Approve AI reply and send to customer",
)
async def approve_ai_reply(
    request: Request,
    ticket_id: int,
    audit_log_id: int,
    body: AIReplyApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Onaylanan AI cevabini musteriye gonder.
    Sadece approve veya approve_and_send action'lari kabul edilir.
    """
    openai_svc = _get_openai_service(request)
    ai_service = AIAutoReplyService(db, openai_svc)

    if body.action not in ("approve", "approve_and_send"):
        raise ValidationError("Invalid action. Use 'approve' or 'approve_and_send'.")

    message = await ai_service.approve_and_send_reply(
        audit_log_id=audit_log_id,
        company_id=user.company_id,
        ticket_id=ticket_id,
        reviewed_by=user.id,
        note=body.note,
    )

    return {
        "success": True,
        "message": f"AI reply approved and sent. Message ID: {message.id}",
        "audit_log_id": audit_log_id,
        "ticket_id": ticket_id,
        "action": "approve_and_send",
    }


@router.post(
    "/tickets/{ticket_id}/ai-reply/{audit_log_id}/reject",
    response_model=AIReplyApprovalResponse,
    summary="Reject AI reply",
)
async def reject_ai_reply(
    request: Request,
    ticket_id: int,
    audit_log_id: int,
    body: AIReplyApprovalRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """AI cevabini red et."""
    openai_svc = _get_openai_service(request)
    ai_service = AIAutoReplyService(db, openai_svc)

    if body.action != "reject":
        raise ValidationError("Invalid action. Use 'reject'.")

    await ai_service.reject_reply(
        audit_log_id=audit_log_id,
        company_id=user.company_id,
        reviewed_by=user.id,
        note=body.note,
    )

    return {
        "success": True,
        "message": "AI reply rejected.",
        "audit_log_id": audit_log_id,
        "ticket_id": ticket_id,
        "action": "reject",
    }


@router.get(
    "/tickets/{ticket_id}/ai-reply/logs",
    response_model=Dict[str, Any],
    summary="List AI reply audit logs for a ticket",
)
async def list_ai_reply_logs(
    ticket_id: int,
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected|auto_sent|filtered)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List AI reply audit logs for a specific ticket."""
    audit_service = AuditLogService(db)
    logs, total = await audit_service.list_logs(
        company_id=user.company_id,
        ticket_id=ticket_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return {
        "items": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ===========================================================================
# Knowledge Base Articles
# ===========================================================================

@router.get(
    "/knowledge-base",
    response_model=KnowledgeBaseArticleListResponse,
    summary="List KB articles",
)
async def list_kb_articles(
    status: Optional[str] = Query(None, pattern="^(draft|published|archived)$"),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List knowledge base articles with filtering."""
    service = KnowledgeBaseService(db)
    articles, total = await service.list_articles(
        company_id=user.company_id,
        status=status,
        category=category,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "items": articles,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/knowledge-base",
    response_model=KnowledgeBaseArticleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create KB article",
)
async def create_kb_article(
    data: KnowledgeBaseArticleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> KnowledgeBaseArticle:
    """Create a new knowledge base article."""
    if data.company_id != user.company_id:
        raise ValidationError("Cannot create article for another company")

    service = KnowledgeBaseService(db)
    article_data = data.model_dump()
    article_data["created_by"] = user.id
    return await service.create_article(user.company_id, article_data)


@router.get(
    "/knowledge-base/{article_id}",
    response_model=KnowledgeBaseArticleResponse,
    summary="Get KB article detail",
)
async def get_kb_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> KnowledgeBaseArticle:
    """Get a knowledge base article by ID (increments view count)."""
    service = KnowledgeBaseService(db)
    return await service.get_article_and_increment_views(article_id, user.company_id)


@router.put(
    "/knowledge-base/{article_id}",
    response_model=KnowledgeBaseArticleResponse,
    summary="Update KB article",
)
async def update_kb_article(
    article_id: int,
    data: KnowledgeBaseArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> KnowledgeBaseArticle:
    """Update a knowledge base article."""
    service = KnowledgeBaseService(db)
    return await service.update_article(
        article_id, user.company_id, data.model_dump(exclude_unset=True)
    )


@router.delete(
    "/knowledge-base/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete/archive KB article",
)
async def delete_kb_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Archive a knowledge base article (soft delete)."""
    service = KnowledgeBaseService(db)
    await service.delete_article(article_id, user.company_id)


# ===========================================================================
# KB Search (RAG)
# ===========================================================================

@router.get(
    "/knowledge-base/search",
    response_model=KnowledgeBaseSearchResponse,
    summary="Search KB articles (RAG)",
)
async def search_kb_articles(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    top_k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Search knowledge base articles using full-text + keyword matching."""
    service = KnowledgeBaseService(db)
    scored_articles = await service.search_articles(
        company_id=user.company_id,
        query_text=q,
        top_k=top_k,
    )

    results = []
    for article, score in scored_articles:
        article_dict = {
            "id": article.id,
            "company_id": article.company_id,
            "title": article.title,
            "content": article.content,
            "summary": article.summary,
            "category": article.category,
            "tags": article.tags,
            "keywords": article.keywords,
            "status": article.status,
            "source": article.source,
            "view_count": article.view_count,
            "helpful_count": article.helpful_count,
            "created_by": article.created_by,
            "created_at": article.created_at,
            "updated_at": article.updated_at,
        }
        results.append({
            "article": article_dict,
            "relevance_score": round(score, 4),
        })

    return {
        "results": results,
        "query": q,
        "total_found": len(results),
    }


# ===========================================================================
# KB Categories
# ===========================================================================

@router.get(
    "/knowledge-base/categories",
    response_model=List[KnowledgeBaseCategoryResponse],
    summary="List KB categories",
)
async def list_kb_categories(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> List[KnowledgeBaseCategory]:
    """List all knowledge base categories."""
    service = KnowledgeBaseService(db)
    return await service.list_categories(user.company_id)


@router.post(
    "/knowledge-base/categories",
    response_model=KnowledgeBaseCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create KB category",
)
async def create_kb_category(
    data: KnowledgeBaseCategoryCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> KnowledgeBaseCategory:
    """Create a new knowledge base category."""
    if data.company_id != user.company_id:
        raise ValidationError("Cannot create category for another company")
    service = KnowledgeBaseService(db)
    return await service.create_category(user.company_id, data.model_dump())


# ===========================================================================
# Macros
# ===========================================================================

@router.get(
    "/macros",
    response_model=SupportMacroListResponse,
    summary="List support macros",
)
async def list_macros(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List support macros for the company."""
    service = MacroService(db)
    macros, total = await service.list_macros(
        company_id=user.company_id,
        category=category,
        page=page,
        page_size=page_size,
    )
    return {
        "items": macros,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/macros",
    response_model=SupportMacroResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create support macro",
)
async def create_macro(
    data: SupportMacroCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SupportMacro:
    """Create a new support macro."""
    if data.company_id != user.company_id:
        raise ValidationError("Cannot create macro for another company")
    service = MacroService(db)
    macro_data = data.model_dump()
    macro_data["created_by"] = user.id
    return await service.create_macro(user.company_id, macro_data)


@router.get(
    "/macros/{shortcut}",
    response_model=SupportMacroResponse,
    summary="Get macro by shortcut",
)
async def get_macro_by_shortcut(
    shortcut: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SupportMacro:
    """Get a macro by its shortcut (e.g., '/refund')."""
    service = MacroService(db)
    macro = await service.get_macro_by_shortcut(user.company_id, shortcut)
    if not macro:
        raise NotFoundError(f"Macro with shortcut '{shortcut}' not found")
    return macro


@router.put(
    "/macros/{macro_id}",
    response_model=SupportMacroResponse,
    summary="Update macro",
)
async def update_macro(
    macro_id: int,
    data: SupportMacroUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> SupportMacro:
    """Update a support macro."""
    service = MacroService(db)
    return await service.update_macro(
        macro_id, user.company_id, data.model_dump(exclude_unset=True)
    )


@router.delete(
    "/macros/{macro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete macro",
)
async def delete_macro(
    macro_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Delete a support macro."""
    service = MacroService(db)
    await service.delete_macro(macro_id, user.company_id)


@router.post(
    "/macros/{shortcut}/expand",
    response_model=MacroExpandResponse,
    summary="Expand a macro",
)
async def expand_macro(
    shortcut: str,
    data: MacroExpandRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Expand a macro by shortcut with variable substitution."""
    service = MacroService(db)
    macro = await service.get_macro_by_shortcut(user.company_id, shortcut)
    if not macro:
        raise NotFoundError(f"Macro with shortcut '{shortcut}' not found")

    expanded = service.expand_macro(macro, data.variables)
    return {
        "expanded_content": expanded,
        "macro_name": macro.name,
        "shortcut": macro.shortcut,
    }


# ===========================================================================
# Escalation Rules
# ===========================================================================

@router.get(
    "/escalation-rules",
    response_model=EscalationRuleListResponse,
    summary="List escalation rules",
)
async def list_escalation_rules(
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List escalation rules for the company."""
    service = EscalationService(db)
    rules = await service.list_rules(user.company_id, active_only=active_only)
    return {
        "items": rules,
        "total": len(rules),
        "page": 1,
        "page_size": len(rules),
    }


@router.post(
    "/escalation-rules",
    response_model=EscalationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create escalation rule",
)
async def create_escalation_rule(
    data: EscalationRuleCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> EscalationRule:
    """Create a new escalation rule."""
    if data.company_id != user.company_id:
        raise ValidationError("Cannot create rule for another company")
    service = EscalationService(db)
    return await service.create_rule(user.company_id, data.model_dump())


@router.put(
    "/escalation-rules/{rule_id}",
    response_model=EscalationRuleResponse,
    summary="Update escalation rule",
)
async def update_escalation_rule(
    rule_id: int,
    data: EscalationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> EscalationRule:
    """Update an escalation rule."""
    service = EscalationService(db)
    return await service.update_rule(
        rule_id, user.company_id, data.model_dump(exclude_unset=True)
    )


@router.delete(
    "/escalation-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete escalation rule",
)
async def delete_escalation_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> None:
    """Delete an escalation rule."""
    service = EscalationService(db)
    rule = await service.get_rule(rule_id, user.company_id)
    await db.delete(rule)
    await db.commit()


# ===========================================================================
# Analytics
# ===========================================================================

@router.get(
    "/analytics",
    response_model=SupportAnalyticsSummary,
    summary="Get support analytics",
)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get aggregated support analytics for the company."""
    service = SupportAnalyticsService(db)
    return await service.get_summary(user.company_id, days=days)


# ===========================================================================
# Conversations (Unified Multi-Channel View)
# ===========================================================================

@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List unified conversations",
)
async def list_conversations(
    source: Optional[str] = Query(None, pattern="^(whatsapp|telegram|instagram|facebook|email|web)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """List conversations in unified multi-channel view."""
    service = ConversationService(db)
    conversations, total = await service.list_conversations(
        company_id=user.company_id,
        branch_id=user.branch_id,
        source=source,
        page=page,
        page_size=page_size,
    )
    return {
        "items": conversations,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/conversations/{ticket_id}/messages",
    response_model=Dict[str, Any],
    summary="Get conversation messages",
)
async def get_conversation_messages(
    ticket_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Get messages for a specific conversation."""
    service = ConversationService(db)
    messages, total = await service.get_conversation_messages(
        ticket_id=ticket_id,
        company_id=user.company_id,
        page=page,
        page_size=page_size,
    )
    return {
        "items": messages,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "/conversations/{ticket_id}/reply",
    response_model=ConversationReplyResponse,
    summary="Reply to a conversation",
)
async def reply_to_conversation(
    request: Request,
    ticket_id: int,
    data: ConversationReplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Reply to a conversation. Optionally use AI to generate the reply."""
    service = ConversationService(db)

    content = data.content
    ai_generated = False
    ai_confidence = None

    # If AI reply requested, generate it (APPROVAL MODE ON)
    if data.use_ai:
        ticket_service = TicketService(db)
        ticket = await ticket_service.get_ticket(ticket_id, user.company_id)

        message_service = MessageService(db)
        messages, _ = await message_service.list_messages(
            ticket_id, user.company_id, page=1, page_size=50
        )

        openai_svc = _get_openai_service(request)
        ai_service = AIAutoReplyService(db, openai_svc)

        result = await ai_service.generate_reply(
            company_id=user.company_id,
            ticket=ticket,
            messages=messages,
        )

        # APPROVAL MODE: AI cevabi otomatik gonderilmez.
        # Human agent'in onayi gerekir.
        # Burada sadece onay bekleme bilgisi donulur.
        return {
            "success": True,
            "message": "AI reply generated but requires approval before sending. "
                       f"Use POST /tickets/{ticket_id}/ai-reply/{result['audit_log_id']}/approve to send.",
            "message_id": None,
            "ticket_id": ticket_id,
            "ai_generated": True,
            "content": result["content"],
            "confidence": result["confidence"],
            "requires_approval": True,
            "audit_log_id": result["audit_log_id"],
            "suggested_human_takeover": result["suggested_human_takeover"],
            "forbidden_triggered": result["forbidden_triggered"],
        }

    message = await service.reply_to_conversation(
        ticket_id=ticket_id,
        company_id=user.company_id,
        content=content,
        sender_id=user.id,
        ai_generated=ai_generated,
        ai_confidence=ai_confidence,
    )

    # Send reply to external platform (WhatsApp/Telegram) if applicable
    outbound_service = OutboundMessageService(db)
    try:
        outbound_result = await outbound_service.send_reply(
            ticket_id=ticket_id,
            company_id=user.company_id,
            content=content,
            sender_id=user.id,
            ai_generated=ai_generated,
            ai_confidence=ai_confidence,
        )
    except Exception as exc:
        logger.warning("Failed to send outbound reply: %s", exc)
        outbound_result = {"success": False, "error": str(exc)}

    return {
        "success": True,
        "message_id": message.id,
        "ticket_id": ticket_id,
        "ai_generated": ai_generated,
        "content": content,
        "outbound_sent": outbound_result.get("success", False),
        "api_message_id": outbound_result.get("api_message_id"),
        "platform": outbound_result.get("platform"),
    }


# ===========================================================================
# Sentiment Analysis (Utility)
# ===========================================================================

@router.post(
    "/sentiment",
    response_model=SentimentAnalysisResponse,
    summary="Analyze sentiment of text",
)
async def analyze_sentiment(
    request: Request,
    data: SentimentAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Analyze the sentiment of a piece of text."""
    openai_svc = _get_openai_service(request)
    service = SentimentService(openai_svc)
    result = await service.analyze(data.text)
    return {
        "sentiment": result["sentiment"],
        "score": result.get("score"),
        "confidence": result["confidence"],
    }


# ===========================================================================
# Auto-Categorization (Utility)
# ===========================================================================

@router.post(
    "/categorize",
    response_model=CategorizationResponse,
    summary="Auto-categorize a ticket",
)
async def categorize_ticket(
    data: CategorizationRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Auto-categorize a ticket based on subject and content using keyword matching."""
    service = TicketService(db)
    category = await service._auto_categorize(data.subject, data.content or "")
    return {
        "category": category,
        "confidence": 0.8 if category != "general" else 0.5,
    }


# ===========================================================================
# RAG Context Retrieval (Utility)
# ===========================================================================

@router.post(
    "/rag-context",
    response_model=Dict[str, Any],
    summary="Retrieve RAG context for a query",
)
async def get_rag_context(
    request: Request,
    query: str = Query(..., min_length=1, max_length=1000),
    top_k: int = Query(RAG_TOP_K_RESULTS, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve relevant KB articles as RAG context for a query."""
    rag_service = RAGService(db)
    result = await rag_service.retrieve_context(
        company_id=user.company_id,
        query=query,
        top_k=top_k,
    )
    return result
