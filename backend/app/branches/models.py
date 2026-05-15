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
        {"schema": "public", "comment": "Branches belonging to companies"},
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

    def __repr__(self) -> str:
        return (
            f"<Branch(id={self.id}, name='{self.name}', "
            f"company_id={self.company_id})>"
        )
