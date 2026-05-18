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
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_governance_soft_delete"
down_revision: Union[str, None] = "004"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str, schema=None) -> bool:
    """Return True if *column_name* already exists on *table_name*."""
    bind = op.get_bind()
    try:
        existing = [c["name"] for c in inspect(bind).get_columns(table_name, schema=schema)]
    except Exception:
        return False
    return column_name in existing


def _add_column_if_not_exists(table_name, column, schema=None):
    """Add a column only when it does not already exist."""
    if _column_exists(table_name, column.name, schema=schema):
        return
    _add_column_if_not_exists(table_name, column, schema=schema)


def _drop_column_if_exists(table_name, column_name, schema=None):
    """Drop a column only when it exists."""
    if not _column_exists(table_name, column_name, schema=schema):
        return
    _drop_column_if_exists(table_name, column_name, schema=schema)


def upgrade() -> None:
    """Apply governance and soft-delete migration."""
    # -------------------------------------------------------------------------
    # 1. Add soft-delete columns to companies
    # -------------------------------------------------------------------------
    _add_column_if_not_exists(
        "companies",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema=None,
    )
    _add_column_if_not_exists(
        "companies",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_companies_deleted_by"),
            nullable=True,
        ),
        schema=None,
    )
    _add_column_if_not_exists(
        "companies",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        schema=None,
    )
    op.create_index(
        "ix_companies_deleted_at", "companies", ["deleted_at"], schema=None
    )
    op.create_index(
        "ix_companies_is_deleted", "companies", ["is_deleted"], schema=None
    )

    # -------------------------------------------------------------------------
    # 2. Add soft-delete columns to branches
    # -------------------------------------------------------------------------
    _add_column_if_not_exists(
        "branches",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema=None,
    )
    _add_column_if_not_exists(
        "branches",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_branches_deleted_by"),
            nullable=True,
        ),
        schema=None,
    )
    _add_column_if_not_exists(
        "branches",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        schema=None,
    )
    _add_column_if_not_exists(
        "branches",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        schema=None,
    )
    _add_column_if_not_exists(
        "branches",
        sa.Column(
            "archived_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_branches_archived_by"),
            nullable=True,
        ),
        schema=None,
    )
    _add_column_if_not_exists(
        "branches",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        schema=None,
    )
    op.create_index(
        "ix_branches_deleted_at", "branches", ["deleted_at"], schema=None
    )
    op.create_index(
        "ix_branches_is_deleted", "branches", ["is_deleted"], schema=None
    )
    op.create_index(
        "ix_branches_is_archived", "branches", ["is_archived"], schema=None
    )

    # -------------------------------------------------------------------------
    # 3. Add soft-delete columns to users
    # -------------------------------------------------------------------------
    _add_column_if_not_exists(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        schema=None,
    )
    _add_column_if_not_exists(
        "users",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_users_deleted_by"),
            nullable=True,
        ),
        schema=None,
    )
    _add_column_if_not_exists(
        "users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="0"),
        schema=None,
    )
    op.create_index(
        "ix_users_deleted_at", "users", ["deleted_at"], schema=None
    )
    op.create_index(
        "ix_users_is_deleted", "users", ["is_deleted"], schema=None
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
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
        sa.Column("data_scope", sa.JSON(), nullable=False,),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=None,
        comment="GDPR/KVKK data export request tracking",
    )
    op.create_index(
        "ix_gdpr_export_requests_company_id",
        "gdpr_export_requests",
        ["company_id"],
        schema=None,
    )
    op.create_index(
        "ix_gdpr_export_requests_user_id",
        "gdpr_export_requests",
        ["user_id"],
        schema=None,
    )
    op.create_index(
        "ix_gdpr_export_requests_status",
        "gdpr_export_requests",
        ["status"],
        schema=None,
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
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "requested_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
        schema=None,
        comment="GDPR/KVKK data deletion request tracking",
    )
    op.create_index(
        "ix_gdpr_deletion_requests_company_id",
        "gdpr_deletion_requests",
        ["company_id"],
        schema=None,
    )
    op.create_index(
        "ix_gdpr_deletion_requests_user_id",
        "gdpr_deletion_requests",
        ["user_id"],
        schema=None,
    )
    op.create_index(
        "ix_gdpr_deletion_requests_status",
        "gdpr_deletion_requests",
        ["status"],
        schema=None,
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
        schema=None,
        comment="Retention policy execution audit log",
    )
    op.create_index(
        "ix_retention_policy_runs_policy_name",
        "retention_policy_runs",
        ["policy_name"],
        schema=None,
    )
    op.create_index(
        "ix_retention_policy_runs_created_at",
        "retention_policy_runs",
        ["created_at"],
        schema=None,
    )


def downgrade() -> None:
    """Revert governance and soft-delete migration."""
    # Drop retention policy runs
    op.drop_table("retention_policy_runs", schema=None)

    # Drop GDPR deletion requests
    op.drop_table("gdpr_deletion_requests", schema=None)
    op.execute("DROP TYPE IF EXISTS gdprrequesttype_deletion CASCADE")
    op.execute("DROP TYPE IF EXISTS gdprrequeststatus_deletion CASCADE")

    # Drop GDPR export requests
    op.drop_table("gdpr_export_requests", schema=None)
    op.execute("DROP TYPE IF EXISTS gdprrequesttype CASCADE")
    op.execute("DROP TYPE IF EXISTS gdprrequeststatus CASCADE")

    # Drop retention run status enum
    op.execute("DROP TYPE IF EXISTS retentionrunstatus CASCADE")

    # Remove soft-delete columns from users
    op.drop_index("ix_users_is_deleted", table_name="users", schema=None)
    op.drop_index("ix_users_deleted_at", table_name="users", schema=None)
    _drop_column_if_exists("users", "is_deleted", schema=None)
    _drop_column_if_exists("users", "deleted_by", schema=None)
    _drop_column_if_exists("users", "deleted_at", schema=None)

    # Remove soft-delete/archive columns from branches
    op.drop_index("ix_branches_is_archived", table_name="branches", schema=None)
    op.drop_index("ix_branches_is_deleted", table_name="branches", schema=None)
    op.drop_index("ix_branches_deleted_at", table_name="branches", schema=None)
    _drop_column_if_exists("branches", "is_archived", schema=None)
    _drop_column_if_exists("branches", "archived_by", schema=None)
    _drop_column_if_exists("branches", "archived_at", schema=None)
    _drop_column_if_exists("branches", "is_deleted", schema=None)
    _drop_column_if_exists("branches", "deleted_by", schema=None)
    _drop_column_if_exists("branches", "deleted_at", schema=None)

    # Remove soft-delete columns from companies
    op.drop_index("ix_companies_is_deleted", table_name="companies", schema=None)
    op.drop_index("ix_companies_deleted_at", table_name="companies", schema=None)
    _drop_column_if_exists("companies", "is_deleted", schema=None)
    _drop_column_if_exists("companies", "deleted_by", schema=None)
    _drop_column_if_exists("companies", "deleted_at", schema=None)
