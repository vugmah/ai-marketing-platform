"""Granular Permission System models."""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class PermissionDefinition(Base):
    """Granular permission definitions."""
    __tablename__ = "permission_definitions"
    __table_args__ = (
        Index("ix_pd_scope", "scope"),
        {"schema": None, "comment": "Granular permission definitions"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(50), nullable=False)  # feature, branch, channel, approval, export, ai, erp, support
    resource = Column(String(100), nullable=False)  # ads, analytics, campaigns, inventory, etc.
    action = Column(String(50), nullable=False)  # read, create, update, delete, approve, export, execute
    description = Column(String(500), nullable=True)
    requires_approval = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class RolePermission(Base):
    """Role-to-permission mapping."""
    __tablename__ = "role_permissions"
    __table_args__ = (
        Index("ix_rp_role_perm", "role_id", "permission_id"),
        Index("ix_rp_company", "company_id"),
        {"schema": None, "comment": "Role permission assignments"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, nullable=False, index=True)
    role_id = Column(Integer, nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("public.permission_definitions.id"), nullable=False)
    granted = Column(Boolean, nullable=False, default=True)
    branch_scope = Column(String(20), nullable=False, default="all")  # all, assigned, none
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class UserPermissionOverride(Base):
    """User-specific permission overrides."""
    __tablename__ = "user_permission_overrides"
    __table_args__ = (
        Index("ix_upo_user_perm", "user_id", "permission_id"),
        {"schema": None, "comment": "User permission overrides"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    permission_id = Column(Integer, ForeignKey("public.permission_definitions.id"), nullable=False)
    granted = Column(Boolean, nullable=False)  # True=grant, False=deny
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
