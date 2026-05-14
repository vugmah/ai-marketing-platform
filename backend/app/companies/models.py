"""
Company (tenant) model for multi-tenant architecture.

Each Company represents a tenant in the system. Companies have subscription
plans, usage limits, and contain multiple branches.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PlanType(str, enum.Enum):
    """Subscription plan tiers."""

    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle statuses."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIAL = "trial"


class Company(Base):
    """
    Multi-tenant company (tenant) entity.

    Attributes:
        id: Primary key.
        name: Company display name.
        slug: Unique URL-friendly identifier.
        description: Optional company description.
        logo_url: URL to company logo image.
        website: Company website URL.
        email: Primary contact email.
        phone: Primary contact phone.
        plan: Subscription plan tier.
        subscription_status: Current subscription status.
        max_branches: Maximum allowed branches for this plan.
        max_users: Maximum allowed users for this plan.
        ai_requests_limit: Monthly AI request quota.
        timezone: Default timezone (e.g., "Asia/Baku").
        currency: Default currency code (e.g., "AZN").
        language: Default language code (e.g., "az").
        is_active: Whether the company account is active.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "companies"
    __table_args__ = {"schema": "public", "comment": "Multi-tenant companies table"}

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Company info
    name = Column(String(255), nullable=False)
    slug = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique URL-friendly identifier",
    )
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    website = Column(String(255), nullable=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)

    # Subscription & limits
    plan = Column(
        Enum(PlanType, name="plantype", create_type=True),
        default=PlanType.STARTER,
        nullable=False,
    )
    subscription_status = Column(
        Enum(SubscriptionStatus, name="subscriptionstatus", create_type=True),
        default=SubscriptionStatus.TRIAL,
        nullable=False,
    )
    max_branches = Column(Integer, default=2, nullable=False)
    max_users = Column(Integer, default=3, nullable=False)
    ai_requests_limit = Column(Integer, default=500, nullable=False)

    # Localization
    timezone = Column(String(50), default="Asia/Baku", nullable=False)
    currency = Column(String(3), default="AZN", nullable=False)
    language = Column(String(5), default="az", nullable=False)

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
    branches = relationship(
        "Branch",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name='{self.name}', slug='{self.slug}')>"
