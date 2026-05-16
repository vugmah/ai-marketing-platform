"""
AI Customer Support services.

Provides 10 core services:
- TicketService: CRUD tickets, assignment, escalation, status workflow, auto-categorization
- MessageService: Add messages, AI auto-reply, sentiment analysis
- KnowledgeBaseService: CRUD articles, full-text + keyword search, RAG retrieval
- MacroService: CRUD macros, variable substitution, shortcut expansion
- EscalationService: Evaluate rules, trigger escalations, notify assignees
- AIAutoReplyService: Generate AI responses using RAG, confidence scoring, human takeover
- RAGService: Retrieve relevant KB articles, rank by relevance, format LLM context
- SentimentService: Analyze message sentiment via OpenAI
- SupportAnalyticsService: Aggregate metrics, calculate response/resolution times
- ConversationService: Multi-channel conversation threads unified view
"""

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError

from app.support.constants import (
    AI_AUTO_REPLY_CONFIDENCE_THRESHOLD,
    AI_CATEGORIZATION_SYSTEM_PROMPT,
    AI_REPLY_CONFIDENCE_SYSTEM_PROMPT,
    AI_REPLY_MAX_LENGTH,
    AI_REPLY_SYSTEM_PROMPT,
    AI_SENTIMENT_SYSTEM_PROMPT,
    ANALYTICS_AGGREGATION_DAYS,
    ANALYTICS_CACHE_TTL_SECONDS,
    AUDIT_LOG_RETENTION_DAYS,
    FORBIDDEN_KEYWORDS,
    FORBIDDEN_RESPONSE_DENYLIST,
    FORBIDDEN_RESPONSE_PATTERNS,
    HUMAN_TAKEOVER_CONSECUTIVE_LOW_CONFIDENCE,
    HUMAN_TAKEOVER_CONFIDENCE_THRESHOLD,
    HUMAN_TAKEOVER_KEYWORDS,
    HUMAN_TAKEOVER_SENTIMENT_THRESHOLD,
    KB_SEARCH_CACHE_TTL_SECONDS,
    RAG_CONTEXT_TEMPLATE,
    RAG_MAX_CONTEXT_TOKENS,
    RAG_MIN_RELEVANCE_SCORE,
    RAG_TOP_K_RESULTS,
    SLA_RESOLUTION_TIME_MINUTES,
    SLA_RESPONSE_TIME_MINUTES,
    SUPPORT_CACHE_PREFIX,
    TICKET_LIST_CACHE_TTL_SECONDS,
    VALID_TICKET_STATUS_TRANSITIONS,
)
from app.support.models import (
    AIReplyAuditLog,
    EscalationRule,
    KnowledgeBaseArticle,
    KnowledgeBaseCategory,
    SupportAnalytics,
    SupportMacro,
    SupportMessage,
    SupportTicket,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ticket Service
# ---------------------------------------------------------------------------

class TicketService:
    """CRUD and workflow management for support tickets."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ticket(
        self,
        company_id: int,
        branch_id: Optional[int],
        data: Dict[str, Any],
    ) -> SupportTicket:
        """Create a new support ticket with optional auto-categorization."""
        ticket = SupportTicket(
            company_id=company_id,
            branch_id=branch_id,
            customer_id=data.get("customer_id"),
            customer_name=data.get("customer_name"),
            customer_email=data.get("customer_email"),
            source=data.get("source", "web"),
            source_conversation_id=data.get("source_conversation_id"),
            subject=data["subject"],
            status="open",
            priority=data.get("priority", "medium"),
            category=data.get("category"),
            tags=data.get("tags", []),
            assigned_to=data.get("assigned_to"),
        )
        self.db.add(ticket)
        await self.db.flush()

        # Add initial message if provided
        initial_message = data.get("initial_message")
        if initial_message:
            message = SupportMessage(
                ticket_id=ticket.id,
                sender_type="customer",
                content=initial_message,
                internal_note=False,
            )
            self.db.add(message)

        # Auto-categorize if no category provided
        if not ticket.category:
            try:
                category = await self._auto_categorize(
                    ticket.subject, initial_message or ""
                )
                ticket.category = category
            except Exception:
                ticket.category = "general"

        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info("Created ticket id=%d company=%d", ticket.id, company_id)
        return ticket

    async def get_ticket(
        self,
        ticket_id: int,
        company_id: int,
    ) -> SupportTicket:
        """Get a ticket by ID with tenant check."""
        result = await self.db.execute(
            select(SupportTicket)
            .where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
            .options(
                selectinload(SupportTicket.messages),
            )
        )
        ticket = result.unique().scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def list_tickets(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[SupportTicket], int]:
        """List tickets with filtering and pagination."""
        filters = filters or {}
        query = select(SupportTicket).where(
            SupportTicket.company_id == company_id
        )

        if branch_id is not None:
            query = query.where(
                (SupportTicket.branch_id == branch_id)
                | (SupportTicket.branch_id.is_(None))
            )

        # Apply filters
        status = filters.get("status")
        if status:
            query = query.where(SupportTicket.status == status)

        priority = filters.get("priority")
        if priority:
            query = query.where(SupportTicket.priority == priority)

        source = filters.get("source")
        if source:
            query = query.where(SupportTicket.source == source)

        category = filters.get("category")
        if category:
            query = query.where(SupportTicket.category == category)

        assignee = filters.get("assignee")
        if assignee is not None:
            query = query.where(SupportTicket.assigned_to == assignee)

        search = filters.get("search")
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    SupportTicket.subject.ilike(search_pattern),
                    SupportTicket.customer_name.ilike(search_pattern),
                    SupportTicket.customer_email.ilike(search_pattern),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results, most recent first
        query = query.order_by(desc(SupportTicket.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        tickets = result.scalars().all()

        return list(tickets), total

    async def update_ticket(
        self,
        ticket_id: int,
        company_id: int,
        data: Dict[str, Any],
    ) -> SupportTicket:
        """Update a ticket's fields."""
        ticket = await self._get_ticket_strict(ticket_id, company_id)

        updatable = [
            "subject", "priority", "category", "tags",
            "assigned_to", "customer_name", "customer_email",
        ]
        for field in updatable:
            if field in data and data[field] is not None:
                setattr(ticket, field, data[field])

        # Handle status transitions
        new_status = data.get("status")
        if new_status and new_status != ticket.status:
            if new_status not in VALID_TICKET_STATUS_TRANSITIONS.get(ticket.status, []):
                raise ValidationError(
                    f"Invalid status transition from {ticket.status} to {new_status}"
                )
            ticket.status = new_status
            if new_status == "resolved":
                ticket.resolved_at = datetime.utcnow()
                ticket.ai_handled = data.get("ai_handled", ticket.ai_handled)

        ticket.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info("Updated ticket id=%d", ticket.id)
        return ticket

    async def assign_ticket(
        self,
        ticket_id: int,
        company_id: int,
        assigned_to: int,
        note: Optional[str] = None,
    ) -> SupportTicket:
        """Assign a ticket to a user."""
        ticket = await self._get_ticket_strict(ticket_id, company_id)
        ticket.assigned_to = assigned_to
        ticket.updated_at = datetime.utcnow()

        if note:
            system_message = SupportMessage(
                ticket_id=ticket.id,
                sender_type="system",
                content=f"Ticket assigned to agent. Note: {note}",
                internal_note=True,
            )
            self.db.add(system_message)

        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info("Assigned ticket id=%d to user=%d", ticket.id, assigned_to)
        return ticket

    async def escalate_ticket(
        self,
        ticket_id: int,
        company_id: int,
        reason: str,
        new_priority: Optional[str] = None,
        assign_to: Optional[int] = None,
    ) -> SupportTicket:
        """Escalate a ticket with optional priority change and reassignment."""
        ticket = await self._get_ticket_strict(ticket_id, company_id)

        if new_priority:
            ticket.priority = new_priority
        # Auto-bump priority if not specified
        elif ticket.priority == "low":
            ticket.priority = "medium"
        elif ticket.priority == "medium":
            ticket.priority = "high"
        elif ticket.priority == "high":
            ticket.priority = "urgent"

        if assign_to:
            ticket.assigned_to = assign_to

        ticket.status = "open"
        ticket.updated_at = datetime.utcnow()

        escalation_message = SupportMessage(
            ticket_id=ticket.id,
            sender_type="system",
            content=f"Ticket escalated. Reason: {reason}",
            internal_note=True,
        )
        self.db.add(escalation_message)

        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info(
            "Escalated ticket id=%d to priority=%s", ticket.id, ticket.priority
        )
        return ticket

    async def close_ticket(
        self,
        ticket_id: int,
        company_id: int,
        resolution_note: Optional[str] = None,
    ) -> SupportTicket:
        """Close a resolved ticket."""
        ticket = await self._get_ticket_strict(ticket_id, company_id)
        ticket.status = "closed"
        ticket.resolved_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()

        if resolution_note:
            system_message = SupportMessage(
                ticket_id=ticket.id,
                sender_type="system",
                content=f"Ticket closed. Resolution: {resolution_note}",
                internal_note=False,
            )
            self.db.add(system_message)

        await self.db.commit()
        await self.db.refresh(ticket)
        logger.info("Closed ticket id=%d", ticket.id)
        return ticket

    async def _get_ticket_strict(
        self, ticket_id: int, company_id: int
    ) -> SupportTicket:
        """Get ticket without loading messages (for updates)."""
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def _auto_categorize(self, subject: str, content: str) -> str:
        """Auto-categorize a ticket using keyword matching (no AI call)."""
        text = f"{subject} {content}".lower()

        keyword_map = {
            "billing": ["payment", "invoice", "charge", "refund", "billing", "subscription", "price", "cost", "fee", "receipt"],
            "technical": ["error", "bug", "crash", "login", "password", "not working", "broken", "api", "integration", "server", "timeout", "ssl", "database"],
            "sales": ["pricing", "plan", "upgrade", "demo", "purchase", "buy", "quote", "proposal", "deal", "discount", "trial"],
        }

        scores = {}
        for category, keywords in keyword_map.items():
            scores[category] = sum(1 for kw in keywords if kw in text)

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] > 0:
                return best
        return "general"


# ---------------------------------------------------------------------------
# Message Service
# ---------------------------------------------------------------------------

class MessageService:
    """CRUD and AI-powered features for support messages."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_message(
        self,
        ticket_id: int,
        company_id: int,
        data: Dict[str, Any],
    ) -> SupportMessage:
        """Add a message to a ticket."""
        # Verify ticket exists
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")

        message = SupportMessage(
            ticket_id=ticket_id,
            sender_type=data.get("sender_type", "agent"),
            sender_id=data.get("sender_id"),
            content=data["content"],
            attachments=data.get("attachments", []),
            internal_note=data.get("internal_note", False),
            ai_generated=data.get("ai_generated", False),
            ai_confidence=data.get("ai_confidence"),
            sentiment=data.get("sentiment"),
        )
        self.db.add(message)

        # Update ticket timestamp
        ticket.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(message)
        logger.info("Added message id=%d to ticket=%d", message.id, ticket_id)
        return message

    async def list_messages(
        self,
        ticket_id: int,
        company_id: int,
        page: int = 1,
        page_size: int = 50,
        include_internal: bool = False,
    ) -> Tuple[List[SupportMessage], int]:
        """List messages for a ticket."""
        # Verify ticket
        result = await self.db.execute(
            select(SupportTicket.id).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        if not result.scalar_one_or_none():
            raise NotFoundError(f"Ticket {ticket_id} not found")

        query = select(SupportMessage).where(
            SupportMessage.ticket_id == ticket_id
        )
        if not include_internal:
            query = query.where(SupportMessage.internal_note.is_(False))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(SupportMessage.created_at)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        messages = result.scalars().all()

        return list(messages), total

    async def get_message_count(self, ticket_id: int) -> int:
        """Get the number of messages in a ticket."""
        result = await self.db.execute(
            select(func.count())
            .where(SupportMessage.ticket_id == ticket_id)
        )
        return result.scalar() or 0


# ---------------------------------------------------------------------------
# Knowledge Base Service
# ---------------------------------------------------------------------------

class KnowledgeBaseService:
    """CRUD and search for knowledge base articles."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_article(
        self, company_id: int, data: Dict[str, Any]
    ) -> KnowledgeBaseArticle:
        """Create a new KB article."""
        article = KnowledgeBaseArticle(
            company_id=company_id,
            title=data["title"],
            content=data["content"],
            summary=data.get("summary"),
            category=data.get("category"),
            tags=data.get("tags", []),
            keywords=data.get("keywords", []),
            source=data.get("source", "manual"),
            status=data.get("status", "draft"),
            created_by=data.get("created_by"),
        )
        self.db.add(article)
        await self.db.commit()
        await self.db.refresh(article)
        logger.info("Created KB article id=%d company=%d", article.id, company_id)
        return article

    async def get_article(
        self, article_id: int, company_id: int
    ) -> KnowledgeBaseArticle:
        """Get a KB article by ID."""
        result = await self.db.execute(
            select(KnowledgeBaseArticle).where(
                KnowledgeBaseArticle.id == article_id,
                KnowledgeBaseArticle.company_id == company_id,
            )
        )
        article = result.scalar_one_or_none()
        if not article:
            raise NotFoundError(f"KB article {article_id} not found")
        return article

    async def get_article_and_increment_views(
        self, article_id: int, company_id: int
    ) -> KnowledgeBaseArticle:
        """Get a KB article and increment its view count."""
        article = await self.get_article(article_id, company_id)
        article.view_count += 1
        await self.db.commit()
        return article

    async def list_articles(
        self,
        company_id: int,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[KnowledgeBaseArticle], int]:
        """List KB articles with filtering."""
        query = select(KnowledgeBaseArticle).where(
            KnowledgeBaseArticle.company_id == company_id
        )

        if status:
            query = query.where(KnowledgeBaseArticle.status == status)
        if category:
            query = query.where(KnowledgeBaseArticle.category == category)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    KnowledgeBaseArticle.title.ilike(pattern),
                    KnowledgeBaseArticle.content.ilike(pattern),
                    KnowledgeBaseArticle.summary.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(desc(KnowledgeBaseArticle.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        articles = result.scalars().all()

        return list(articles), total

    async def update_article(
        self,
        article_id: int,
        company_id: int,
        data: Dict[str, Any],
    ) -> KnowledgeBaseArticle:
        """Update a KB article."""
        article = await self.get_article(article_id, company_id)

        updatable = [
            "title", "content", "summary", "category", "tags",
            "keywords", "status", "vector_embedding",
        ]
        for field in updatable:
            if field in data and data[field] is not None:
                setattr(article, field, data[field])

        article.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(article)
        logger.info("Updated KB article id=%d", article.id)
        return article

    async def delete_article(self, article_id: int, company_id: int) -> None:
        """Soft-delete a KB article by archiving it."""
        article = await self.get_article(article_id, company_id)
        article.status = "archived"
        article.updated_at = datetime.utcnow()
        await self.db.commit()
        logger.info("Archived KB article id=%d", article.id)

    async def search_articles(
        self,
        company_id: int,
        query_text: str,
        top_k: int = RAG_TOP_K_RESULTS,
    ) -> List[Tuple[KnowledgeBaseArticle, float]]:
        """
        Full-text + keyword search for KB articles.
        Returns articles with relevance scores.
        """
        pattern = f"%{query_text}%"
        db_query = select(KnowledgeBaseArticle).where(
            KnowledgeBaseArticle.company_id == company_id,
            KnowledgeBaseArticle.status == "published",
        ).where(
            or_(
                KnowledgeBaseArticle.title.ilike(pattern),
                KnowledgeBaseArticle.content.ilike(pattern),
                KnowledgeBaseArticle.summary.ilike(pattern),
                KnowledgeBaseArticle.keywords.contains([query_text.lower()]),
            )
        ).limit(top_k * 2)

        result = await self.db.execute(db_query)
        articles = result.scalars().all()

        # Score articles by relevance
        scored = []
        query_words = set(query_text.lower().split())
        for article in articles:
            score = self._calculate_relevance_score(article, query_words, query_text.lower())
            scored.append((article, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _calculate_relevance_score(
        self,
        article: KnowledgeBaseArticle,
        query_words: set,
        query_lower: str,
    ) -> float:
        """Calculate a relevance score between 0 and 1."""
        score = 0.0
        title_lower = (article.title or "").lower()
        content_lower = (article.content or "").lower()
        summary_lower = (article.summary or "").lower()
        keywords = [k.lower() for k in (article.keywords or [])]
        tags = [t.lower() for t in (article.tags or [])]

        # Exact title match = highest score
        if query_lower in title_lower:
            score += 0.4

        # Title word overlap
        title_words = set(title_lower.split())
        title_overlap = len(query_words & title_words) / max(len(query_words), 1)
        score += title_overlap * 0.25

        # Keyword match
        keyword_overlap = len(query_words & set(keywords)) / max(len(query_words), 1)
        score += keyword_overlap * 0.2

        # Tag match
        tag_overlap = len(query_words & set(tags)) / max(len(query_words), 1)
        score += tag_overlap * 0.1

        # Content match
        if query_lower in content_lower:
            score += 0.05

        return min(score, 1.0)

    # -- KB Category CRUD --

    async def create_category(
        self, company_id: int, data: Dict[str, Any]
    ) -> KnowledgeBaseCategory:
        """Create a KB category."""
        category = KnowledgeBaseCategory(
            company_id=company_id,
            name=data["name"],
            description=data.get("description"),
            parent_id=data.get("parent_id"),
            sort_order=data.get("sort_order", 0),
        )
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        return category

    async def list_categories(
        self, company_id: int
    ) -> List[KnowledgeBaseCategory]:
        """List all KB categories for a company."""
        result = await self.db.execute(
            select(KnowledgeBaseCategory)
            .where(KnowledgeBaseCategory.company_id == company_id)
            .order_by(KnowledgeBaseCategory.sort_order, KnowledgeBaseCategory.name)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Macro Service
# ---------------------------------------------------------------------------

class MacroService:
    """CRUD and expansion for support macros."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_macro(
        self, company_id: int, data: Dict[str, Any]
    ) -> SupportMacro:
        """Create a new macro."""
        # Check shortcut uniqueness
        existing = await self.get_macro_by_shortcut(company_id, data["shortcut"])
        if existing:
            raise ValidationError(
                f"Macro with shortcut '{data['shortcut']}' already exists"
            )

        macro = SupportMacro(
            company_id=company_id,
            name=data["name"],
            description=data.get("description"),
            shortcut=data["shortcut"],
            content=data["content"],
            variables=data.get("variables"),
            category=data.get("category"),
            created_by=data.get("created_by"),
        )
        self.db.add(macro)
        await self.db.commit()
        await self.db.refresh(macro)
        logger.info("Created macro id=%d shortcut=%s", macro.id, macro.shortcut)
        return macro

    async def get_macro(self, macro_id: int, company_id: int) -> SupportMacro:
        """Get a macro by ID."""
        result = await self.db.execute(
            select(SupportMacro).where(
                SupportMacro.id == macro_id,
                SupportMacro.company_id == company_id,
            )
        )
        macro = result.scalar_one_or_none()
        if not macro:
            raise NotFoundError(f"Macro {macro_id} not found")
        return macro

    async def get_macro_by_shortcut(
        self, company_id: int, shortcut: str
    ) -> Optional[SupportMacro]:
        """Get a macro by its shortcut."""
        result = await self.db.execute(
            select(SupportMacro).where(
                SupportMacro.company_id == company_id,
                SupportMacro.shortcut == shortcut,
            )
        )
        return result.scalar_one_or_none()

    async def list_macros(
        self,
        company_id: int,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[SupportMacro], int]:
        """List macros for a company."""
        query = select(SupportMacro).where(
            SupportMacro.company_id == company_id
        )
        if category:
            query = query.where(SupportMacro.category == category)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(SupportMacro.name)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        macros = result.scalars().all()

        return list(macros), total

    async def update_macro(
        self,
        macro_id: int,
        company_id: int,
        data: Dict[str, Any],
    ) -> SupportMacro:
        """Update a macro."""
        macro = await self.get_macro(macro_id, company_id)

        for field in ["name", "description", "shortcut", "content", "variables", "category"]:
            if field in data and data[field] is not None:
                setattr(macro, field, data[field])

        macro.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(macro)
        return macro

    async def delete_macro(self, macro_id: int, company_id: int) -> None:
        """Hard-delete a macro."""
        macro = await self.get_macro(macro_id, company_id)
        await self.db.delete(macro)
        await self.db.commit()

    def expand_macro(
        self,
        macro: SupportMacro,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Expand a macro with variable substitution."""
        variables = variables or {}
        content = macro.content

        # Replace {{variable}} placeholders
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))

        return content


# ---------------------------------------------------------------------------
# Escalation Service
# ---------------------------------------------------------------------------

class EscalationService:
    """Evaluate escalation rules and trigger actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(
        self, company_id: int, data: Dict[str, Any]
    ) -> EscalationRule:
        """Create a new escalation rule."""
        rule = EscalationRule(
            company_id=company_id,
            name=data["name"],
            conditions=data["conditions"],
            actions=data["actions"],
            is_active=data.get("is_active", True),
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        logger.info("Created escalation rule id=%d", rule.id)
        return rule

    async def get_rule(self, rule_id: int, company_id: int) -> EscalationRule:
        """Get an escalation rule by ID."""
        result = await self.db.execute(
            select(EscalationRule).where(
                EscalationRule.id == rule_id,
                EscalationRule.company_id == company_id,
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise NotFoundError(f"Escalation rule {rule_id} not found")
        return rule

    async def list_rules(
        self, company_id: int, active_only: bool = True
    ) -> List[EscalationRule]:
        """List escalation rules for a company."""
        query = select(EscalationRule).where(
            EscalationRule.company_id == company_id
        )
        if active_only:
            query = query.where(EscalationRule.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_rule(
        self,
        rule_id: int,
        company_id: int,
        data: Dict[str, Any],
    ) -> EscalationRule:
        """Update an escalation rule."""
        rule = await self.get_rule(rule_id, company_id)

        for field in ["name", "conditions", "actions", "is_active"]:
            if field in data and data[field] is not None:
                setattr(rule, field, data[field])

        rule.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def evaluate_rules_for_ticket(
        self, ticket: SupportTicket, messages: List[SupportMessage]
    ) -> Dict[str, Any]:
        """
        Evaluate all active escalation rules against a ticket.
        Returns dict with triggered status and actions taken.
        """
        rules = await self.list_rules(ticket.company_id, active_only=True)
        triggered_rules = []
        actions_taken = []

        for rule in rules:
            if self._evaluate_conditions(rule.conditions, ticket, messages):
                triggered_rules.append(rule.id)
                rule_actions = await self._execute_actions(
                    rule.actions, ticket
                )
                actions_taken.extend(rule_actions)

        return {
            "triggered": len(triggered_rules) > 0,
            "rules_matched": triggered_rules,
            "actions_taken": actions_taken,
        }

    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        ticket: SupportTicket,
        messages: List[SupportMessage],
    ) -> bool:
        """Check if a ticket matches rule conditions."""
        # Check priority
        if "priority" in conditions:
            if ticket.priority != conditions["priority"]:
                return False

        # Check category
        if "category" in conditions:
            if ticket.category != conditions["category"]:
                return False

        # Check status
        if "status" in conditions:
            if ticket.status != conditions["status"]:
                return False

        # Check source
        if "source" in conditions:
            if ticket.source != conditions["source"]:
                return False

        # Check sentiment
        if "sentiment" in conditions and messages:
            latest_customer_msg = None
            for m in reversed(messages):
                if m.sender_type == "customer":
                    latest_customer_msg = m
                    break
            if not latest_customer_msg or latest_customer_msg.sentiment != conditions["sentiment"]:
                return False

        # Check wait time (minutes since last update)
        if "wait_time_minutes" in conditions:
            wait_time = (datetime.utcnow() - ticket.updated_at).total_seconds() / 60
            if wait_time < conditions["wait_time_minutes"]:
                return False

        # Check AI handled
        if "ai_handled" in conditions:
            if ticket.ai_handled != conditions["ai_handled"]:
                return False

        return True

    async def _execute_actions(
        self, actions: Dict[str, Any], ticket: SupportTicket
    ) -> List[str]:
        """Execute escalation actions on a ticket."""
        taken = []

        # Assign to user
        if "assign_to" in actions:
            ticket.assigned_to = actions["assign_to"]
            taken.append(f"assigned_to:{actions['assign_to']}")

        # Change priority
        if "set_priority" in actions:
            ticket.priority = actions["set_priority"]
            taken.append(f"priority_set:{actions['set_priority']}")

        # Add system message
        if "add_note" in actions:
            note = SupportMessage(
                ticket_id=ticket.id,
                sender_type="system",
                content=actions["add_note"],
                internal_note=True,
            )
            self.db.add(note)
            taken.append("note_added")

        # Change status
        if "set_status" in actions:
            ticket.status = actions["set_status"]
            taken.append(f"status_set:{actions['set_status']}")

        await self.db.flush()
        return taken


# ---------------------------------------------------------------------------
# Forbidden Response Filter
# ---------------------------------------------------------------------------

class ForbiddenResponseFilter:
    """Filter AI responses for forbidden keywords, patterns, and denylisted phrases."""

    @staticmethod
    def check_keywords(text: str) -> List[str]:
        """Check for forbidden keywords in text."""
        text_lower = text.lower()
        found = []
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in text_lower:
                found.append(keyword)
        return found

    @staticmethod
    def check_patterns(text: str) -> List[str]:
        """Check for forbidden response patterns."""
        text_lower = text.lower()
        found = []
        for pattern in FORBIDDEN_RESPONSE_PATTERNS:
            if pattern.lower() in text_lower:
                found.append(pattern)
        return found

    @staticmethod
    def check_denylist(text: str) -> List[str]:
        """Check for denylisted phrases AI should never say."""
        text_lower = text.lower()
        found = []
        for phrase in FORBIDDEN_RESPONSE_DENYLIST:
            if phrase.lower() in text_lower:
                found.append(phrase)
        return found

    @classmethod
    def filter_response(cls, text: str) -> Dict[str, Any]:
        """
        Full filter check on AI response.
        Returns dict with cleaned text and filter results.
        """
        keywords_found = cls.check_keywords(text)
        patterns_found = cls.check_patterns(text)
        denylist_found = cls.check_denylist(text)

        all_found = keywords_found + patterns_found + denylist_found
        is_blocked = bool(keywords_found) or bool(denylist_found)

        # Clean the response: replace forbidden matches with [REDACTED]
        cleaned = text
        if is_blocked:
            for item in all_found:
                cleaned = re.sub(
                    re.escape(item),
                    "[REDACTED]",
                    cleaned,
                    flags=re.IGNORECASE,
                )

        return {
            "original": text,
            "cleaned": cleaned,
            "is_blocked": is_blocked,
            "keywords_found": keywords_found,
            "patterns_found": patterns_found + denylist_found,
            "requires_human_review": is_blocked or bool(denylist_found),
        }


# ---------------------------------------------------------------------------
# Audit Log Service
# ---------------------------------------------------------------------------

class AuditLogService:
    """Log every AI reply for audit, compliance, and review."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_log(
        self,
        ticket_id: int,
        company_id: int,
        original_content: str,
        filtered_content: Optional[str],
        confidence: float,
        kb_articles_used: List[int],
        relevance_scores: Dict[str, float],
        forbidden_triggered: bool,
        forbidden_keywords_found: List[str],
        forbidden_patterns_found: List[str],
        detected_sentiment: Optional[str],
        suggested_human_takeover: bool,
        tokens_used: int,
        cost_estimate: float,
        status: str = "pending",
    ) -> AIReplyAuditLog:
        """Create an audit log entry for an AI reply."""
        log = AIReplyAuditLog(
            ticket_id=ticket_id,
            company_id=company_id,
            original_content=original_content,
            filtered_content=filtered_content,
            confidence=confidence,
            kb_articles_used=kb_articles_used,
            relevance_scores=relevance_scores,
            status=status,
            forbidden_triggered=forbidden_triggered,
            forbidden_keywords_found=forbidden_keywords_found,
            forbidden_patterns_found=forbidden_patterns_found,
            detected_sentiment=detected_sentiment,
            suggested_human_takeover=suggested_human_takeover,
            tokens_used=tokens_used,
            cost_estimate=cost_estimate,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        logger.info("Created AI reply audit log id=%d ticket=%d status=%s", log.id, ticket_id, status)
        return log

    async def update_status(
        self,
        log_id: int,
        company_id: int,
        status: str,
        reviewed_by: Optional[int] = None,
        review_note: Optional[str] = None,
    ) -> AIReplyAuditLog:
        """Update audit log status (approve/reject)."""
        result = await self.db.execute(
            select(AIReplyAuditLog).where(
                AIReplyAuditLog.id == log_id,
                AIReplyAuditLog.company_id == company_id,
            )
        )
        log = result.scalar_one_or_none()
        if not log:
            raise NotFoundError(f"Audit log {log_id} not found")

        log.status = status
        log.reviewed_by = reviewed_by
        log.reviewed_at = datetime.utcnow()
        log.review_note = review_note
        await self.db.commit()
        await self.db.refresh(log)
        logger.info("Updated audit log id=%d status=%s", log_id, status)
        return log

    async def list_logs(
        self,
        company_id: int,
        ticket_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AIReplyAuditLog], int]:
        """List audit logs with filtering."""
        query = select(AIReplyAuditLog).where(
            AIReplyAuditLog.company_id == company_id
        )
        if ticket_id:
            query = query.where(AIReplyAuditLog.ticket_id == ticket_id)
        if status:
            query = query.where(AIReplyAuditLog.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(desc(AIReplyAuditLog.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        logs = result.scalars().all()
        return list(logs), total

    async def cleanup_old_logs(self, company_id: int) -> int:
        """Delete audit logs older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
        result = await self.db.execute(
            select(AIReplyAuditLog).where(
                AIReplyAuditLog.company_id == company_id,
                AIReplyAuditLog.created_at < cutoff,
            )
        )
        old_logs = result.scalars().all()
        for log in old_logs:
            await self.db.delete(log)
        await self.db.commit()
        deleted = len(old_logs)
        logger.info("Cleaned up %d old audit logs for company=%d", deleted, company_id)
        return deleted


# ---------------------------------------------------------------------------
# Sentiment Service
# ---------------------------------------------------------------------------

class SentimentService:
    """Analyze message sentiment using OpenAI API."""

    def __init__(self, openai_service: Any):
        self.openai = openai_service

    async def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a message.
        Returns dict with sentiment label and confidence.
        """
        try:
            messages = [
                {"role": "system", "content": AI_SENTIMENT_SYSTEM_PROMPT},
                {"role": "user", "content": text[:2000]},
            ]
            result = await self.openai.create_chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=50,
            )
            raw_sentiment = result["content"].strip().lower()

            # Parse response
            if "positive" in raw_sentiment:
                sentiment = "positive"
            elif "negative" in raw_sentiment:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            return {
                "sentiment": sentiment,
                "confidence": 0.85,
                "raw": raw_sentiment,
            }
        except Exception as exc:
            logger.warning("Sentiment analysis failed: %s", str(exc))
            # Fallback to keyword-based analysis
            return self._keyword_sentiment(text)

    def _keyword_sentiment(self, text: str) -> Dict[str, Any]:
        """Fallback keyword-based sentiment analysis."""
        text_lower = text.lower()

        positive_words = ["good", "great", "excellent", "amazing", "love", "thanks", "appreciate", "happy", "best", "awesome", "perfect"]
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "horrible", "angry", "frustrated", "disappointed", "annoying", "useless", "broken", "slow", "error"]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if neg_count > pos_count:
            return {"sentiment": "negative", "confidence": 0.6, "raw": "keyword_negative"}
        elif pos_count > neg_count:
            return {"sentiment": "positive", "confidence": 0.6, "raw": "keyword_positive"}
        return {"sentiment": "neutral", "confidence": 0.5, "raw": "keyword_neutral"}


# ---------------------------------------------------------------------------
# RAG Service
# ---------------------------------------------------------------------------

class RAGService:
    """Retrieve relevant KB articles and format as LLM context."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.kb_service = KnowledgeBaseService(db)

    async def retrieve_context(
        self,
        company_id: int,
        query: str,
        top_k: int = RAG_TOP_K_RESULTS,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant KB articles for a query and format as context.
        Returns dict with formatted context, article IDs, and relevance scores.
        """
        # Search for relevant articles
        scored_articles = await self.kb_service.search_articles(
            company_id, query, top_k=top_k
        )

        # Filter by minimum relevance
        filtered = [
            (article, score)
            for article, score in scored_articles
            if score >= RAG_MIN_RELEVANCE_SCORE
        ]

        if not filtered:
            return {
                "context": "",
                "articles_used": [],
                "relevance_scores": {},
            }

        # Format context
        context_parts = []
        article_ids = []
        relevance_scores = {}

        for i, (article, score) in enumerate(filtered[:top_k], 1):
            part = f"Article {i}: {article.title}\n{article.content[:500]}"
            if article.summary:
                part = f"Article {i}: {article.title}\nSummary: {article.summary}\n{article.content[:300]}"
            context_parts.append(part)
            article_ids.append(article.id)
            relevance_scores[article.id] = round(score, 4)

        context = RAG_CONTEXT_TEMPLATE.format(context="\n\n".join(context_parts))

        return {
            "context": context,
            "articles_used": article_ids,
            "relevance_scores": relevance_scores,
        }


# ---------------------------------------------------------------------------
# AI Auto-Reply Service
# ---------------------------------------------------------------------------

class AIAutoReplyService:
    """
    Generate AI responses using RAG context with confidence scoring,
    forbidden filtering, and approval mode (default ON).

    CRITICAL: AI cevabi HICBIR ZAMAN otomatik gonderilmez.
    Her zaman onay bekler (approval mode default: True).
    """

    def __init__(self, db: AsyncSession, openai_service: Any):
        self.db = db
        self.openai = openai_service
        self.rag = RAGService(db)
        self.sentiment = SentimentService(openai_service)
        self.forbidden_filter = ForbiddenResponseFilter()
        self.audit_service = AuditLogService(db)

    async def generate_reply(
        self,
        company_id: int,
        ticket: SupportTicket,
        messages: List[SupportMessage],
        tone: str = "professional",
        max_length: int = 500,
        context_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an AI reply for a ticket using RAG.
        Returns dict with content, confidence, filtering results, and approval status.

        KURAL: AI cevabi otomatik GONDERILMEZ. Her zaman onay bekler.
        """
        # Build conversation history
        conversation_history = self._format_conversation(messages)

        # Get RAG context
        last_customer_message = self._get_last_customer_message(messages)
        query = context_override or last_customer_message or ticket.subject

        rag_result = await self.rag.retrieve_context(company_id, query)
        kb_context = rag_result["context"]

        # Analyze sentiment of last customer message
        detected_sentiment = None
        if last_customer_message:
            sentiment_result = await self.sentiment.analyze(last_customer_message)
            detected_sentiment = sentiment_result.get("sentiment")

        # Build system prompt with anti-hallucination guardrails
        system_prompt = (
            f"{AI_REPLY_SYSTEM_PROMPT}\n\n"
            f"Tone: {tone}. Keep responses under {max_length} characters.\n\n"
            f"CRITICAL RULES:\n"
            f"- NEVER say 'I don't have access to your data' or 'I cannot check your account'\n"
            f"- NEVER say 'As an AI' or 'I am an AI language model'\n"
            f"- NEVER ask for sensitive info like passwords, credit cards, or SSN\n"
            f"- If you cannot answer, suggest escalating to a human agent\n"
            f"- Only use the provided knowledge base context\n"
            f"- If the context doesn't have the answer, say so clearly\n"
        )
        if kb_context:
            system_prompt += kb_context

        # Build messages
        chat_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Ticket Subject: {ticket.subject}\n\nConversation:\n{conversation_history}\n\nGenerate a helpful response to the customer's latest message."},
        ]

        # Call OpenAI
        result = await self.openai.create_chat_completion(
            messages=chat_messages,
            temperature=0.7,
            max_tokens=min(max_length, AI_REPLY_MAX_LENGTH),
            company_id=company_id,
        )

        raw_content = result["content"].strip()

        # ==========================================
        # 1. FORBIDDEN RESPONSE FILTER
        # ==========================================
        filter_result = self.forbidden_filter.filter_response(raw_content)
        content = filter_result["cleaned"] if filter_result["is_blocked"] else raw_content
        forbidden_triggered = filter_result["is_blocked"]
        forbidden_keywords = filter_result["keywords_found"]
        forbidden_patterns = filter_result["patterns_found"]

        # ==========================================
        # 2. CONFIDENCE SCORING
        # ==========================================
        confidence = await self._score_confidence(
            content, query, len(rag_result["articles_used"])
        )

        # ==========================================
        # 3. HUMAN TAKEOVER CHECK
        # ==========================================
        human_takeover = self._should_trigger_human_takeover(
            confidence, messages, content, detected_sentiment
        )

        # ==========================================
        # 4. ESCALATION CHECK (urgent + negative)
        # ==========================================
        escalation_triggered, escalation_reason = self._check_escalation(
            ticket, detected_sentiment, confidence
        )

        # ==========================================
        # 5. AUDIT LOG - Her AI cevabi loglanir
        # ==========================================
        audit_log = await self.audit_service.create_log(
            ticket_id=ticket.id,
            company_id=company_id,
            original_content=raw_content,
            filtered_content=content if forbidden_triggered else None,
            confidence=round(confidence, 4),
            kb_articles_used=rag_result["articles_used"],
            relevance_scores=rag_result["relevance_scores"],
            forbidden_triggered=forbidden_triggered,
            forbidden_keywords_found=forbidden_keywords,
            forbidden_patterns_found=forbidden_patterns,
            detected_sentiment=detected_sentiment,
            suggested_human_takeover=human_takeover,
            tokens_used=result.get("total_tokens", 0),
            cost_estimate=result.get("cost_estimate", 0),
            status="filtered" if forbidden_triggered else "pending",
        )

        # ==========================================
        # 6. APPROVAL MODE (DEFAULT: ON)
        # ==========================================
        # AI cevabi HICBIR ZAMAN otomatik gonderilmez.
        # Her zaman onay bekler.
        requires_approval = True
        auto_sent = False

        # Eger forbidden kelime varsa, RED edilmis sayilir
        if forbidden_triggered:
            requires_approval = True

        # Eger confidence < 0.7 ise mutlaka onay bekle
        if confidence < AI_AUTO_REPLY_CONFIDENCE_THRESHOLD:
            requires_approval = True

        # Human takeover oneriliyorsa, onay bekle
        if human_takeover:
            requires_approval = True

        # Escalation trigger edilmisse, onay bekle
        if escalation_triggered:
            requires_approval = True

        # Status belirle
        approval_status = "filtered" if forbidden_triggered else "pending"

        return {
            "content": content,
            "confidence": round(confidence, 4),
            "kb_articles_used": rag_result["articles_used"],
            "relevance_scores": rag_result["relevance_scores"],
            "suggested_human_takeover": human_takeover,
            "tokens_used": result.get("total_tokens", 0),
            "cost_estimate": result.get("cost_estimate", 0),
            # Approval mode fields
            "auto_sent": auto_sent,
            "requires_approval": requires_approval,
            "approval_status": approval_status,
            # Filtering results
            "forbidden_triggered": forbidden_triggered,
            "forbidden_keywords_found": forbidden_keywords,
            "forbidden_patterns_found": forbidden_patterns,
            # Audit log
            "audit_log_id": audit_log.id,
            # Escalation
            "escalation_triggered": escalation_triggered,
            "escalation_reason": escalation_reason,
        }

    async def approve_and_send_reply(
        self,
        audit_log_id: int,
        company_id: int,
        ticket_id: int,
        reviewed_by: int,
        note: Optional[str] = None,
    ) -> SupportMessage:
        """
        Onaylanan AI cevabini mesaj olarak gonder.
        Bu fonksiyon sadece human agent onay verdikten sonra cagrilir.
        """
        # Audit log'u kontrol et
        result = await self.db.execute(
            select(AIReplyAuditLog).where(
                AIReplyAuditLog.id == audit_log_id,
                AIReplyAuditLog.company_id == company_id,
                AIReplyAuditLog.ticket_id == ticket_id,
            )
        )
        log = result.scalar_one_or_none()
        if not log:
            raise NotFoundError(f"Audit log {audit_log_id} not found")

        if log.status not in ("pending", "filtered"):
            raise ValidationError(f"Cannot approve audit log with status '{log.status}'")

        # Mesaj icerigini belirle (filtered varsa onu kullan)
        message_content = log.filtered_content or log.original_content

        # Mesaji olustur
        message = SupportMessage(
            ticket_id=ticket_id,
            sender_type="ai",
            content=message_content,
            ai_generated=True,
            ai_confidence=log.confidence,
            internal_note=False,
        )
        self.db.add(message)

        # Ticket'i guncelle
        ticket_result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = ticket_result.scalar_one_or_none()
        if ticket:
            ticket.ai_handled = True
            ticket.ai_confidence = log.confidence
            ticket.updated_at = datetime.utcnow()

        # Audit log'u guncelle
        log.status = "approved"
        log.reviewed_by = reviewed_by
        log.reviewed_at = datetime.utcnow()
        log.review_note = note

        await self.db.commit()
        await self.db.refresh(message)
        logger.info(
            "AI reply approved and sent: audit_log=%d ticket=%d by_user=%d",
            audit_log_id, ticket_id, reviewed_by,
        )
        return message

    async def reject_reply(
        self,
        audit_log_id: int,
        company_id: int,
        reviewed_by: int,
        note: Optional[str] = None,
    ) -> AIReplyAuditLog:
        """AI cevabini red et."""
        return await self.audit_service.update_status(
            log_id=audit_log_id,
            company_id=company_id,
            status="rejected",
            reviewed_by=reviewed_by,
            review_note=note,
        )

    async def score_confidence_for_message(
        self,
        content: str,
        query: str,
        article_count: int,
    ) -> float:
        """Score the confidence of an AI-generated reply."""
        return await self._score_confidence(content, query, article_count)

    async def _score_confidence(
        self,
        content: str,
        query: str,
        article_count: int,
    ) -> float:
        """Internal: score confidence of the AI reply."""
        try:
            messages = [
                {"role": "system", "content": AI_REPLY_CONFIDENCE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Query: {query}\n\nAI Response: {content[:500]}\n\nKB articles referenced: {article_count}"},
            ]
            result = await self.openai.create_chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
            )
            raw_score = result["content"].strip()
            score = float(re.findall(r"0?\.\d+", raw_score)[0])
            return max(0.0, min(1.0, score))
        except (IndexError, ValueError, Exception) as exc:
            logger.debug("Confidence scoring failed: %s", str(exc))
            # Heuristic fallback - daha katı
            if not content or len(content) < 20:
                return 0.3
            if "sorry" in content.lower() and "cannot" in content.lower():
                return 0.4
            if "I don't have" in content or "I cannot" in content:
                return 0.35
            if article_count > 0:
                return 0.75
            return 0.6

    def _should_trigger_human_takeover(
        self,
        confidence: float,
        messages: List[SupportMessage],
        content: str,
        detected_sentiment: Optional[str] = None,
    ) -> bool:
        """Determine if human takeover should be suggested."""
        # Low confidence
        if confidence < HUMAN_TAKEOVER_CONFIDENCE_THRESHOLD:
            return True

        # Negative sentiment detected
        if detected_sentiment == "negative":
            return True

        # Check for human-request keywords in customer's message
        last_customer = self._get_last_customer_message(messages)
        if last_customer:
            last_lower = last_customer.lower()
            for keyword in HUMAN_TAKEOVER_KEYWORDS:
                if keyword in last_lower:
                    return True

        # Check consecutive low-confidence AI messages
        ai_messages = [m for m in messages if m.ai_generated]
        if len(ai_messages) >= HUMAN_TAKEOVER_CONSECUTIVE_LOW_CONFIDENCE:
            recent_low = sum(
                1 for m in ai_messages[-HUMAN_TAKEOVER_CONSECUTIVE_LOW_CONFIDENCE:]
                if (m.ai_confidence or 1.0) < AI_AUTO_REPLY_CONFIDENCE_THRESHOLD
            )
            if recent_low >= HUMAN_TAKEOVER_CONSECUTIVE_LOW_CONFIDENCE:
                return True

        # Forbidden content detected
        filter_result = self.forbidden_filter.filter_response(content)
        if filter_result["requires_human_review"]:
            return True

        return False

    def _check_escalation(
        self,
        ticket: SupportTicket,
        detected_sentiment: Optional[str],
        confidence: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if escalation should be triggered.
        Returns (triggered, reason).
        """
        # Urgent priority + negative sentiment = escalate
        if ticket.priority == "urgent" and detected_sentiment == "negative":
            return True, "urgent_priority_with_negative_sentiment"

        # Urgent priority + low confidence = escalate
        if ticket.priority == "urgent" and confidence < AI_AUTO_REPLY_CONFIDENCE_THRESHOLD:
            return True, "urgent_priority_with_low_ai_confidence"

        # High priority + negative sentiment + low confidence = escalate
        if (
            ticket.priority == "high"
            and detected_sentiment == "negative"
            and confidence < AI_AUTO_REPLY_CONFIDENCE_THRESHOLD
        ):
            return True, "high_priority_negative_sentiment_low_confidence"

        return False, None

    def _format_conversation(self, messages: List[SupportMessage]) -> str:
        """Format messages for the LLM prompt."""
        lines = []
        for m in messages[-20:]:  # Last 20 messages for context
            sender = m.sender_type.capitalize()
            lines.append(f"{sender}: {m.content[:300]}")
        return "\n".join(lines)

    def _get_last_customer_message(
        self, messages: List[SupportMessage]
    ) -> Optional[str]:
        """Get the most recent customer message."""
        for m in reversed(messages):
            if m.sender_type == "customer":
                return m.content
        return None


# ---------------------------------------------------------------------------
# Support Analytics Service
# ---------------------------------------------------------------------------

class SupportAnalyticsService:
    """Aggregate and calculate support analytics metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_analytics(
        self,
        company_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[SupportAnalytics]:
        """Get daily analytics for a date range."""
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=ANALYTICS_AGGREGATION_DAYS)

        result = await self.db.execute(
            select(SupportAnalytics)
            .where(
                SupportAnalytics.company_id == company_id,
                SupportAnalytics.date >= start_date,
                SupportAnalytics.date <= end_date,
            )
            .order_by(SupportAnalytics.date)
        )
        return list(result.scalars().all())

    async def get_summary(
        self,
        company_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get aggregated analytics summary."""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get analytics rows
        result = await self.db.execute(
            select(SupportAnalytics)
            .where(
                SupportAnalytics.company_id == company_id,
                SupportAnalytics.date >= start_date,
            )
        )
        rows = result.scalars().all()

        if not rows:
            return {
                "total_tickets": 0,
                "resolved_tickets": 0,
                "open_tickets": 0,
                "avg_response_time_minutes": None,
                "avg_resolution_time_minutes": None,
                "ai_resolution_rate": None,
                "customer_satisfaction": None,
                "tickets_by_source": {},
                "tickets_by_priority": {},
                "tickets_by_status": {},
            }

        # Aggregate
        total_tickets = sum(r.total_tickets for r in rows)
        resolved_tickets = sum(r.resolved_tickets for r in rows)

        response_times = [r.avg_response_time for r in rows if r.avg_response_time is not None]
        resolution_times = [r.avg_resolution_time for r in rows if r.avg_resolution_time is not None]
        ai_rates = [r.ai_resolution_rate for r in rows if r.ai_resolution_rate is not None]
        csat_scores = [r.customer_satisfaction for r in rows if r.customer_satisfaction is not None]

        # Count current open tickets
        open_result = await self.db.execute(
            select(func.count())
            .where(
                SupportTicket.company_id == company_id,
                SupportTicket.status.in_(["open", "pending"]),
            )
        )
        open_tickets = open_result.scalar() or 0

        # Aggregate by source
        source_counts: Dict[str, int] = {}
        for r in rows:
            if r.tickets_by_source:
                for source, count in r.tickets_by_source.items():
                    source_counts[source] = source_counts.get(source, 0) + count

        # Aggregate by priority (from tickets table)
        priority_result = await self.db.execute(
            select(SupportTicket.priority, func.count())
            .where(
                SupportTicket.company_id == company_id,
                SupportTicket.created_at >= start_date,
            )
            .group_by(SupportTicket.priority)
        )
        priority_counts = {p: c for p, c in priority_result.all()}

        # Status counts
        status_result = await self.db.execute(
            select(SupportTicket.status, func.count())
            .where(SupportTicket.company_id == company_id)
            .group_by(SupportTicket.status)
        )
        status_counts = {s: c for s, c in status_result.all()}

        return {
            "total_tickets": total_tickets,
            "resolved_tickets": resolved_tickets,
            "open_tickets": open_tickets,
            "avg_response_time_minutes": round(sum(response_times) / len(response_times), 2) if response_times else None,
            "avg_resolution_time_minutes": round(sum(resolution_times) / len(resolution_times), 2) if resolution_times else None,
            "ai_resolution_rate": round(sum(ai_rates) / len(ai_rates), 4) if ai_rates else None,
            "customer_satisfaction": round(sum(csat_scores) / len(csat_scores), 2) if csat_scores else None,
            "tickets_by_source": source_counts,
            "tickets_by_priority": priority_counts,
            "tickets_by_status": status_counts,
        }

    async def aggregate_daily(self, company_id: int, date: datetime) -> SupportAnalytics:
        """Aggregate analytics for a specific day."""
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Count total tickets
        total_result = await self.db.execute(
            select(func.count())
            .where(
                SupportTicket.company_id == company_id,
                SupportTicket.created_at >= day_start,
                SupportTicket.created_at < day_end,
            )
        )
        total_tickets = total_result.scalar() or 0

        # Count resolved
        resolved_result = await self.db.execute(
            select(func.count())
            .where(
                SupportTicket.company_id == company_id,
                SupportTicket.resolved_at >= day_start,
                SupportTicket.resolved_at < day_end,
            )
        )
        resolved_tickets = resolved_result.scalar() or 0

        # AI resolved count
        ai_resolved_result = await self.db.execute(
            select(func.count())
            .where(
                SupportTicket.company_id == company_id,
                SupportTicket.resolved_at >= day_start,
                SupportTicket.resolved_at < day_end,
                SupportTicket.ai_handled.is_(True),
            )
        )
        ai_resolved = ai_resolved_result.scalar() or 0

        ai_rate = ai_resolved / resolved_tickets if resolved_tickets > 0 else None

        analytics = SupportAnalytics(
            company_id=company_id,
            date=day_start,
            total_tickets=total_tickets,
            resolved_tickets=resolved_tickets,
            ai_resolution_rate=ai_rate,
        )
        self.db.add(analytics)
        await self.db.commit()
        await self.db.refresh(analytics)
        return analytics


# ---------------------------------------------------------------------------
# Conversation Service
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Admin Alert Service
# ---------------------------------------------------------------------------

class AdminAlertService:
    """Send admin alerts for important events (escalation, errors, SLA breach).

    Supports multiple notification channels: in-app, email (placeholder),
    and webhook. Alerts are scoped by company/branch for multi-tenant
    isolation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_alert(
        self,
        company_id: int,
        alert_type: str,
        title: str,
        message: str,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send an admin alert through configured channels.

        Args:
            company_id: Tenant company ID.
            alert_type: Type of alert (escalation, error, sla_breach,
                        human_takeover, high_priority).
            title: Alert title.
            message: Alert body.
            branch_id: Optional branch scope.
            metadata: Additional context (ticket_id, user_id, etc.).
            channels: Notification channels (in_app, email, webhook).

        Returns:
            Dict with delivery results per channel.
        """
        channels = channels or ["in_app"]
        results: Dict[str, Any] = {}

        for channel in channels:
            try:
                if channel == "in_app":
                    results["in_app"] = await self._send_in_app_alert(
                        company_id, alert_type, title, message, branch_id, metadata
                    )
                elif channel == "email":
                    results["email"] = await self._send_email_alert(
                        company_id, title, message, branch_id, metadata
                    )
                elif channel == "webhook":
                    results["webhook"] = await self._send_webhook_alert(
                        company_id, title, message, metadata
                    )
            except Exception as exc:
                logger.error("Alert channel %s failed: %s", channel, exc)
                results[channel] = {"sent": False, "error": str(exc)}

        logger.info(
            "Admin alert sent: type=%s company=%d branches=%s channels=%s",
            alert_type, company_id, branch_id, channels,
        )
        return results

    async def alert_escalation(
        self,
        company_id: int,
        ticket_id: int,
        reason: str,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alert admins when a ticket is escalated.

        Args:
            company_id: Tenant company ID.
            ticket_id: Escalated ticket ID.
            reason: Escalation reason.
            branch_id: Optional branch scope.

        Returns:
            Delivery results.
        """
        return await self.send_alert(
            company_id=company_id,
            alert_type="escalation",
            title=f"Ticket #{ticket_id} Escalated",
            message=f"Ticket #{ticket_id} has been escalated. Reason: {reason}",
            branch_id=branch_id,
            metadata={"ticket_id": ticket_id, "reason": reason},
            channels=["in_app", "email"],
        )

    async def alert_human_takeover(
        self,
        company_id: int,
        ticket_id: int,
        agent_id: int,
        reason: str,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alert admins when AI hands over to human agent.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket ID.
            agent_id: Human agent user ID.
            reason: Takeover reason.
            branch_id: Optional branch scope.

        Returns:
            Delivery results.
        """
        return await self.send_alert(
            company_id=company_id,
            alert_type="human_takeover",
            title=f"Human Takeover: Ticket #{ticket_id}",
            message=(
                f"Ticket #{ticket_id} has been transferred to human "
                f"agent (ID: {agent_id}). Reason: {reason}"
            ),
            branch_id=branch_id,
            metadata={"ticket_id": ticket_id, "agent_id": agent_id, "reason": reason},
            channels=["in_app"],
        )

    async def alert_sla_breach(
        self,
        company_id: int,
        ticket_id: int,
        sla_type: str,  # 'response' or 'resolution'
        minutes_overdue: int,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alert admins when an SLA is breached.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket ID.
            sla_type: 'response' or 'resolution'.
            minutes_overdue: Minutes past SLA target.
            branch_id: Optional branch scope.

        Returns:
            Delivery results.
        """
        return await self.send_alert(
            company_id=company_id,
            alert_type="sla_breach",
            title=f"SLA Breach: Ticket #{ticket_id}",
            message=(
                f"Ticket #{ticket_id} has breached the {sla_type} SLA "
                f"by {minutes_overdue} minutes."
            ),
            branch_id=branch_id,
            metadata={
                "ticket_id": ticket_id,
                "sla_type": sla_type,
                "minutes_overdue": minutes_overdue,
            },
            channels=["in_app", "email"],
        )

    async def alert_high_priority(
        self,
        company_id: int,
        ticket_id: int,
        priority: str,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alert admins when a high/urgent priority ticket is created.

        Args:
            company_id: Tenant company ID.
            ticket_id: Ticket ID.
            priority: Ticket priority level.
            branch_id: Optional branch scope.

        Returns:
            Delivery results.
        """
        return await self.send_alert(
            company_id=company_id,
            alert_type="high_priority",
            title=f"High Priority Ticket: #{ticket_id} ({priority.upper()})",
            message=f"A new {priority.upper()} priority ticket #{ticket_id} requires immediate attention.",
            branch_id=branch_id,
            metadata={"ticket_id": ticket_id, "priority": priority},
            channels=["in_app", "email"],
        )

    async def alert_api_error(
        self,
        company_id: int,
        platform: str,
        error_message: str,
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Alert admins when a platform API error occurs.

        Args:
            company_id: Tenant company ID.
            platform: Platform name (whatsapp, telegram, etc.).
            error_message: Error description.
            account_id: Optional affected account ID.

        Returns:
            Delivery results.
        """
        return await self.send_alert(
            company_id=company_id,
            alert_type="api_error",
            title=f"API Error: {platform.title()}",
            message=f"{platform.title()} API error: {error_message}",
            metadata={"platform": platform, "account_id": account_id, "error": error_message},
            channels=["in_app"],
        )

    # -- Private channel senders --

    async def _send_in_app_alert(
        self,
        company_id: int,
        alert_type: str,
        title: str,
        message: str,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store an in-app notification in the database.

        Uses the escalation mechanism: adds a system message to
        open/pending tickets that admins monitor.
        """
        from sqlalchemy import select as sa_select
        from app.support.models import SupportTicket, SupportMessage

        # Find the most recently active ticket for this company/branch
        query = sa_select(SupportTicket).where(
            SupportTicket.company_id == company_id,
            SupportTicket.status.in_(["open", "pending"]),
        ).order_by(desc(SupportTicket.updated_at)).limit(1)

        result = await self.db.execute(query)
        ticket = result.scalar_one_or_none()

        if ticket:
            note = SupportMessage(
                ticket_id=ticket.id,
                sender_type="system",
                content=f"[ADMIN ALERT - {alert_type.upper()}] {title}: {message}",
                internal_note=True,
            )
            self.db.add(note)
            await self.db.commit()
            return {"sent": True, "ticket_id": ticket.id}

        # No active ticket - create a dedicated admin alert ticket
        ticket_service = TicketService(self.db)
        alert_ticket = await ticket_service.create_ticket(
            company_id=company_id,
            branch_id=branch_id,
            data={
                "customer_id": "system",
                "customer_name": "System Alert",
                "source": "web",
                "subject": f"[ALERT] {title}",
                "initial_message": message,
                "priority": "high" if alert_type in ("sla_breach", "escalation") else "medium",
                "category": "general",
                "tags": ["admin_alert", alert_type],
            },
        )

        # Attach metadata
        if metadata:
            meta_msg = SupportMessage(
                ticket_id=alert_ticket.id,
                sender_type="system",
                content=f"Metadata: {json.dumps(metadata)}",
                internal_note=True,
            )
            self.db.add(meta_msg)
            await self.db.commit()

        return {"sent": True, "ticket_id": alert_ticket.id, "created_alert_ticket": True}

    async def _send_email_alert(
        self,
        company_id: int,
        title: str,
        message: str,
        branch_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send email alert (placeholder - integrate with email provider).

        Args:
            company_id: Tenant company ID.
            title: Email subject.
            message: Email body.
            branch_id: Optional branch scope.
            metadata: Additional context.

        Returns:
            Delivery result placeholder.
        """
        # TODO: Integrate with SendGrid/AWS SES/email service
        # For now, log the intent and store for later processing
        logger.info(
            "[EMAIL ALERT] company=%d branch=%s title=%s msg=%s",
            company_id, branch_id, title, message[:200],
        )
        return {"sent": True, "note": "Email integration placeholder - logged only"}

    async def _send_webhook_alert(
        self,
        company_id: int,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send alert via external webhook (e.g. Slack, Discord).

        Args:
            company_id: Tenant company ID.
            title: Alert title.
            message: Alert body.
            metadata: Additional context.

        Returns:
            Delivery result.
        """
        import httpx

        webhook_url = getattr(settings, "ADMIN_ALERT_WEBHOOK_URL", None)
        if not webhook_url:
            return {"sent": False, "error": "No webhook URL configured"}

        payload = {
            "text": f"*{title}*\n{message}",
            "company_id": company_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
            return {"sent": True}
        except Exception as exc:
            logger.error("Webhook alert failed: %s", exc)
            return {"sent": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Conversation Service
# ---------------------------------------------------------------------------

class ConversationService:
    """Manage multi-channel conversation threads in a unified view."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_conversations(
        self,
        company_id: int,
        branch_id: Optional[int] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List conversations in unified view."""
        query = select(SupportTicket).where(
            SupportTicket.company_id == company_id
        )

        if branch_id is not None:
            query = query.where(
                (SupportTicket.branch_id == branch_id)
                | (SupportTicket.branch_id.is_(None))
            )
        if source:
            query = query.where(SupportTicket.source == source)

        # Exclude closed tickets from active conversations
        query = query.where(SupportTicket.status != "closed")

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(desc(SupportTicket.updated_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        tickets = result.scalars().all()

        conversations = []
        for ticket in tickets:
            msg_count_result = await self.db.execute(
                select(func.count())
                .where(SupportMessage.ticket_id == ticket.id)
            )
            msg_count = msg_count_result.scalar() or 0

            conversations.append({
                "ticket_id": ticket.id,
                "customer_name": ticket.customer_name,
                "customer_email": ticket.customer_email,
                "source": ticket.source,
                "subject": ticket.subject,
                "status": ticket.status,
                "priority": ticket.priority,
                "last_message_at": ticket.updated_at,
                "message_count": msg_count,
                "ai_handled": ticket.ai_handled,
                "assigned_to": ticket.assigned_to,
                "source_conversation_id": ticket.source_conversation_id,
            })

        return conversations, total

    async def get_conversation_messages(
        self,
        ticket_id: int,
        company_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get messages for a specific conversation."""
        # Verify ticket
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Conversation {ticket_id} not found")

        query = select(SupportMessage).where(
            SupportMessage.ticket_id == ticket_id,
            SupportMessage.internal_note.is_(False),
        )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(SupportMessage.created_at)
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        messages = result.scalars().all()

        conversation_messages = []
        for msg in messages:
            sender_name = None
            if msg.sender_type == "customer":
                sender_name = ticket.customer_name or "Customer"
            elif msg.sender_type == "agent":
                sender_name = f"Agent ({msg.sender_id})"
            elif msg.sender_type == "ai":
                sender_name = "AI Assistant"
            elif msg.sender_type == "system":
                sender_name = "System"

            conversation_messages.append({
                "id": msg.id,
                "sender_type": msg.sender_type,
                "sender_name": sender_name,
                "content": msg.content,
                "ai_generated": msg.ai_generated,
                "sentiment": msg.sentiment,
                "created_at": msg.created_at,
            })

        return conversation_messages, total

    async def reply_to_conversation(
        self,
        ticket_id: int,
        company_id: int,
        content: str,
        sender_id: Optional[int] = None,
        ai_generated: bool = False,
        ai_confidence: Optional[float] = None,
    ) -> SupportMessage:
        """Add a reply to a conversation."""
        result = await self.db.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.company_id == company_id,
            )
        )
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise NotFoundError(f"Conversation {ticket_id} not found")

        if ticket.status == "closed":
            raise ValidationError("Cannot reply to a closed conversation")

        # GUVENLIK: AI sender_type ile dogrudan mesaj eklemeyi engelle
        # AI mesajlari sadece approve endpoint'i ile gonderilir
        if ai_generated:
            raise ValidationError(
                "AI-generated messages cannot be sent directly. "
                "Use the approve endpoint after generating an AI reply."
            )

        message = SupportMessage(
            ticket_id=ticket_id,
            sender_type="agent",
            sender_id=sender_id,
            content=content,
            ai_generated=False,
            ai_confidence=ai_confidence,
            internal_note=False,
        )
        self.db.add(message)

        ticket.updated_at = datetime.utcnow()
        if ticket.status == "open":
            ticket.status = "pending"

        await self.db.commit()
        await self.db.refresh(message)
        logger.info("Replied to conversation ticket=%d", ticket_id)
        return message


