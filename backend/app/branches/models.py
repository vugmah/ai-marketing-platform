"""
Branch model for multi-tenant architecture.

Each Branch belongs to a Company (tenant). Branches represent physical or
logical locations such as restaurants, cafes, retail stores, or franchises.
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class BranchType(str, enum.Enum):
    """Types of business branches."""

    RESTAURANT = "restaurant"
    CAFE = "cafe"
    RETAIL = "retail"
    FRANCHISE = "franchise"
    OTHER = "other"


class BranchStatus(str, enum.Enum):
    """Branch operational statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class Branch(Base):
    """
    Branch entity belonging to a Company (tenant).

    Attributes:
        id: Primary key.
        company_id: FK to the parent company.
        name: Branch display name.
        slug: URL-friendly identifier (unique per company).
        city: City where the branch is located.
        address: Full address.
        type: Branch business type.
        status: Operational status.
        manager_name: Branch manager name.
        manager_email: Manager contact email.
        manager_phone: Manager contact phone.
        employee_count: Number of employees at this branch.
        monthly_revenue_target: Revenue target in company currency.
        daily_order_target: Daily order count target.
        instagram_account: Instagram handle.
        facebook_page_id: Facebook page identifier.
        google_place_id: Google Places identifier.
        is_active: Whether the branch is active.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "slug", name="uq_branch_company_slug"
        ),
        {"schema": None, "comment": "Branches belonging to companies"},
    )

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to company (tenant)
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_branches_company_id",
        ),
        nullable=False,
        index=True,
    )

    # Branch info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    address = Column(Text, nullable=True)

    # Type & status
    type = Column(
        Enum(BranchType, name="branchtype", create_type=True),
        default=BranchType.RESTAURANT,
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(BranchStatus, name="branchstatus", create_type=True),
        default=BranchStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Manager info
    manager_name = Column(String(255), nullable=True)
    manager_email = Column(String(255), nullable=True)
    manager_phone = Column(String(50), nullable=True)

    # Workforce
    employee_count = Column(Integer, default=0, nullable=False)

    # Targets
    monthly_revenue_target = Column(Float, default=0.0, nullable=False)
    daily_order_target = Column(Integer, default=0, nullable=False)

    # Social & external integrations
    instagram_account = Column(String(255), nullable=True)
    facebook_page_id = Column(String(255), nullable=True)
    google_place_id = Column(String(255), nullable=True)

    # Status & timestamps
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
    company = relationship("Company", back_populates="branches")
    users = relationship(
        "User",
        back_populates="branch",
        lazy="selectin",
    )
    configs = relationship(
        "BranchConfig",
        back_populates="branch",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Branch(id={self.id}, name='{self.name}', "
            f"company_id={self.company_id})>"
        )


class BranchConfig(Base):
    """
    Per-branch configuration / metadata key-value store.

    Used to store AI settings, social account tokens, ERP
    integration parameters, or any other branch-scoped config.

    Attributes:
        id: Primary key.
        branch_id: FK to the parent branch.
        config_key: Configuration key name.
        config_value: Configuration value (JSON string or plain text).
        created_at: Record creation timestamp.
    """

    __tablename__ = "branch_configs"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "config_key", name="uq_branch_config_key"
        ),
        {"schema": None, "comment": "Branch-level configuration store"},
    )

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to branch
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_branch_configs_branch_id",
        ),
        nullable=False,
        index=True,
    )

    # Config data
    config_key = Column(String(255), nullable=False)
    config_value = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    branch = relationship("Branch", back_populates="configs")

    def __repr__(self) -> str:
        return (
            f"<BranchConfig(id={self.id}, branch_id={self.branch_id}, "
            f"key='{self.config_key}')>"
        )


# =============================================================================
# AI Prompt Overrides (branch-scoped AI prompt customization)
# =============================================================================


class AIPromptOverride(Base):
    """
    Per-branch AI prompt override / customization store.

    Allows branches to customize AI-generated content prompts
    (e.g., tone of voice, brand guidelines, special instructions).

    Attributes:
        id: Primary key.
        branch_id: FK to the parent branch.
        prompt_key: Identifier for the prompt type (e.g., 'instagram_caption').
        prompt_template: Custom prompt template / override text.
        is_active: Whether this override is active.
        priority: Priority order (higher = more important).
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "ai_prompt_overrides"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "prompt_key", name="uq_ai_prompt_branch_key"
        ),
        {"schema": None, "comment": "Branch-level AI prompt overrides"},
    )

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to branch
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_ai_prompt_overrides_branch_id",
        ),
        nullable=False,
        index=True,
    )

    # Prompt data
    prompt_key = Column(String(255), nullable=False, index=True)
    prompt_template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)

    # Timestamps
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
    branch = relationship("Branch", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<AIPromptOverride(id={self.id}, branch_id={self.branch_id}, "
            f"key='{self.prompt_key}', active={self.is_active})>"
        )


# =============================================================================
# Social Account Configs (branch-scoped social media integrations)
# =============================================================================


class SocialPlatform(str, enum.Enum):
    """Supported social media platforms."""

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    GOOGLE_BUSINESS = "google_business"
    YOUTUBE = "youtube"
    PINTEREST = "pinterest"


class SocialAccountConfig(Base):
    """
    Per-branch social media account configuration.

    Stores OAuth tokens, API keys, and connection settings for
    each social platform linked to a branch.

    Attributes:
        id: Primary key.
        branch_id: FK to the parent branch.
        platform: Social media platform name.
        account_handle: Username / handle on the platform.
        access_token: OAuth access token (encrypted at rest).
        refresh_token: OAuth refresh token (encrypted at rest).
        token_expires_at: When the access token expires.
        page_id: Platform-specific page/account ID.
        is_connected: Whether the account is currently connected.
        auto_publish: Whether to auto-publish content.
        settings_json: Additional platform-specific JSON settings.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "social_account_configs"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "platform", name="uq_social_account_branch_platform"
        ),
        {"schema": None, "comment": "Branch-level social media account configs"},
    )

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to branch
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_social_account_configs_branch_id",
        ),
        nullable=False,
        index=True,
    )

    # Platform connection
    platform = Column(
        Enum(SocialPlatform, name="socialplatform", create_type=True),
        nullable=False,
        index=True,
    )
    account_handle = Column(String(255), nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    page_id = Column(String(255), nullable=True)

    # Status & automation
    is_connected = Column(Boolean, default=False, nullable=False)
    auto_publish = Column(Boolean, default=False, nullable=False)

    # Extra settings
    settings_json = Column(Text, nullable=True)

    # Timestamps
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
    branch = relationship("Branch", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<SocialAccountConfig(id={self.id}, branch_id={self.branch_id}, "
            f"platform='{self.platform}', connected={self.is_connected})>"
        )


# =============================================================================
# ERP Connection Configs (branch-scoped ERP integrations)
# =============================================================================


class ERPProvider(str, enum.Enum):
    """Supported ERP / POS system providers."""

    IKO = "iko"
    R_KEEPER = "r_keeper"
    MICROS = "micros"
    SQUARE = "square"
    TOAST = "toast"
    LIGHTSPEED = "lightspeed"
    CLOVER = "clover"
    CUSTOM = "custom"


class ERPConnectionConfig(Base):
    """
    Per-branch ERP / POS system connection configuration.

    Stores API credentials and connection parameters for integrating
    with external ERP or POS systems (e.g., IKO, R-Keeper).

    Attributes:
        id: Primary key.
        branch_id: FK to the parent branch.
        provider: ERP/POS provider name.
        api_base_url: Base URL for the ERP API.
        api_key: API key / client ID (encrypted at rest).
        api_secret: API secret / client secret (encrypted at rest).
        webhook_secret: Webhook verification secret.
        location_id: Branch location identifier in the ERP.
        terminal_id: Terminal/device identifier.
        is_active: Whether the connection is active.
        sync_enabled: Whether automatic sync is enabled.
        sync_interval_minutes: Sync interval in minutes.
        last_sync_at: Timestamp of last successful sync.
        last_sync_status: Status of last sync attempt.
        settings_json: Additional provider-specific JSON settings.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "erp_connection_configs"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "provider", name="uq_erp_config_branch_provider"
        ),
        {"schema": None, "comment": "Branch-level ERP/POS connection configs"},
    )

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign key to branch
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="CASCADE",
            onupdate="CASCADE",
            name="fk_erp_connection_configs_branch_id",
        ),
        nullable=False,
        index=True,
    )

    # Provider connection
    provider = Column(
        Enum(ERPProvider, name="erpprovider", create_type=True),
        nullable=False,
        index=True,
    )
    api_base_url = Column(String(500), nullable=True)
    api_key = Column(Text, nullable=True)
    api_secret = Column(Text, nullable=True)
    webhook_secret = Column(Text, nullable=True)

    # Location identifiers
    location_id = Column(String(255), nullable=True)
    terminal_id = Column(String(255), nullable=True)

    # Status & sync
    is_active = Column(Boolean, default=True, nullable=False)
    sync_enabled = Column(Boolean, default=False, nullable=False)
    sync_interval_minutes = Column(Integer, default=60, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(50), nullable=True)

    # Extra settings
    settings_json = Column(Text, nullable=True)

    # Timestamps
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
    branch = relationship("Branch", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ERPConnectionConfig(id={self.id}, branch_id={self.branch_id}, "
            f"provider='{self.provider}', active={self.is_active})>"
        )
