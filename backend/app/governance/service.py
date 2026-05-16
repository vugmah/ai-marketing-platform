"""GDPR/KVKK data export and deletion service.

Implements:
- Full user data export (Article 20: Right to Data Portability)
- Complete user data hard deletion (Article 17: Right to be Forgotten)
- Company/branch archiving with cascade soft-delete
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import (
    AIConversation,
    AIMessage,
    AIRecommendation,
    AISuggestion,
    AIUsageLog,
)
from app.analytics.models import AnalyticsSnapshot
from app.audit.models import AuditLog, DataAccessLog, LoginAttempt
from app.auth.models import User
from app.branches.models import Branch, BranchConfig
from app.companies.models import Company
from app.events.models import EventLog
from app.governance.models import (
    GDPRDeletionRequest,
    GDPRDeletionRequest as GDPRDeletionRequestModel,
    GDPRRequestStatus,
    GDPRExportRequest,
    GDPRExportRequest as GDPRExportRequestModel,
    GDPRRequestType,
)
from app.governance.schemas import (
    GDPRDeleteRequest,
    GDPRDeleteResponse,
    GDPRUserDataExport,
    GDPRExportResponse,
)
from app.media.models import MediaAsset
from app.social.models import SocialPost


# =============================================================================
# GDPR Service
# =============================================================================


class GDPRService:
    """Service for GDPR/KVKK compliance operations.

    Handles data export (Article 20) and data deletion (Article 17)
    for individual users across all modules.
    """

    # Tables to query for user-related data, mapped by scope
    SCOPE_TABLES = {
        "user": ["users"],
        "company": ["companies"],
        "branch": ["branches", "branch_configs"],
        "ai": ["ai_conversations", "ai_messages", "ai_suggestions", "ai_recommendations", "ai_usage_logs"],
        "ads": ["ad_campaigns", "ad_creatives", "ad_platforms", "ad_adsets"],
        "audit": ["audit_logs", "login_attempts", "data_access_logs"],
        "events": ["event_log"],
        "social": ["social_media_posts"],
        "media": ["media_files"],
        "analytics": ["analytics_snapshots"],
    }

    @staticmethod
    async def export_user_data(
        db: AsyncSession,
        user_id: int,
        company_id: int,
        scopes: List[str],
        requested_by: int,
    ) -> Dict[str, Any]:
        """Export all user data for GDPR/KVKK Article 20 compliance.

        Aggregates data from all relevant tables scoped to the user
        and returns a comprehensive JSON structure.

        Args:
            db: Async database session.
            user_id: The user whose data is being exported.
            company_id: The user's company ID.
            scopes: List of data scopes to include.
            requested_by: User ID who initiated the export.

        Returns:
            Complete user data export as a dictionary.
        """
        export_request = GDPRExportRequestModel(
            company_id=company_id,
            user_id=user_id,
            requested_by=requested_by if requested_by != user_id else None,
            request_type=GDPRRequestType.EXPORT,
            status=GDPRRequestStatus.PROCESSING,
            data_scope=scopes,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(export_request)
        await db.commit()
        await db.refresh(export_request)

        include_all = "all" in scopes
        result_data: Dict[str, Any] = {
            "export_metadata": {
                "export_id": export_request.id,
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "company_id": company_id,
                "scopes": scopes,
                "version": "2.0.0",
                "legal_basis": "GDPR Article 20 / KVKK Maddesi 11",
            },
            "user": None,
            "company": None,
            "branches": [],
            "ai_conversations": [],
            "ai_messages": [],
            "ai_suggestions": [],
            "ai_recommendations": [],
            "ai_usage_logs": [],
            "ad_campaigns": [],
            "ad_creatives": [],
            "audit_logs": [],
            "login_attempts": [],
            "data_access_logs": [],
            "event_logs": [],
            "social_posts": [],
            "media_files": [],
        }

        total_records = 0

        # --- User profile ---
        if include_all or "user" in scopes:
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                result_data["user"] = {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "role": user.role.value if user.role else None,
                    "status": user.status.value if user.status else None,
                    "company_id": user.company_id,
                    "branch_id": user.branch_id,
                    "is_active": user.is_active,
                    "email_verified": user.email_verified,
                    "last_login_at": (
                        user.last_login_at.isoformat() if user.last_login_at else None
                    ),
                    "created_at": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                    "updated_at": (
                        user.updated_at.isoformat() if user.updated_at else None
                    ),
                }
                total_records += 1

        # --- Company data ---
        if include_all or "company" in scopes:
            company_result = await db.execute(
                select(Company).where(Company.id == company_id)
            )
            company = company_result.scalar_one_or_none()
            if company:
                result_data["company"] = {
                    "id": company.id,
                    "name": company.name,
                    "slug": company.slug,
                    "description": company.description,
                    "email": company.email,
                    "phone": company.phone,
                    "website": company.website,
                    "plan": company.plan.value if company.plan else None,
                    "subscription_status": (
                        company.subscription_status.value
                        if company.subscription_status
                        else None
                    ),
                    "timezone": company.timezone,
                    "currency": company.currency,
                    "language": company.language,
                    "is_active": company.is_active,
                    "created_at": (
                        company.created_at.isoformat() if company.created_at else None
                    ),
                    "updated_at": (
                        company.updated_at.isoformat() if company.updated_at else None
                    ),
                }
                total_records += 1

        # --- Branch data ---
        if include_all or "branch" in scopes:
            branch_result = await db.execute(
                select(Branch).where(
                    Branch.company_id == company_id,
                    Branch.id == user.branch_id if user and user.branch_id else True,
                )
            )
            branches = branch_result.scalars().all()
            for branch in branches:
                result_data["branches"].append(
                    {
                        "id": branch.id,
                        "name": branch.name,
                        "city": branch.city,
                        "address": branch.address,
                        "type": branch.type.value if branch.type else None,
                        "status": branch.status.value if branch.status else None,
                        "manager_name": branch.manager_name,
                        "manager_email": branch.manager_email,
                        "manager_phone": branch.manager_phone,
                        "created_at": (
                            branch.created_at.isoformat() if branch.created_at else None
                        ),
                    }
                )
                total_records += 1

        # --- AI module data ---
        if include_all or "ai" in scopes:
            # Conversations
            conv_result = await db.execute(
                select(AIConversation).where(AIConversation.user_id == user_id)
            )
            for conv in conv_result.scalars().all():
                result_data["ai_conversations"].append(
                    {
                        "id": conv.id,
                        "session_id": conv.session_id,
                        "title": conv.title,
                        "model": conv.model.value if conv.model else None,
                        "total_tokens": conv.total_tokens,
                        "status": conv.status.value if conv.status else None,
                        "created_at": (
                            conv.created_at.isoformat() if conv.created_at else None
                        ),
                    }
                )
                total_records += 1

            # Messages (via conversations)
            conv_ids = [c.id for c in conv_result.scalars().all()]
            if conv_ids:
                msg_result = await db.execute(
                    select(AIMessage).where(AIMessage.conversation_id.in_(conv_ids))
                )
                for msg in msg_result.scalars().all():
                    result_data["ai_messages"].append(
                        {
                            "id": msg.id,
                            "conversation_id": msg.conversation_id,
                            "role": msg.role.value if msg.role else None,
                            "content": msg.content,
                            "tokens": msg.tokens,
                            "model": msg.model.value if msg.model else None,
                            "created_at": (
                                msg.created_at.isoformat() if msg.created_at else None
                            ),
                        }
                    )
                    total_records += 1

            # Suggestions
            sug_result = await db.execute(
                select(AISuggestion).where(
                    AISuggestion.company_id == company_id,
                )
            )
            for sug in sug_result.scalars().all():
                result_data["ai_suggestions"].append(
                    {
                        "id": sug.id,
                        "trigger_type": (
                            sug.trigger_type.value if sug.trigger_type else None
                        ),
                        "context": sug.context,
                        "response": sug.response,
                        "tokens_used": sug.tokens_used,
                        "model": sug.model.value if sug.model else None,
                        "was_applied": sug.was_applied,
                        "user_feedback": (
                            sug.user_feedback.value if sug.user_feedback else None
                        ),
                        "created_at": (
                            sug.created_at.isoformat() if sug.created_at else None
                        ),
                    }
                )
                total_records += 1

            # Recommendations
            rec_result = await db.execute(
                select(AIRecommendation).where(
                    AIRecommendation.company_id == company_id,
                )
            )
            for rec in rec_result.scalars().all():
                result_data["ai_recommendations"].append(
                    {
                        "id": rec.id,
                        "category": rec.category.value if rec.category else None,
                        "title": rec.title,
                        "description": rec.description,
                        "confidence_score": rec.confidence_score,
                        "status": rec.status.value if rec.status else None,
                        "created_at": (
                            rec.created_at.isoformat() if rec.created_at else None
                        ),
                    }
                )
                total_records += 1

            # Usage logs
            usage_result = await db.execute(
                select(AIUsageLog).where(AIUsageLog.user_id == user_id)
            )
            for usage in usage_result.scalars().all():
                result_data["ai_usage_logs"].append(
                    {
                        "id": usage.id,
                        "model": usage.model.value if usage.model else None,
                        "endpoint": usage.endpoint,
                        "tokens_input": usage.tokens_input,
                        "tokens_output": usage.tokens_output,
                        "cost_estimate": usage.cost_estimate,
                        "latency_ms": usage.latency_ms,
                        "status": usage.status,
                        "created_at": (
                            usage.created_at.isoformat() if usage.created_at else None
                        ),
                    }
                )
                total_records += 1

        # --- Audit data ---
        if include_all or "audit" in scopes:
            audit_result = await db.execute(
                select(AuditLog).where(AuditLog.user_id == user_id)
            )
            for log in audit_result.scalars().all():
                result_data["audit_logs"].append(
                    {
                        "id": log.id,
                        "action": log.action.value if log.action else None,
                        "resource_type": (
                            log.resource_type.value if log.resource_type else None
                        ),
                        "resource_id": log.resource_id,
                        "details": log.details,
                        "ip_address": log.ip_address,
                        "status": log.status,
                        "created_at": (
                            log.created_at.isoformat() if log.created_at else None
                        ),
                    }
                )
                total_records += 1

            login_result = await db.execute(
                select(LoginAttempt).where(LoginAttempt.email == user.email if user else False)
            )
            for login in login_result.scalars().all():
                result_data["login_attempts"].append(
                    {
                        "id": login.id,
                        "email": login.email,
                        "ip_address": login.ip_address,
                        "status": login.status.value if login.status else None,
                        "failure_reason": login.failure_reason,
                        "created_at": (
                            login.created_at.isoformat() if login.created_at else None
                        ),
                    }
                )
                total_records += 1

            dal_result = await db.execute(
                select(DataAccessLog).where(DataAccessLog.user_id == user_id)
            )
            for dal in dal_result.scalars().all():
                result_data["data_access_logs"].append(
                    {
                        "id": dal.id,
                        "table_name": dal.table_name,
                        "record_id": dal.record_id,
                        "action": dal.action.value if dal.action else None,
                        "accessed_fields": dal.accessed_fields,
                        "reason": dal.reason,
                        "created_at": (
                            dal.created_at.isoformat() if dal.created_at else None
                        ),
                    }
                )
                total_records += 1

        # --- Event logs ---
        if include_all or "events" in scopes:
            event_result = await db.execute(
                select(EventLog).where(EventLog.source_user_id == user_id)
            )
            for event in event_result.scalars().all():
                result_data["event_logs"].append(
                    {
                        "id": event.id,
                        "event_name": event.event_name,
                        "payload": event.payload,
                        "source_module": event.source_module,
                        "status": event.status,
                        "created_at": (
                            event.created_at.isoformat() if event.created_at else None
                        ),
                    }
                )
                total_records += 1

        # --- Social media posts ---
        if include_all or "social" in scopes:
            social_result = await db.execute(
                select(SocialPost).where(SocialPost.company_id == company_id)
            )
            for post in social_result.scalars().all():
                result_data["social_posts"].append(
                    {
                        "id": post.id,
                        "platform": post.platform.value if post.platform else None,
                        "content": post.content,
                        "status": post.status.value if post.status else None,
                        "created_at": (
                            post.created_at.isoformat() if post.created_at else None
                        ),
                    }
                )
                total_records += 1

        # --- Media files ---
        if include_all or "media" in scopes:
            media_result = await db.execute(
                select(MediaAsset).where(
                    (MediaAsset.company_id == company_id)
                    & (MediaAsset.created_by == user_id)
                )
            )
            for media in media_result.scalars().all():
                result_data["media_files"].append(
                    {
                        "id": media.id,
                        "filename": media.filename,
                        "mime_type": media.mime_type,
                        "file_size": media.file_size,
                        "file_path": media.file_path,
                        "created_at": (
                            media.created_at.isoformat() if media.created_at else None
                        ),
                    }
                )
                total_records += 1

        # Update export request
        export_request.status = GDPRRequestStatus.COMPLETED
        export_request.record_count = total_records
        export_request.completed_at = datetime.utcnow()
        await db.commit()

        result_data["export_metadata"]["total_records"] = total_records
        return result_data

    @staticmethod
    async def delete_user_data(
        db: AsyncSession,
        user_id: int,
        company_id: int,
        scopes: List[str],
        requested_by: int,
    ) -> Dict[str, int]:
        """Hard delete all user data for GDPR/KVKK Article 17 compliance.

        Permanently deletes user-related records from all scoped tables.
        This operation is IRREVERSIBLE.

        Args:
            db: Async database session.
            user_id: The user whose data will be deleted.
            company_id: The user's company ID.
            scopes: List of data scopes to delete.
            requested_by: User ID who initiated the deletion.

        Returns:
            Dictionary mapping table names to deleted record counts.
        """
        deletion_request = GDPRDeletionRequestModel(
            company_id=company_id,
            user_id=user_id,
            requested_by=requested_by if requested_by != user_id else None,
            request_type=GDPRRequestType.DELETION,
            status=GDPRRequestStatus.PROCESSING,
            started_at=datetime.utcnow(),
        )
        db.add(deletion_request)
        await db.commit()
        await db.refresh(deletion_request)

        include_all = "all" in scopes
        affected: Dict[str, int] = {}

        try:
            # --- AI module data ---
            if include_all or "ai" in scopes:
                # Delete messages via conversation IDs
                conv_result = await db.execute(
                    select(AIConversation.id).where(AIConversation.user_id == user_id)
                )
                conv_ids = [row[0] for row in conv_result.all()]

                if conv_ids:
                    msg_del = await db.execute(
                        delete(AIMessage).where(AIMessage.conversation_id.in_(conv_ids))
                    )
                    affected["ai_messages"] = msg_del.rowcount

                    conv_del = await db.execute(
                        delete(AIConversation).where(AIConversation.id.in_(conv_ids))
                    )
                    affected["ai_conversations"] = conv_del.rowcount

                # AI suggestions
                sug_del = await db.execute(
                    delete(AISuggestion).where(AISuggestion.company_id == company_id)
                )
                affected["ai_suggestions"] = sug_del.rowcount

                # AI recommendations
                rec_del = await db.execute(
                    delete(AIRecommendation).where(
                        AIRecommendation.company_id == company_id
                    )
                )
                affected["ai_recommendations"] = rec_del.rowcount

                # AI usage logs
                usage_del = await db.execute(
                    delete(AIUsageLog).where(AIUsageLog.user_id == user_id)
                )
                affected["ai_usage_logs"] = usage_del.rowcount

            # --- Audit data ---
            if include_all or "audit" in scopes:
                audit_del = await db.execute(
                    delete(AuditLog).where(AuditLog.user_id == user_id)
                )
                affected["audit_logs"] = audit_del.rowcount

                # Get user email for login attempts
                user_result = await db.execute(
                    select(User.email).where(User.id == user_id)
                )
                user_email = user_result.scalar_one_or_none()
                if user_email:
                    login_del = await db.execute(
                        delete(LoginAttempt).where(LoginAttempt.email == user_email)
                    )
                    affected["login_attempts"] = login_del.rowcount

                dal_del = await db.execute(
                    delete(DataAccessLog).where(DataAccessLog.user_id == user_id)
                )
                affected["data_access_logs"] = dal_del.rowcount

            # --- Event logs ---
            if include_all or "events" in scopes:
                event_del = await db.execute(
                    delete(EventLog).where(EventLog.source_user_id == user_id)
                )
                affected["event_logs"] = event_del.rowcount

            # --- Media files ---
            if include_all or "media" in scopes:
                media_del = await db.execute(
                    delete(MediaAsset).where(MediaAsset.created_by == user_id)
                )
                affected["media_files"] = media_del.rowcount

            # --- Analytics snapshots ---
            if include_all or "analytics" in scopes:
                snap_del = await db.execute(
                    delete(AnalyticsSnapshot).where(
                        AnalyticsSnapshot.company_id == company_id
                    )
                )
                affected["analytics_snapshots"] = snap_del.rowcount

            # --- User record (delete last after all FK refs are cleared) ---
            if include_all or "user" in scopes:
                user_del = await db.execute(
                    delete(User).where(User.id == user_id)
                )
                affected["users"] = user_del.rowcount

            # Update deletion request
            total_deleted = sum(affected.values())
            deletion_request.status = GDPRRequestStatus.COMPLETED
            deletion_request.records_deleted = total_deleted
            deletion_request.affected_tables = affected
            deletion_request.completed_at = datetime.utcnow()
            await db.commit()

            return affected

        except Exception as exc:
            deletion_request.status = GDPRRequestStatus.FAILED
            deletion_request.error_message = str(exc)
            await db.commit()
            raise


# =============================================================================
# Archive Service
# =============================================================================


class ArchiveService:
    """Service for company and branch archiving operations.

    Implements soft-delete cascading for company/branch archiving
    with full audit trail.
    """

    @staticmethod
    async def archive_company(
        db: AsyncSession,
        company_id: int,
        archived_by: int,
    ) -> Dict[str, Any]:
        """Archive a company and all related entities (soft-delete cascade).

        Args:
            db: Async database session.
            company_id: Company to archive.
            archived_by: User ID performing the archive.

        Returns:
            Archive statistics (affected branches, users).
        """
        from datetime import datetime

        now = datetime.utcnow()

        # 1. Archive the company
        company_result = await db.execute(
            select(Company).where(Company.id == company_id)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        company.is_active = False
        # Company model doesn't have archive fields, so we use soft-delete pattern
        # via a metadata approach
        await db.commit()

        # 2. Soft-delete all branches
        branch_result = await db.execute(
            select(Branch).where(Branch.company_id == company_id)
        )
        branches = branch_result.scalars().all()
        affected_branches = 0
        for branch in branches:
            branch.is_active = False
            affected_branches += 1

        # 3. Deactivate all users
        user_result = await db.execute(
            select(User).where(User.company_id == company_id)
        )
        users = user_result.scalars().all()
        affected_users = 0
        for user in users:
            user.is_active = False
            affected_users += 1

        await db.commit()

        return {
            "company_id": company_id,
            "is_archived": True,
            "archived_at": now,
            "archived_by": archived_by,
            "affected_branches": affected_branches,
            "affected_users": affected_users,
        }

    @staticmethod
    async def archive_branch(
        db: AsyncSession,
        branch_id: int,
        company_id: int,
        archived_by: int,
    ) -> Dict[str, Any]:
        """Archive a branch and deactivate its users.

        Args:
            db: Async database session.
            branch_id: Branch to archive.
            company_id: Parent company ID for validation.
            archived_by: User ID performing the archive.

        Returns:
            Archive statistics.
        """
        from datetime import datetime

        now = datetime.utcnow()

        # 1. Archive the branch
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
            )
        )
        branch = branch_result.scalar_one_or_none()
        if not branch:
            raise ValueError(f"Branch {branch_id} not found in company {company_id}")

        branch.is_active = False

        # 2. Deactivate users in this branch
        user_result = await db.execute(
            select(User).where(User.branch_id == branch_id)
        )
        users = user_result.scalars().all()
        affected_users = 0
        for user in users:
            user.is_active = False
            user.branch_id = None
            affected_users += 1

        await db.commit()

        return {
            "branch_id": branch_id,
            "company_id": company_id,
            "is_archived": True,
            "archived_at": now,
            "archived_by": archived_by,
            "affected_users": affected_users,
        }

    @staticmethod
    async def unarchive_company(
        db: AsyncSession,
        company_id: int,
    ) -> Dict[str, Any]:
        """Restore an archived company.

        Args:
            db: Async database session.
            company_id: Company to restore.

        Returns:
            Restoration status.
        """
        company_result = await db.execute(
            select(Company).where(Company.id == company_id)
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise ValueError(f"Company {company_id} not found")

        company.is_active = True

        # Restore branches
        branch_result = await db.execute(
            select(Branch).where(Branch.company_id == company_id)
        )
        for branch in branch_result.scalars().all():
            branch.is_active = True

        # Note: We don't auto-reactivate users for security

        await db.commit()

        return {
            "company_id": company_id,
            "is_archived": False,
            "is_deleted": False,
            "restored_at": datetime.utcnow(),
        }

    @staticmethod
    async def unarchive_branch(
        db: AsyncSession,
        branch_id: int,
        company_id: int,
    ) -> Dict[str, Any]:
        """Restore an archived branch.

        Args:
            db: Async database session.
            branch_id: Branch to restore.
            company_id: Parent company ID for validation.

        Returns:
            Restoration status.
        """
        branch_result = await db.execute(
            select(Branch).where(
                Branch.id == branch_id,
                Branch.company_id == company_id,
            )
        )
        branch = branch_result.scalar_one_or_none()
        if not branch:
            raise ValueError(f"Branch {branch_id} not found in company {company_id}")

        branch.is_active = True
        await db.commit()

        return {
            "branch_id": branch_id,
            "is_archived": False,
            "is_deleted": False,
            "restored_at": datetime.utcnow(),
        }
