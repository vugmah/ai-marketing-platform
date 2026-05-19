"""Convert users.role from MySQL ENUM to VARCHAR(50).

Revision ID: 012
Revises: 011_add_missing_foreign_keys
Create Date: 2026-05-19 16:30:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "012_convert_user_role_enum_to_string"
down_revision = "011_add_missing_foreign_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert ENUM to VARCHAR(50) with lowercase default
    op.execute(
        "ALTER TABLE users MODIFY COLUMN role VARCHAR(50) NOT NULL DEFAULT 'company_admin'"
    )
    # Normalize any existing uppercase values to lowercase
    op.execute("UPDATE users SET role = LOWER(role) WHERE role IS NOT NULL")


def downgrade() -> None:
    # Revert to ENUM (best-effort; may fail if new values exist)
    op.execute(
        "ALTER TABLE users MODIFY COLUMN role ENUM("
        "'super_admin','company_admin','branch_manager',"
        "'marketing_manager','support_agent','analyst'"
        ") NOT NULL DEFAULT 'company_admin'"
    )
