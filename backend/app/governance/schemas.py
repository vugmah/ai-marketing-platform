"""Pydantic schemas for Data Governance & GDPR/KVKK endpoints."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# GDPR Export Schemas
# =============================================================================


class GDPRExportRequest(BaseModel):
    """Request body for GDPR data export."""

    user_id: int = Field(..., description="User ID whose data will be exported")
    data_scope: List[str] = Field(
        default=["all"],
        description="Data scopes to include: all, user, company, branch, ai, ads, audit, events",
    )


class GDPRExportResponse(BaseModel):
    """Response for GDPR data export."""

    model_config = ConfigDict(from_attributes=True)

    export_id: int
    status: str
    user_id: int
    data_scope: List[str]
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    record_count: Optional[int] = None
    expires_at: datetime
    created_at: datetime
    completed_at: Optional[datetime] = None


class GDPRUserDataExport(BaseModel):
    """Complete user data export for GDPR/KVKK (Article 20).

    This is the comprehensive JSON structure returned by the export endpoint
    containing all user-related data across all modules.
    """

    model_config = ConfigDict(from_attributes=True)

    # Metadata
    export_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Export request metadata (timestamp, requester, version)",
    )

    # User profile
    user: Optional[Dict[str, Any]] = Field(
        default=None, description="User account data"
    )

    # Company data
    company: Optional[Dict[str, Any]] = Field(
        default=None, description="Company/tenant data"
    )

    # Branch data
    branches: List[Dict[str, Any]] = Field(
        default_factory=list, description="Branch memberships and data"
    )

    # AI module data
    ai_conversations: List[Dict[str, Any]] = Field(
        default_factory=list, description="AI chat conversations"
    )
    ai_messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="AI conversation messages"
    )
    ai_suggestions: List[Dict[str, Any]] = Field(
        default_factory=list, description="AI marketing suggestions"
    )
    ai_recommendations: List[Dict[str, Any]] = Field(
        default_factory=list, description="AI marketing recommendations"
    )
    ai_usage_logs: List[Dict[str, Any]] = Field(
        default_factory=list, description="AI API usage logs"
    )

    # Ads module data
    ad_campaigns: List[Dict[str, Any]] = Field(
        default_factory=list, description="Advertising campaigns"
    )
    ad_creatives: List[Dict[str, Any]] = Field(
        default_factory=list, description="Ad creative assets"
    )

    # Audit data
    audit_logs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Security audit logs"
    )
    login_attempts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Login attempt records"
    )
    data_access_logs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Data access compliance logs"
    )

    # Events data
    event_logs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Published event logs"
    )

    # Social media data
    social_posts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Social media posts"
    )

    # Media data
    media_files: List[Dict[str, Any]] = Field(
        default_factory=list, description="Uploaded media files"
    )


# =============================================================================
# GDPR Delete Schemas
# =============================================================================


class GDPRDeleteRequest(BaseModel):
    """Request body for GDPR data deletion (Right to be Forgotten)."""

    user_id: int = Field(..., description="User ID whose data will be permanently deleted")
    verification_token: Optional[str] = Field(
        default=None,
        description="Verification token for double-opt-in deletion",
    )
    scopes: List[str] = Field(
        default=["all"],
        description="Data scopes to delete: all, user, ai, ads, audit, events, social, media",
    )


class GDPRDeleteResponse(BaseModel):
    """Response for GDPR data deletion."""

    model_config = ConfigDict(from_attributes=True)

    deletion_id: int
    status: str
    user_id: int
    affected_tables: Dict[str, int] = Field(
        default_factory=dict, description="Table names and count of deleted records"
    )
    total_records_deleted: int
    completed_at: Optional[datetime] = None


# =============================================================================
# Archive Schemas
# =============================================================================


class CompanyArchiveRequest(BaseModel):
    """Request body for company archiving."""

    reason: Optional[str] = Field(
        default=None, description="Reason for archiving the company"
    )


class CompanyArchiveResponse(BaseModel):
    """Response for company archive operation."""

    company_id: int
    is_archived: bool
    archived_at: Optional[datetime] = None
    archived_by: Optional[int] = None
    affected_branches: int = Field(
        default=0, description="Number of branches archived"
    )
    affected_users: int = Field(
        default=0, description="Number of users deactivated"
    )
    message: str


class BranchArchiveRequest(BaseModel):
    """Request body for branch archiving."""

    reason: Optional[str] = Field(
        default=None, description="Reason for archiving the branch"
    )


class BranchArchiveResponse(BaseModel):
    """Response for branch archive operation."""

    branch_id: int
    company_id: int
    is_archived: bool
    archived_at: Optional[datetime] = None
    archived_by: Optional[int] = None
    affected_users: int = Field(
        default=0, description="Number of users deactivated"
    )
    message: str


class UnarchiveResponse(BaseModel):
    """Response for unarchive operation."""

    id: int
    is_archived: bool
    is_deleted: bool
    restored_at: datetime
    message: str


# =============================================================================
# Retention Policy Schemas
# =============================================================================


class RetentionPolicyConfig(BaseModel):
    """Configuration for a single retention policy."""

    policy_name: str
    table_name: str
    retention_days: int
    date_column: str = "created_at"
    description: str


class RetentionPolicyStatus(BaseModel):
    """Status of a retention policy run."""

    policy_name: str
    table_name: str
    retention_days: int
    last_run: Optional[datetime] = None
    records_affected: int = 0
    status: str = "idle"


class RetentionPolicyExecuteResponse(BaseModel):
    """Response for retention policy execution."""

    executed_at: datetime
    policies: List[Dict[str, Any]] = Field(default_factory=list)
    total_records_deleted: int = 0
    errors: List[str] = Field(default_factory=list)


# =============================================================================
# Soft Delete Filter Schema (for list endpoints)
# =============================================================================


class ListFilterParams(BaseModel):
    """Query parameters for list endpoints with soft-delete awareness."""

    include_deleted: bool = Field(
        default=False,
        description="Include soft-deleted records in results",
    )
    include_archived: bool = Field(
        default=False,
        description="Include archived records in results",
    )
