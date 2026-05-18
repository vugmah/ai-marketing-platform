"""005_governance_soft_delete

Data Governance & GDPR/KVKK Compliance Migration.

- Adds SoftDeleteMixin and ArchiveMixin columns to key tables
- Creates governance tracking tables (gdpr_export_requests, gdpr_deletion_requests, retention_policy_runs)
- Adds indexes for soft-delete query performance

Revision ID: 005_governance_soft_delete
Revises: 004_add_indexes
Create Date: 2025-01-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_governance_soft_delete"
down_revision: Union[str, None] = "004"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    """Apply governance and soft-delete migration."""
    # -------------------------------------------------------------------------
    # 1. Add soft-delete columns to companies
    # -------------------------------------------------------------------------
    op.add_column(
        "companies",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema="public",
    )
    op.add_column(
        "companies",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL", name="fk_companies_deleted_by"),
            nullable=True,
        ),
        schema="public",
    )
    op.add_column(
        "companies",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        schema="public",
    )
    op.create_index(
        "ix_companies_deleted_at", "companies", ["deleted_at"], schema="public"
    )
    op.create_index(
        "ix_companies_is_deleted", "companies", ["is_deleted"], schema="public"
    )

    # -------------------------------------------------------------------------
    # 2. Add soft-delete columns to branches
    # -------------------------------------------------------------------------
    op.add_column(
        "branches",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema="public",
    )
    op.add_column(
        "branches",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL", name="fk_branches_deleted_by"),
            nullable=True,
        ),
        schema="public",
    )
    op.add_column(
        "branches",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        schema="public",
    )
    op.add_column(
        "branches",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        schema="public",
    )
    op.add_column(
        "branches",
        sa.Column(
            "archived_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL", name="fk_branches_archived_by"),
            nullable=True,
        ),
        schema="public",
    )
    op.add_column(
        "branches",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        schema="public",
    )
    op.create_index(
        "ix_branches_deleted_at", "branches", ["deleted_at"], schema="public"
    )
    op.create_index(
        "ix_branches_is_deleted", "branches", ["is_deleted"], schema="public"
    )
    op.create_index(
        "ix_branches_is_archived", "branches", ["is_archived"], schema="public"
    )

    # -------------------------------------------------------------------------
    # 3. Add soft-delete columns to users
    # -------------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL", name="fk_users_deleted_by"),
            nullable=True,
        ),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        schema="public",
    )
    op.create_index(
        "ix_users_deleted_at", "users", ["deleted_at"], schema="public"
    )
    op.create_index(
        "ix_users_is_deleted", "users", ["is_deleted"], schema="public"
    )

    # -------------------------------------------------------------------------
    # 4. Create GDPR export requests table
    # -------------------------------------------------------------------------
    op.create_table(
        "gdpr_export_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("public.companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "request_type",
            sa.Enum("EXPORT", "DELETION", "RECTIFICATION", "RESTRICTION", name="gdprrequesttype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", "EXPIRED", name="gdprrequeststatus"),
            nullable=False,
            index=True,
        ),
        sa.Column("data_scope", sa.JSON(), nullable=False, server_default='["all"]'),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
        comment="GDPR/KVKK data export request tracking",
    )
    op.create_index(
        "ix_gdpr_export_requests_company_id",
        "gdpr_export_requests",
        ["company_id"],
        schema="public",
    )
    op.create_index(
        "ix_gdpr_export_requests_user_id",
        "gdpr_export_requests",
        ["user_id"],
        schema="public",
    )
    op.create_index(
        "ix_gdpr_export_requests_status",
        "gdpr_export_requests",
        ["status"],
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 5. Create GDPR deletion requests table
    # -------------------------------------------------------------------------
    op.create_table(
        "gdpr_deletion_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("public.companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            sa.Integer(),
            sa.ForeignKey("public.users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "request_type",
            sa.Enum("EXPORT", "DELETION", "RECTIFICATION", "RESTRICTION", name="gdprrequesttype_deletion"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", "EXPIRED", name="gdprrequeststatus_deletion"),
            nullable=False,
            index=True,
        ),
        sa.Column("verification_token", sa.String(255), nullable=True, index=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("affected_tables", sa.JSON(), nullable=True),
        sa.Column("records_deleted", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
        comment="GDPR/KVKK data deletion request tracking",
    )
    op.create_index(
        "ix_gdpr_deletion_requests_company_id",
        "gdpr_deletion_requests",
        ["company_id"],
        schema="public",
    )
    op.create_index(
        "ix_gdpr_deletion_requests_user_id",
        "gdpr_deletion_requests",
        ["user_id"],
        schema="public",
    )
    op.create_index(
        "ix_gdpr_deletion_requests_status",
        "gdpr_deletion_requests",
        ["status"],
        schema="public",
    )

    # -------------------------------------------------------------------------
    # 6. Create retention policy runs table
    # -------------------------------------------------------------------------
    op.create_table(
        "retention_policy_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_name", sa.String(128), nullable=False, index=True),
        sa.Column("table_name", sa.String(128), nullable=False, index=True),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("records_affected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("success", "failed", "partial", name="retentionrunstatus"),
            nullable=False,
            index=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cutoff_date", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
        comment="Retention policy execution audit log",
    )
    op.create_index(
        "ix_retention_policy_runs_policy_name",
        "retention_policy_runs",
        ["policy_name"],
        schema="public",
    )
    op.create_index(
        "ix_retention_policy_runs_created_at",
        "retention_policy_runs",
        ["created_at"],
        schema="public",
    )


def downgrade() -> None:
    """Revert governance and soft-delete migration."""
    # Drop retention policy runs
    op.drop_table("retention_policy_runs", schema="public")

    # Drop GDPR deletion requests
    op.drop_table("gdpr_deletion_requests", schema="public")
    op.execute("DROP TYPE IF EXISTS gdprrequesttype_deletion CASCADE")
    op.execute("DROP TYPE IF EXISTS gdprrequeststatus_deletion CASCADE")

    # Drop GDPR export requests
    op.drop_table("gdpr_export_requests", schema="public")
    op.execute("DROP TYPE IF EXISTS gdprrequesttype CASCADE")
    op.execute("DROP TYPE IF EXISTS gdprrequeststatus CASCADE")

    # Drop retention run status enum
    op.execute("DROP TYPE IF EXISTS retentionrunstatus CASCADE")

    # Remove soft-delete columns from users
    op.drop_index("ix_users_is_deleted", table_name="users", schema="public")
    op.drop_index("ix_users_deleted_at", table_name="users", schema="public")
    op.drop_column("users", "is_deleted", schema="public")
    op.drop_column("users", "deleted_by", schema="public")
    op.drop_column("users", "deleted_at", schema="public")

    # Remove soft-delete/archive columns from branches
    op.drop_index("ix_branches_is_archived", table_name="branches", schema="public")
    op.drop_index("ix_branches_is_deleted", table_name="branches", schema="public")
    op.drop_index("ix_branches_deleted_at", table_name="branches", schema="public")
    op.drop_column("branches", "is_archived", schema="public")
    op.drop_column("branches", "archived_by", schema="public")
    op.drop_column("branches", "archived_at", schema="public")
    op.drop_column("branches", "is_deleted", schema="public")
    op.drop_column("branches", "deleted_by", schema="public")
    op.drop_column("branches", "deleted_at", schema="public")

    # Remove soft-delete columns from companies
    op.drop_index("ix_companies_is_deleted", table_name="companies", schema="public")
    op.drop_index("ix_companies_deleted_at", table_name="companies", schema="public")
    op.drop_column("companies", "is_deleted", schema="public")
    op.drop_column("companies", "deleted_by", schema="public")
    op.drop_column("companies", "deleted_at", schema="public")
