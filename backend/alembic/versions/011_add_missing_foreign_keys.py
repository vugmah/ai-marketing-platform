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

# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # 1. ad_campaigns.platform_account_id
    op.add_column(
        "ad_campaigns",
        sa.Column("platform_account_id", sa.Integer(), nullable=True, index=True),
        schema="public",
    )
    op.create_foreign_key(
        "fk_ad_campaigns_platform_account_id",
        "ad_campaigns",
        "ad_platforms",
        ["platform_account_id"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
        source_schema="public",
        referent_schema="public",
    )

    # 2. ad_audiences.platform_account_id
    op.add_column(
        "ad_audiences",
        sa.Column("platform_account_id", sa.Integer(), nullable=True, index=True),
        schema="public",
    )
    op.create_foreign_key(
        "fk_ad_audiences_platform_account_id",
        "ad_audiences",
        "ad_platforms",
        ["platform_account_id"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
        source_schema="public",
        referent_schema="public",
    )

    # 3. ai_conversations.prompt_id -> ai_prompts.id FK
    op.create_foreign_key(
        "fk_ai_conversations_prompt_id",
        "ai_conversations",
        "ai_prompts",
        ["prompt_id"],
        ["id"],
        ondelete="SET NULL",
        onupdate="CASCADE",
        source_schema="public",
        referent_schema="public",
    )

    # 4. ai_messages.conversation_id -> ai_conversations.id FK
    op.create_foreign_key(
        "fk_ai_messages_conversation_id",
        "ai_messages",
        "ai_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="CASCADE",
        onupdate="CASCADE",
        source_schema="public",
        referent_schema="public",
    )


def downgrade():
    # 4
    op.drop_constraint(
        "fk_ai_messages_conversation_id",
        "ai_messages",
        schema="public",
        type_="foreignkey",
    )
    # 3
    op.drop_constraint(
        "fk_ai_conversations_prompt_id",
        "ai_conversations",
        schema="public",
        type_="foreignkey",
    )
    # 2
    op.drop_constraint(
        "fk_ad_audiences_platform_account_id",
        "ad_audiences",
        schema="public",
        type_="foreignkey",
    )
    op.drop_column("ad_audiences", "platform_account_id", schema="public")
    # 1
    op.drop_constraint(
        "fk_ad_campaigns_platform_account_id",
        "ad_campaigns",
        schema="public",
        type_="foreignkey",
    )
    op.drop_column("ad_campaigns", "platform_account_id", schema="public")
