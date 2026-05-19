"""Convert users.status from MySQL ENUM to VARCHAR(50).

Revision ID: 013
Revises: 012_role_to_string
Create Date: 2026-05-19 17:10:00
"""

from alembic import op

# revision identifiers
revision = "013_status_to_string"
down_revision = "012_role_to_string"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users MODIFY COLUMN status VARCHAR(50) NOT NULL DEFAULT 'active'"
    )
    op.execute("UPDATE users SET status = LOWER(status) WHERE status IS NOT NULL")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users MODIFY COLUMN status ENUM("
        "'active','inactive','pending'"
        ") NOT NULL DEFAULT 'active'"
    )
