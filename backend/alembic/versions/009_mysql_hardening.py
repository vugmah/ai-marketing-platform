"""MySQL 8.0 hardening - charset, collation, FK optimization

Revision ID: 009
Revises: 008
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_exists(table_name: str, index_name: str, schema=None) -> bool:
    """Return True if *index_name* already exists on *table_name*."""
    bind = op.get_bind()
    try:
        indexes = inspect(bind).get_indexes(table_name, schema=schema)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _column_exists(table_name: str, column_name: str, schema=None) -> bool:
    """Return True if *column_name* already exists on *table_name*."""
    bind = op.get_bind()
    try:
        columns = [c["name"] for c in inspect(bind).get_columns(table_name, schema=schema)]
    except Exception:
        return False
    return column_name in columns


def _create_index_if_not_exists(index_name, table_name, columns, unique=False, schema=None):
    """Create an index only when it does not already exist and all columns exist."""
    if _index_exists(table_name, index_name, schema=schema):
        return
    bind = op.get_bind()
    try:
        existing_cols = [c["name"] for c in inspect(bind).get_columns(table_name, schema=schema)]
    except Exception:
        return
    if not all(col in existing_cols for col in columns):
        return
    op.create_index(index_name, table_name, columns, unique=unique, schema=schema)


def _drop_index_if_exists(index_name, table_name, schema=None):
    """Drop an index only when it exists."""
    if not _index_exists(table_name, index_name, schema=schema):
        return
    op.drop_index(index_name, table_name=table_name, schema=schema)


def upgrade() -> None:
    """Apply MySQL 8.0 hardening: optimize indexes, verify charset."""
    # 1. Composite index for common tenant lookups
    _create_index_if_not_exists("ix_tenant_lookup", "users", ["company_id", "branch_id", "role"])

    # 2. Time-series index for analytics queries (snapshot_date, not "date")
    _create_index_if_not_exists("ix_analytics_time", "analytics_snapshots", ["company_id", "snapshot_date"])

    # 3. Performance index for company queries (only if db_created_at exists)
    if _column_exists("companies", "db_created_at"):
        _create_index_if_not_exists("ix_companies_db_created", "companies", ["db_created_at"])

    # 4. Ensure utf8mb4 charset on core tables
    op.execute("ALTER TABLE companies CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE branches CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")


def downgrade() -> None:
    """Reverse MySQL 8.0 hardening."""
    _drop_index_if_exists("ix_companies_db_created", "companies")
    _drop_index_if_exists("ix_tenant_lookup", "users")
    _drop_index_if_exists("ix_analytics_time", "analytics_snapshots")
