"""
Initial migration: create companies, branches, and users tables.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

This migration sets up the multi-tenant core schema:
- companies: tenant table with subscription and limit tracking
- branches: per-company locations with targets and manager info
- users: authentication accounts with roles, linked to companies and branches
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create companies and branches tables with indexes and constraints."""

    # ------------------------------------------------------------------
    # 1. Create ENUM types (PostgreSQL)
    # ------------------------------------------------------------------
    plantype = sa.Enum("starter", "pro", "enterprise", "custom", name="plantype")
    plantype.create(op.get_bind(), checkfirst=True)

    subscriptionstatus = sa.Enum(
        "active", "past_due", "cancelled", "trial", name="subscriptionstatus"
    )
    subscriptionstatus.create(op.get_bind(), checkfirst=True)

    branchtype = sa.Enum(
        "restaurant", "cafe", "retail", "franchise", "other", name="branchtype"
    )
    branchtype.create(op.get_bind(), checkfirst=True)

    branchstatus = sa.Enum(
        "active", "inactive", "pending", name="branchstatus"
    )
    branchstatus.create(op.get_bind(), checkfirst=True)

    userrole = sa.Enum(
        "super_admin",
        "company_admin",
        "branch_manager",
        "marketing_manager",
        "support_agent",
        "analyst",
        name="userrole",
    )
    userrole.create(op.get_bind(), checkfirst=True)

    userstatus = sa.Enum(
        "active", "inactive", "pending", name="userstatus"
    )
    userstatus.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 2. Create "companies" table
    # ------------------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
            comment="Unique URL-friendly identifier",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column(
            "plan",
            sa.Enum("starter", "pro", "enterprise", "custom", name="plantype"),
            server_default="starter",
            nullable=False,
        ),
        sa.Column(
            "subscription_status",
            sa.Enum(
                "active", "past_due", "cancelled", "trial", name="subscriptionstatus"
            ),
            server_default="trial",
            nullable=False,
        ),
        sa.Column(
            "max_branches",
            sa.Integer(),
            server_default="2",
            nullable=False,
        ),
        sa.Column(
            "max_users",
            sa.Integer(),
            server_default="3",
            nullable=False,
        ),
        sa.Column(
            "ai_requests_limit",
            sa.Integer(),
            server_default="500",
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sa.String(length=50),
            server_default="Asia/Baku",
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="AZN",
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=5),
            server_default="az",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        # Unique constraints
        sa.UniqueConstraint("slug", name=op.f("uq_companies_slug")),
        # Table args
        schema=None,
        comment="Multi-tenant companies table",
    )

    # Indexes on companies
    op.create_index(
        op.f("ix_companies_id"), "companies", ["id"], unique=False, schema=None
    )
    op.create_index(
        op.f("ix_companies_slug"),
        "companies",
        ["slug"],
        unique=True,
        schema=None,
    )
    op.create_index(
        op.f("ix_companies_created_at"),
        "companies",
        ["created_at"],
        unique=False,
        schema=None,
    )

    # ------------------------------------------------------------------
    # 3. Create "branches" table
    # ------------------------------------------------------------------
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "type",
            sa.Enum(
                "restaurant", "cafe", "retail", "franchise", "other", name="branchtype"
            ),
            server_default="restaurant",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "inactive", "pending", name="branchstatus"
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("manager_name", sa.String(length=255), nullable=True),
        sa.Column("manager_email", sa.String(length=255), nullable=True),
        sa.Column("manager_phone", sa.String(length=50), nullable=True),
        sa.Column(
            "employee_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "monthly_revenue_target",
            sa.Float(),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column(
            "daily_order_target",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("instagram_account", sa.String(length=255), nullable=True),
        sa.Column("facebook_page_id", sa.String(length=255), nullable=True),
        sa.Column("google_place_id", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        # Foreign key to companies with CASCADE delete
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_branches_company_id"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        # Unique constraint: slug per company
        sa.UniqueConstraint(
            "company_id", "slug", name=op.f("uq_branch_company_slug")
        ),
        # Table args
        schema=None,
        comment="Branches belonging to companies",
    )

    # Indexes on branches
    op.create_index(
        op.f("ix_branches_id"), "branches", ["id"], unique=False, schema=None
    )
    op.create_index(
        op.f("ix_branches_company_id"),
        "branches",
        ["company_id"],
        unique=False,
        schema=None,
    )
    op.create_index(
        op.f("ix_branches_type"),
        "branches",
        ["type"],
        unique=False,
        schema=None,
    )
    op.create_index(
        op.f("ix_branches_status"),
        "branches",
        ["status"],
        unique=False,
        schema=None,
    )
    op.create_index(
        op.f("ix_branches_created_at"),
        "branches",
        ["created_at"],
        unique=False,
        schema=None,
    )

    # ------------------------------------------------------------------
    # 4. Create "users" table
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "super_admin",
                "company_admin",
                "branch_manager",
                "marketing_manager",
                "support_agent",
                "analyst",
                name="userrole",
            ),
            server_default="company_admin",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active", "inactive", "pending", name="userstatus"
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        # Unique constraint on email
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_users_company_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_users_branch_id"),
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        # Table args
        schema=None,
        comment="User accounts for authentication",
    )

    # Indexes on users
    op.create_index(
        op.f("ix_users_id"), "users", ["id"], unique=False, schema=None
    )
    op.create_index(
        op.f("ix_users_email"),
        "users",
        ["email"],
        unique=True,
        schema=None,
    )
    op.create_index(
        op.f("ix_users_company_id"),
        "users",
        ["company_id"],
        unique=False,
        schema=None,
    )
    op.create_index(
        op.f("ix_users_branch_id"),
        "users",
        ["branch_id"],
        unique=False,
        schema=None,
    )
    op.create_index(
        op.f("ix_users_created_at"),
        "users",
        ["created_at"],
        unique=False,
        schema=None,
    )


def downgrade() -> None:
    """Drop users, branches, and companies tables with their ENUM types."""

    # 1. Drop users table and its indexes
    op.drop_index(
        op.f("ix_users_created_at"), table_name="users", schema=None
    )
    op.drop_index(
        op.f("ix_users_branch_id"), table_name="users", schema=None
    )
    op.drop_index(
        op.f("ix_users_company_id"), table_name="users", schema=None
    )
    op.drop_index(
        op.f("ix_users_email"), table_name="users", schema=None
    )
    op.drop_index(
        op.f("ix_users_id"), table_name="users", schema=None
    )
    op.drop_table("users", schema=None)

    # 2. Drop branches table and its indexes
    op.drop_index(
        op.f("ix_branches_created_at"), table_name="branches", schema=None
    )
    op.drop_index(
        op.f("ix_branches_status"), table_name="branches", schema=None
    )
    op.drop_index(
        op.f("ix_branches_type"), table_name="branches", schema=None
    )
    op.drop_index(
        op.f("ix_branches_company_id"), table_name="branches", schema=None
    )
    op.drop_index(
        op.f("ix_branches_id"), table_name="branches", schema=None
    )
    op.drop_table("branches", schema=None)

    # 3. Drop companies table and its indexes
    op.drop_index(
        op.f("ix_companies_created_at"), table_name="companies", schema=None
    )
    op.drop_index(
        op.f("ix_companies_slug"), table_name="companies", schema=None
    )
    op.drop_index(
        op.f("ix_companies_id"), table_name="companies", schema=None
    )
    op.drop_table("companies", schema=None)

    # 4. Drop ENUM types
    sa.Enum(name="userstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="branchstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="branchtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscriptionstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plantype").drop(op.get_bind(), checkfirst=True)
