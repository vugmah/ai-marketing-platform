"""011_add_missing_foreign_keys

Revision ID: 011
Revises: 010
Create Date: 2026-05-18

Eksik ForeignKey'leri ekler:
- ad_campaigns.platform_account_id
- ad_audiences.platform_account_id
- ai_conversations.prompt_id -> ai_prompts.id
- ai_messages.conversation_id -> ai_conversations.id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def _column_exists(table_name, column_name, schema=None):
    """Return True if column exists on table."""
    bind = op.get_bind()
    try:
        columns = [c["name"] for c in inspect(bind).get_columns(table_name, schema=schema)]
    except Exception:
        return False
    return column_name in columns


def _constraint_exists(table_name, constraint_name, schema=None):
    """Return True if FK constraint exists on table."""
    bind = op.get_bind()
    try:
        fks = inspect(bind).get_foreign_keys(table_name, schema=schema)
    except Exception:
        return False
    return any(fk.get("name") == constraint_name for fk in fks)


def upgrade():
    # 1. ad_campaigns.platform_account_id
    if not _column_exists("ad_campaigns", "platform_account_id"):
        op.add_column(
            "ad_campaigns",
            sa.Column("platform_account_id", sa.Integer(), nullable=True, index=True),
            schema=None,
        )
    if not _constraint_exists("ad_campaigns", "fk_ad_campaigns_platform_account_id"):
        op.create_foreign_key(
            "fk_ad_campaigns_platform_account_id",
            "ad_campaigns",
            "ad_platforms",
            ["platform_account_id"],
            ["id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
            source_schema=None,
            referent_schema=None,
        )

    # 2. ad_audiences.platform_account_id
    if not _column_exists("ad_audiences", "platform_account_id"):
        op.add_column(
            "ad_audiences",
            sa.Column("platform_account_id", sa.Integer(), nullable=True, index=True),
            schema=None,
        )
    if not _constraint_exists("ad_audiences", "fk_ad_audiences_platform_account_id"):
        op.create_foreign_key(
            "fk_ad_audiences_platform_account_id",
            "ad_audiences",
            "ad_platforms",
            ["platform_account_id"],
            ["id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
            source_schema=None,
            referent_schema=None,
        )

    # 3. ai_conversations.prompt_id -> ai_prompts.id FK
    if not _constraint_exists("ai_conversations", "fk_ai_conversations_prompt_id"):
        op.create_foreign_key(
            "fk_ai_conversations_prompt_id",
            "ai_conversations",
            "ai_prompts",
            ["prompt_id"],
            ["id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
            source_schema=None,
            referent_schema=None,
        )

    # 4. ai_messages.conversation_id -> ai_conversations.id FK
    if not _constraint_exists("ai_messages", "fk_ai_messages_conversation_id"):
        op.create_foreign_key(
            "fk_ai_messages_conversation_id",
            "ai_messages",
            "ai_conversations",
            ["conversation_id"],
            ["id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
            source_schema=None,
            referent_schema=None,
        )


def downgrade():
    # 4
    if _constraint_exists("ai_messages", "fk_ai_messages_conversation_id"):
        op.drop_constraint(
            "fk_ai_messages_conversation_id",
            "ai_messages",
            schema=None,
            type_="foreignkey",
        )
    # 3
    if _constraint_exists("ai_conversations", "fk_ai_conversations_prompt_id"):
        op.drop_constraint(
            "fk_ai_conversations_prompt_id",
            "ai_conversations",
            schema=None,
            type_="foreignkey",
        )
    # 2
    if _constraint_exists("ad_audiences", "fk_ad_audiences_platform_account_id"):
        op.drop_constraint(
            "fk_ad_audiences_platform_account_id",
            "ad_audiences",
            schema=None,
            type_="foreignkey",
        )
    if _column_exists("ad_audiences", "platform_account_id"):
        op.drop_column("ad_audiences", "platform_account_id", schema=None)
    # 1
    if _constraint_exists("ad_campaigns", "fk_ad_campaigns_platform_account_id"):
        op.drop_constraint(
            "fk_ad_campaigns_platform_account_id",
            "ad_campaigns",
            schema=None,
            type_="foreignkey",
        )
    if _column_exists("ad_campaigns", "platform_account_id"):
        op.drop_column("ad_campaigns", "platform_account_id", schema=None)
