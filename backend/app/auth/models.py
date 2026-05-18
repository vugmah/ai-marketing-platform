"""
User model for authentication and authorization.

Users belong to a Company (tenant) and optionally a Branch.
Each user has a role that determines their permissions in the system.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    """User role hierarchy for access control."""

    SUPER_ADMIN = "super_admin"
    COMPANY_ADMIN = "company_admin"
    BRANCH_MANAGER = "branch_manager"
    MARKETING_MANAGER = "marketing_manager"
    SUPPORT_AGENT = "support_agent"
    ANALYST = "analyst"


class UserStatus(str, enum.Enum):
    """User account lifecycle statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class User(Base):
    """
    User entity for authentication and authorization.

    Attributes:
        id: Primary key.
        email: Unique email address (login identifier).
        password_hash: Hashed password (never store plain text).
        first_name: User's first name.
        last_name: User's last name.
        role: User's role in the system (determines permissions).
        status: Account status (active, inactive, pending).
        company_id: FK to the parent company (nullable for super admins).
        branch_id: FK to a specific branch (nullable).
        is_active: Whether the account is active.
        email_verified: Whether the email has been verified.
        last_login_at: Timestamp of the last successful login.
        created_at: Record creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "users"
    __table_args__ = {"schema": None, "comment": "User accounts for authentication"}

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Role & status
    role = Column(
        Enum(UserRole, name="userrole", create_type=True),
        default=UserRole.COMPANY_ADMIN,
        nullable=False,
    )
    status = Column(
        Enum(UserStatus, name="userstatus", create_type=True),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    # Foreign keys to tenant hierarchy
    company_id = Column(
        Integer,
        ForeignKey(
            "public.companies.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_users_company_id",
        ),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        Integer,
        ForeignKey(
            "public.branches.id",
            ondelete="SET NULL",
            onupdate="CASCADE",
            name="fk_users_branch_id",
        ),
        nullable=True,
        index=True,
    )

    # Status & timestamps
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
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
    company = relationship("Company", back_populates="users")
    branch = relationship("Branch", back_populates="users")

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email='{self.email}', "
            f"role='{self.role}', company_id={self.company_id})>"
        )
