"""MySQL 8.0 hardening - charset, collation, FK optimization

Revision ID: 009
Revises: 008
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply MySQL 8.0 hardening: optimize indexes, verify charset."""
    # 1. Composite index for common tenant lookups
    op.create_index("ix_tenant_lookup", "users", ["company_id", "branch_id", "role"])

    # 2. Time-series index for analytics queries
    op.create_index("ix_analytics_time", "analytics_snapshots", ["company_id", "date"])

    # 3. Performance index for company queries
    op.create_index("ix_companies_db_created", "companies", ["db_created_at"])

    # 4. Ensure utf8mb4 charset on core tables
    op.execute("ALTER TABLE companies CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE branches CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")


def downgrade() -> None:
    """Reverse MySQL 8.0 hardening."""
    op.drop_index("ix_companies_db_created", table_name="companies")
    op.drop_index("ix_tenant_lookup", table_name="users")
    op.drop_index("ix_analytics_time", table_name="analytics_snapshots")
